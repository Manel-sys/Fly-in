from .map import Map, Connection
from .validation_models import ZoneType


class ReservationError(Exception):
    """Raised when a reservation table operation is attempted against
    an already-full zone/connection, or when releasing a reservation
    that was never made."""
    pass


class ReservationTable:
    """Tracks per-turn occupancy of every zone and connection, and
    exposes the atomic "can this move/wait happen" and "make this
    move/wait happen" operations used during A* search and path
    commitment.
    """

    def __init__(self, graph: Map) -> None:
        """Create an empty reservation table for the given map.

        Args:
            graph: The map whose zones and connections this table will
                track occupancy for.
        """

        self.zone_reservs: dict[tuple[str, int], int] = {}
        self.connection_reservs: dict[tuple[str, int], int] = {}
        self.graph: Map = graph

    def reserve_zone(self, turn: int, zone: str,) -> None:
        """Claim one unit of occupancy in a zone at a given turn.

        Args:
            turn: The turn to reserve occupancy at.
            zone: The zone to reserve.

        Raises:
            ReservationError: If the zone is already at its
                ``max_drones`` capacity at this turn.
        """

        if not self.is_zone_available(turn, zone):
            raise ReservationError(f"Zone {zone} is at capacity at"
                                   f" turn {turn}")

        self.zone_reservs[(zone, turn)] = (
            self.zone_reservs.get((zone, turn), 0) + 1
        )

    def release_zone(self, turn: int, zone: str) -> None:
        """Free one previously-claimed unit of occupancy in a zone at a
        given turn.

        Args:
            turn: The turn to release occupancy at.
            zone: The zone to release.

        Raises:
            ReservationError: If there is no existing reservation to
                release (occupancy at this (zone, turn) is already 0).
        """

        current = self.zone_reservs.get((zone, turn), 0)

        if current <= 0:
            raise ReservationError(f"No reservation to release for {zone}"
                                   f" at turn {turn}")

        self.zone_reservs[(zone, turn)] = current - 1

    def is_zone_available(self, turn: int, zone: str) -> bool:
        """Check whether a zone has spare capacity at a given turn.

        Args:
            turn: The turn to check.
            zone: The zone to check.

        Returns:
            ``True`` if current occupancy is below the zone's
            ``max_drones``.
        """

        current: int = self.zone_reservs.get((zone, turn), 0)

        capacity: int = self.graph.zones[zone].max_drones

        return current < capacity

    def reserve_connection(self, turn: int, zone1: str, zone2: str) -> None:
        """Claim one unit of occupancy on a connection at a given turn.

        Args:
            turn: The turn to reserve occupancy at.
            zone1: One endpoint of the connection.
            zone2: The other endpoint of the connection.

        Raises:
            ReservationError: If the connection is already at its
                ``max_link_capacity`` at this turn.
        """

        connection: Connection = self.graph.connections[zone1][zone2]

        if not self.is_connection_available(turn, zone1, zone2):
            raise ReservationError(
                f"Connection {connection.get_id()} is at capacity "
                "and cannot be reserved at this time"
            )

        key = (connection.get_id(), turn)
        self.connection_reservs[key] = self.connection_reservs.get(key, 0) + 1

    def is_connection_available(self, turn: int,
                                zone1: str, zone2: str) -> bool:
        """Check whether a connection has spare capacity at a given
        turn.

        Args:
            turn: The turn to check.
            zone1: One endpoint of the connection.
            zone2: The other endpoint of the connection.

        Returns:
            ``True`` if current occupancy is below the connection's
            ``max_link_capacity``.
        """

        connection: Connection = self.graph.connections[zone1][zone2]

        current: int = self.connection_reservs.get((connection.get_id(),
                                                    turn), 0)

        capacity: int = connection.max_link_capacity

        return current < capacity

    def release_connection(self, turn: int, zone1: str, zone2: str) -> None:
        """Free one previously-claimed unit of occupancy on a
        connection at a given turn.

        Args:
            turn: The turn to release occupancy at.
            zone1: One endpoint of the connection.
            zone2: The other endpoint of the connection.

        Raises:
            ReservationError: If there is no existing reservation to
                release.
        """

        connection = self.graph.connections[zone1][zone2]

        key = (connection.get_id(), turn)
        current = self.connection_reservs.get(key, 0)

        if current <= 0:
            raise ReservationError(f"No reservation to release for "
                                   f"{connection.get_id()} at turn {turn}")

        self.connection_reservs[key] = current - 1

    def can_move(self, turn: int, zone1: str, zone2: str) -> tuple[bool, int]:
        """Check, without reserving anything, whether a drone could
        legally depart ``zone1`` for ``zone2`` at ``turn``.

        Accounts for the destination zone's movement cost (1 turn for
        normal/priority, 2 turns for restricted), checking that the
        connection is free for every turn of the transit and that the
        destination zone has capacity at the computed arrival turn.
        Blocked destination zones are always rejected.

        Args:
            turn: The turn the drone would depart at.
            zone1: The zone the drone is departing from.
            zone2: The zone the drone would move into.

        Returns:
            A tuple of (is legal, arrival turn). If not legal, arrival
            turn is ``-1``.
        """

        if self.graph.zones[zone2].zone_type == ZoneType.BLOCKED:
            return False, -1

        duration: int = self.graph.zones[zone2].weight()
        arrival: int = turn + duration

        for t in range(turn, arrival):
            if not self.is_connection_available(t, zone1, zone2):
                return False, -1

        if not self.is_zone_available(arrival, zone2):
            return False, -1

        return True, arrival

    def commit_move(self, turn: int, zone1: str, zone2: str) -> int:
        """Reserve every connection turn and the destination zone for a
        move from ``zone1`` to ``zone2`` starting at ``turn``.

        Re-validates via ``can_move`` before reserving anything, so the
        whole move is committed atomically -- either every reservation
        succeeds, or none of them are made.

        Args:
            turn: The turn the drone departs at.
            zone1: The zone the drone is departing from.
            zone2: The zone the drone is moving into.

        Returns:
            The turn the drone arrives at ``zone2``.

        Raises:
            ReservationError: If the move is not currently legal.
        """

        ok, arrival = self.can_move(turn, zone1, zone2)

        if not ok:
            raise ReservationError(f"Cannot commit move from {zone1} to"
                                   f" {zone2} at turn {turn}")

        for t in range(turn, arrival):
            self.reserve_connection(t, zone1, zone2)

        self.reserve_zone(arrival, zone2)

        return arrival

    def can_wait(self, turn: int, zone: str) -> bool:
        """Check whether a drone could legally remain in ``zone`` for
        one more turn.

        Args:
            turn: The turn the drone is currently at.
            zone: The zone the drone would continue waiting in.

        Returns:
            ``True`` if the zone has spare capacity at ``turn + 1``.
        """
        return self.is_zone_available(turn + 1, zone)

    def commit_wait(self, turn: int, zone: str) -> int:
        """Reserve one more turn of occupancy for a drone waiting in
        ``zone``.

        Args:
            turn: The turn the drone is currently at.
            zone: The zone the drone continues waiting in.

        Returns:
            The turn the drone is now at (``turn + 1``).

        Raises:
            ReservationError: If the zone has no spare capacity at
                ``turn + 1``.
        """

        if not self.is_zone_available(turn + 1, zone):
            raise ReservationError(f"Cannot wait at {zone}: no capacity at"
                                   f" {turn + 1}")

        self.reserve_zone(turn + 1, zone)

        return turn + 1

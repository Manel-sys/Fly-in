from .map import Connection, Map


class Drone:
    """A single drone moving along a precomputed (zone, turn) path.

    Attributes:
        id: Unique identifier for this drone.
        position: The zone the drone currently occupies. Only meaningful
            when the drone is not mid-transit on a restricted move.
        connection: The connection the drone currently occupies while
            mid-transit on a restricted (multi-turn) move, or ``None``
            when settled at a zone.
        moved: ``True`` if the drone's zone changed on the most recently
            processed turn (i.e. it just arrived somewhere new).
        intransit: ``True`` if the drone is currently between its
            departure and arrival turn on a restricted (multi-turn) move.
    """

    def __init__(self, drone_id: int, drone_zone: str) -> None:
        """Create a drone positioned at its starting zone.

        Args:
            drone_id: Unique identifier for this drone.
            drone_zone: The zone name the drone starts at (normally the
                map's start hub).
        """

        self.id: int = drone_id
        self.position: str = drone_zone
        self.connection: Connection | None = None
        self.moved: bool = False
        self.intransit: bool = False

    def get_position(self) -> str:
        """Return the zone this drone currently occupies."""
        return self.position

    def get_id(self) -> int:
        """Return this drone's unique identifier."""
        return self.id

    def get_connection(self) -> Connection | None:
        """Return the connection this drone is mid-transit on, if any."""
        return self.connection

    def next_turn(self, path: list[tuple[str, int]],
                  turn: int, map: Map) -> None:
        """Update this drone's state to reflect the given simulation turn.

        Scans the drone's path for the segment that covers ``turn`` and
        updates ``position``, ``connection``, ``moved`` and ``intransit``
        accordingly:

        - If ``turn`` is exactly a segment's arrival turn, the drone is
          placed at the destination zone and ``moved`` reflects whether
          the zone actually changed (a wait segment never counts as a
          move).
        - If ``turn`` falls strictly inside a multi-turn (restricted)
          segment, the drone is marked as occupying that connection and,
          if strictly between departure and arrival, as ``intransit``.
        - Otherwise (typically a wait segment's departure turn), nothing
          changes and ``moved``/``intransit`` are reset to ``False``.

        This method is stateless with respect to any previous call: it
        always re-scans the full path from the start, so it can be
        called with turns in any order.

        Args:
            path: The drone's full path, as a list of (zone, turn) pairs
                as returned by the scheduler.
            turn: The simulation turn to update the drone's state for.
            map: The map, used to resolve connection objects for
                mid-transit moves.
        """

        for i in range(len(path) - 1):
            zone1, t1 = path[i]
            zone2, t2 = path[i + 1]

            if turn == t2:
                self.position = zone2
                self.connection = None
                self.moved = (zone1 != zone2)
                self.intransit = False
                return

            if (t2 - t1) > 1 and t1 <= turn < t2:
                self.connection = map.connections[zone1][zone2]
                self.moved = False
                if t1 < turn < t2:
                    self.intransit = True
                return

            self.moved = False
            self.intransit = False

    @staticmethod
    def get_render_position(path: list[tuple[str, int]],
                            frac_turn: float,
                            graph: Map) -> tuple[float, float]:
        """Return the map coordinates to draw a drone at for a given
        continuous turn value.

        Unlike ``next_turn``, ``frac_turn`` may be fractional (e.g. 3.4
        means 40% of the way between turn 3 and turn 4), allowing a
        renderer to smoothly interpolate a drone's position between
        turns rather than snapping it discretely. This method is a pure,
        stateless computation: it does not read or write any drone
        state, and is safe to call with ``frac_turn`` moving forward,
        backward, or jumping arbitrarily between calls.

        Args:
            path: The drone's full path, as a list of (zone, turn) pairs.
            frac_turn: The (possibly fractional) turn to compute a
                position for.
            graph: The map, used to resolve each zone's coordinates.

        Returns:
            The (x, y) map coordinates the drone should be drawn at.
        """

        for i in range(len(path) - 1):
            zone1, t1 = path[i]
            zone2, t2 = path[i + 1]

            if t1 <= frac_turn <= t2:
                x1, y1 = graph.zones[zone1].coordinates
                x2, y2 = graph.zones[zone2].coordinates

                if zone1 == zone2 or t2 == t1:
                    return float(x1), float(y1)

                progress = (frac_turn - t1) / (t2 - t1)
                x = x1 + (x2 - x1) * progress
                y = y1 + (y2 - y1) * progress
                return x, y

        last_zone = path[-1][0]
        x, y = graph.zones[last_zone].coordinates
        return float(x), float(y)

    @staticmethod
    def generate_drone_fleet(map: Map) -> list["Drone"]:
        """Build the full fleet of drones for a parsed map.

        Every drone starts at the map's start hub, per the subject's
        rules (all drones begin at the same zone). Drone ids are
        assigned sequentially starting at 1.

        Args:
            map: The parsed map, providing ``start_hub`` and
                ``nb_drones``.

        Returns:
            A list of ``nb_drones`` drones, all positioned at
            ``map.start_hub``, or an empty list if the map has no start
            hub set.
        """

        if map.start_hub is None:
            return []
        else:
            return [Drone(i, map.start_hub)
                    for i in range(1, map.nb_drones + 1)]

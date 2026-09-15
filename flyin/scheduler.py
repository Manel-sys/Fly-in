from .map import Map
from .drone import Drone
from .solver import Solver
from .reservation_table import ReservationTable, ReservationError


class SchedulerError(Exception):
    """Raised when a drone cannot be scheduled within the configured
    turn horizon, given the reservations already committed by earlier
    drones."""
    pass


class Scheduler:
    """Sequentially plans and commits a path for every drone in a
    fleet, using time-expanded A* search against a shared
    ``ReservationTable``.
    """

    def __init__(self, graph: Map, max_turns: int,
                 drones: list[Drone]) -> None:
        """Set up a scheduler for the given map and fleet.

        Precomputes the static, reservation-independent shortest-turn
        distance from every zone to the end hub once, up front, to use
        as the A* heuristic for every drone's search.

        Args:
            graph: The map to schedule drones on.
            max_turns: The search horizon (in turns) each drone's A*
                search is allowed to explore before giving up.
            drones: The fleet of drones to schedule, in the order they
                will be planned (earlier drones get first pick of the
                cheapest routes).
        """

        self.map: Map = graph
        self.solver: Solver = Solver(graph)
        self.max_turns: int = max_turns
        self.drones: list[Drone] = drones
        self.reservations: ReservationTable = ReservationTable(self.map)
        self.heuristic: dict[str, int | float] = self._set_heuristic()

    def _set_heuristic(self) -> dict[str, int | float]:
        """Compute the static, unconstrained shortest-turn distance from
        every zone to the map's end hub, used as the A* heuristic.

        Returns:
            A dict mapping each zone name to its shortest-path turn
            cost to the end hub, ignoring reservations.
        """

        heuristic, _ = self.solver.dijkstra(self.map.end_hub)

        return heuristic

    def _commit_path(self, path: list[tuple[str, int]]) -> None:
        """Reserve every hop of a drone's already-found path in the
        shared reservation table.

        Walks the path pairwise, committing a wait for same-zone
        segments and a move for zone-changing segments, so subsequent
        drones' searches see this drone's occupancy.

        Args:
            path: The full (zone, turn) path to commit.

        Raises:
            SchedulerError: If any segment can no longer be committed
                (should not normally happen, since the path was just
                found against this same table).
        """

        for i in range(len(path) - 1):
            zone1, t1 = path[i]
            zone2, t2 = path[i + 1]

            try:
                if zone1 == zone2:
                    self.reservations.commit_wait(t1, zone1)
                else:
                    self.reservations.commit_move(t1, zone1, zone2)
            except ReservationError as e:
                raise SchedulerError(e)

    def schedule_all(self) -> dict[int, list[tuple[str, int]]]:
        """Plan and commit a path for every drone in the fleet, in
        order.

        For each drone, in turn, runs A* against the current state of
        the shared reservation table, commits the resulting path if one
        was found, and moves on to the next drone -- so each drone's
        search is shaped by every previously-scheduled drone's
        reservations.

        Returns:
            A dict mapping each drone's id to its scheduled path.

        Raises:
            SchedulerError: If any drone has no feasible path within
                ``max_turns``, given the reservations already committed
                by earlier drones.
        """

        paths: dict[int, list[tuple[str, int]]] = {}

        for d in self.drones:
            path = self.solver.astar_path(d.get_position(), 0,
                                          self.reservations, self.heuristic,
                                          self.max_turns)

            if path is None:
                raise SchedulerError(f"Could not find path for D{d.get_id()}"
                                     " within the given horizon - "
                                     f"{self.max_turns} turns")

            self._commit_path(path)
            paths[d.get_id()] = path

        return paths

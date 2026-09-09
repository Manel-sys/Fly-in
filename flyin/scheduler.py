from .map import Map
from .drone import Drone
from .solver import Solver
from .reservation_table import ReservationTable, ReservationError


class SchedulerError(Exception):
    pass


class Scheduler:
    def __init__(self, graph: Map, max_turns: int,
                 drones: list[Drone]) -> None:

        self.map: Map = graph
        self.solver: Solver = Solver(graph)
        self.max_turns: int = max_turns
        self.drones: list[Drone] = drones
        self.reservations: ReservationTable = ReservationTable(self.map)
        self.heuristic: dict[str, int | float] = self._set_heuristic()

    def _set_heuristic(self) -> dict[str, int | float]:
        heuristic, _ = self.solver.dijkstra(self.map.end_hub)

        return heuristic

    def _commit_path(self, path: list[tuple[str, int]]) -> None:

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

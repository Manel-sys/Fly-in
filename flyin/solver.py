from .map import Map
from .validation_models import ZoneType
from .priority_queue import MinPriorityQueue
from .scheduler import ReservationTable


class SolverError(Exception):
    pass


class Solver:
    def __init__(self, map: Map) -> None:
        self.graph: Map = map

    def dijkstra(self, from_zone: str) -> tuple[dict[str, int | float],
                                                dict[str, str | None]]:
        zones: list[str] = self.graph.get_zones()
        if from_zone not in zones:
            raise SolverError(f"Could not find Zone {from_zone}"
                              " in graph zones.")

        distances: dict[str, int | float] = {zone: float("inf")
                                             for zone in zones}

        previous: dict[str, str | None] = {zone: None for zone in zones}

        distances[from_zone] = 0

        queue: MinPriorityQueue = MinPriorityQueue([(0, from_zone)])

        while not queue.is_empty():
            current_distance, current = queue.pop()

            if current_distance > distances[current]:
                continue

            for neighbour in self.graph.connections[current]:
                if self.graph.zones[neighbour].zone_type == ZoneType.BLOCKED:
                    continue

                weight: int | float = self.graph.zones[neighbour].weight()
                new_distance: int | float = current_distance + weight

                if new_distance < distances[neighbour]:
                    distances[neighbour] = new_distance
                    previous[neighbour] = current

                    queue.push(new_distance, neighbour)

        return distances, previous

    def get_path(self, previous: dict[str, str | None],
                 from_zone: str, to_zone: str) -> list[str]:
        path: list[str] = []
        zones: list[str] = self.graph.get_zones()

        if from_zone not in zones:
            raise SolverError(f"Could not find Zone {from_zone}"
                              " in graph zones.")
        elif to_zone not in zones:
            raise SolverError(f"Could not find Zone {to_zone}"
                              " in graph zones.")

        current: str | None = to_zone
        while current:
            path.append(current)

            if current == from_zone:
                return path[::-1]

            current = previous[current]

        raise SolverError(f"No path exists from {from_zone} to {to_zone}")

    def solvable(self) -> bool:
        distances: dict[str, int | float] = {}
        previous: dict[str, str | None] = {}

        distances, previous = self.dijkstra(self.graph.start_hub)

        return distances[self.graph.end_hub] != float("inf")

    def astar_path(self, start_zone: str, turn: int,
                   reservations: ReservationTable,
                   heuristic: dict[str, int | float],
                   horizon: int) -> list[tuple[str, int]] | None:

        start_state: tuple[str, int] = (start_zone, turn)
        queue: MinPriorityQueue = MinPriorityQueue([(heuristic[start_zone],
                                                     (0, start_state))])

        g_score: dict[tuple[str, int], int] = {start_state: turn}
        previous: dict[tuple[str, int],
                       tuple[str, int] | None] = {start_state: None}
        closed: set[tuple[str, int]] = set()

        while not queue.is_empty():
            _, (_, current) = queue.pop()
            zone, t = current

            if current in closed:
                continue
            closed.add(current)

            if zone == self.graph.end_hub:
                return self._reconstruct(previous, current)

            if t >= horizon:
                continue

            if reservations.can_wait(t, zone):
                self._try_relax(current, (zone, t + 1),
                                1, g_score, previous, heuristic,
                                queue, closed)

            for zone2 in self.graph.connections[zone]:
                ok, arrival = reservations.can_move(t, zone, zone2)
                if ok:
                    cost: int = arrival - t
                    neighbour: tuple[str, int] = (zone2, arrival)

                    self._try_relax(current, neighbour, cost, g_score,
                                    previous, heuristic, queue, closed)

        return None

    def _try_relax(self, current: tuple[str, int],
                   neighbour: tuple[str, int],
                   cost: int, g_score: dict[tuple[str, int], int],
                   previous: dict[tuple[str, int], tuple[str, int] | None],
                   heuristic: dict[str, int | float],
                   queue: MinPriorityQueue, closed: set[tuple[str, int]]
                   ) -> None:

        if neighbour in closed:
            return

        zone_type: ZoneType = self.graph.zones[neighbour[0]].zone_type
        new_g_score: int = g_score[current] + cost

        if new_g_score < g_score.get(neighbour, float("inf")):
            g_score[neighbour] = new_g_score
            previous[neighbour] = current

            f = new_g_score + heuristic[neighbour[0]]
            if zone_type == ZoneType.PRIORITY:
                penalty: int = 0
            else:
                penalty: int = 1

            queue.push(f, (penalty, neighbour))

    def _reconstruct(self,
                     previous: dict[tuple[str, int], tuple[str, int] | None],
                     end: tuple[str, int],
                     ) -> list[tuple[str, int]]:

        path: list[tuple[str, int]] = []
        current: tuple[str, int] | None = end
        while current is not None:
            path.append(current)
            current = previous[current]

        return path[::-1]

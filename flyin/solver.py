from .map import Map
from .validation_models import ZoneType
from .priority_queue import MinPriorityQueue


class Solver:
    def __init__(self, map: Map) -> None:
        self.graph: Map = map

    def dijkstra(self) -> tuple[dict[str, int | float], dict[str, str | None]]:
        zones: list[str] = self.graph.get_zones()

        distances: dict[str, int | float] = {zone: float("inf")
                                             for zone in zones}

        previous: dict[str, str | None] = {zone: None for zone in zones}

        distances[self.graph.start_hub] = 0

        queue: MinPriorityQueue = MinPriorityQueue([(0, self.graph.start_hub)])

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

    def get_path(self, previous: dict[str, str | None]) -> list[str]:
        path: list[str] = []

        current: str | None = self.graph.end_hub
        while current:
            path.append(current)

            if current == self.graph.start_hub:
                break

            current = previous[current]

        return path[::-1]

    def solvable(self) -> bool:
        distances: dict[str, int | float] = {}
        previous: dict[str, str | None] = {}

        distances, previous = self.dijkstra()

        return distances[self.graph.end_hub] != float("inf")

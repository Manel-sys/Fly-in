from .map import Map, Connection
from .validation_models import ZoneType
from .priority_queue import MinPriorityQueue


class SolverError(Exception):
    pass


class ReservationTable:
    def __init__(self, graph: Map) -> None:
        self.zone_reservs: dict[tuple[int, str], int] = {}
        self.connection_reservs: dict[tuple[int, str], int] = {}
        self.graph: Map = graph

    def reserve_zone(self, turn: int, zone: str) -> None:
        if not self.is_zone_available(turn, zone):
            raise SolverError(f"Zone {zone} is at capacity at turn {turn}")

        self.zone_reservs[(turn, zone)] = (
            self.zone_reservs.get((turn, zone), 0) + 1
        )

    def release_zone(self, turn: int, zone: str) -> None:
        current = self.zone_reservs.get((turn, zone), 0)

        if current <= 0:
            raise SolverError(f"No reservation to release for {zone}"
                              f" at turn {turn}")

        self.zone_reservs[(turn, zone)] = current - 1

    def is_zone_available(self, turn: int, zone: str) -> bool:
        current: int = self.zone_reservs.get((turn, zone), 0)

        capacity: int = self.graph.zones[zone].max_drones

        return current < capacity

    def reserve_connections(self, turn: int, zone1: str, zone2: str) -> None:
        connection: Connection = self.graph.connections[zone1][zone2]

        if not self.is_connection_available(turn, zone1, zone2):
            raise SolverError(
                f"Connection {connection.get_id()} is at capacity "
                "and cannot be reserved at this time"
            )

        key = (turn, connection.get_id())
        self.connection_reservs[key] = self.connection_reservs.get(key, 0) + 1

    def is_connection_available(self, turn: int,
                                zone1: str, zone2: str) -> bool:

        connection: Connection = self.graph.connections[zone1][zone2]

        current: int = self.connection_reservs.get((turn,
                                                    connection.get_id()), 0)

        capacity: int = connection.max_link_capacity

        return current < capacity

    def release_connection(self, turn: int, zone1: str, zone2: str) -> None:
        connection = self.graph.connections[zone1][zone2]

        key = (turn, connection.get_id())
        current = self.connection_reservs.get(key, 0)

        if current <= 0:
            raise SolverError(f"No reservation to release for "
                              f"{connection.get_id()} at turn {turn}")

        self.connection_reservs[key] = current - 1

    def can_move(self, turn: int, zone1: str, zone2: str) -> tuple[bool, int]:
        pass

    def commit_move(self, turn: int, zone1: str, zone2: str) -> int:
        pass

    def can_wait(self, turn: int, zone: str) -> bool:
        pass

    def commit_wait(self, turn: int, zone: str) -> int:
        pass


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

from .map import Map, Connection
from .validation_models import ZoneType
from .drone import Drone
from .solver import Solver


class SchedulerError(Exception):
    pass


class ReservationTable:
    def __init__(self, graph: Map) -> None:
        self.zone_reservs: dict[tuple[str, int], int] = {}
        self.connection_reservs: dict[tuple[str, int], int] = {}
        self.graph: Map = graph

    def reserve_zone(self, turn: int, zone: str,) -> None:
        if not self.is_zone_available(turn, zone):
            raise SchedulerError(f"Zone {zone} is at capacity at turn {turn}")

        self.zone_reservs[(zone, turn)] = (
            self.zone_reservs.get((zone, turn), 0) + 1
        )

    def release_zone(self, turn: int, zone: str) -> None:
        current = self.zone_reservs.get((zone, turn), 0)

        if current <= 0:
            raise SchedulerError(f"No reservation to release for {zone}"
                                 f" at turn {turn}")

        self.zone_reservs[(zone, turn)] = current - 1

    def is_zone_available(self, turn: int, zone: str) -> bool:
        current: int = self.zone_reservs.get((zone, turn), 0)

        capacity: int = self.graph.zones[zone].max_drones

        return current < capacity

    def reserve_connection(self, turn: int, zone1: str, zone2: str) -> None:
        connection: Connection = self.graph.connections[zone1][zone2]

        if not self.is_connection_available(turn, zone1, zone2):
            raise SchedulerError(
                f"Connection {connection.get_id()} is at capacity "
                "and cannot be reserved at this time"
            )

        key = (connection.get_id(), turn)
        self.connection_reservs[key] = self.connection_reservs.get(key, 0) + 1

    def is_connection_available(self, turn: int,
                                zone1: str, zone2: str) -> bool:

        connection: Connection = self.graph.connections[zone1][zone2]

        current: int = self.connection_reservs.get((connection.get_id(),
                                                    turn), 0)

        capacity: int = connection.max_link_capacity

        return current < capacity

    def release_connection(self, turn: int, zone1: str, zone2: str) -> None:
        connection = self.graph.connections[zone1][zone2]

        key = (connection.get_id(), turn)
        current = self.connection_reservs.get(key, 0)

        if current <= 0:
            raise SchedulerError(f"No reservation to release for "
                                 f"{connection.get_id()} at turn {turn}")

        self.connection_reservs[key] = current - 1

    def can_move(self, turn: int, zone1: str, zone2: str) -> tuple[bool, int]:

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
        ok, arrival = self.can_move(turn, zone1, zone2)

        if not ok:
            raise SchedulerError(f"Cannot commit move from {zone1} to {zone2}"
                                 f" at turn {turn}")

        for t in range(turn, arrival):
            self.reserve_connection(t, zone1, zone2)

        self.reserve_zone(arrival, zone2)

        return arrival

    def can_wait(self, turn: int, zone: str) -> bool:
        return self.is_zone_available(turn + 1, zone)

    def commit_wait(self, turn: int, zone: str) -> int:
        if not self.is_zone_available(turn + 1, zone):
            raise SchedulerError(f"Cannot wait at {zone}: no capacity at"
                                 f" {turn + 1}")

        self.reserve_zone(turn + 1, zone)

        return turn + 1


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

            if zone1 == zone2:
                self.reservations.commit_wait(t1, zone1)
            else:
                self.reservations.commit_move(t1, zone1, zone2)

    def schedule_all(self) -> dict[int, list[tuple[str, int]]]:

        paths: dict[int, list[tuple[str, int]]] = {}

        for d in self.drones:
            path = self.solver.astar_path(d.get_position(), 0,
                                          self.reservations, self.heuristic,
                                          self.max_turns)

            if path is None:
                raise SchedulerError(f"Could not find path for D{d.get_id()}"
                                     " within the given horizon -"
                                     f"{self.max_turns} turns")

            self._commit_path(path)
            paths[d.get_id()] = path

        return paths

from .map import Connection, Map


class Drone:
    def __init__(self, drone_id: int, drone_zone: str) -> None:
        self.id: int = drone_id
        self.position: str = drone_zone
        self.connection: Connection | None = None
        self.moved: bool = False

    def get_position(self) -> str:
        return self.position

    def get_id(self) -> int:
        return self.id

    def get_connection(self) -> Connection | None:
        return self.connection

    def next_turn(self, path: list[tuple[str, int]], turn: int,
                  map: Map, index: int) -> int:

        if index >= len(path) - 1:
            return -1

        zone1, t1 = path[index]
        zone2, t2 = path[index + 1]

        if turn == t2:
            self.position = zone2
            self.connection = None
            self.moved = (zone1 != zone2)
            return index + 1

        if (t2 - t1) > 1 and t1 <= turn < t2:
            self.connection = map.connections[zone1][zone2]
            self.moved = False
            return index

        self.moved = False
        return index

    @staticmethod
    def generate_drone_fleet(map: Map) -> list["Drone"]:
        if map.start_hub is None:
            return []
        else:
            return [Drone(i, map.start_hub)
                    for i in range(1, map.nb_drones + 1)]

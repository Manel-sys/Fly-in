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

    def next_turn(self, path: list[tuple[str, int]],
                  turn: int, map: Map) -> None:

        for i in range(len(path) - 1):
            zone1, t1 = path[i]
            zone2, t2 = path[i + 1]

            if turn == t2:
                self.position = zone2
                self.connection = None
                self.moved = (zone1 != zone2)
                return

            if (t2 - t1) > 1 and t1 <= turn < t2:
                self.connection = map.connections[zone1][zone2]
                self.moved = False
                return

            self.moved = False

    @staticmethod
    def get_render_position(path: list[tuple],
                            frac_turn: float,
                            graph: Map) -> tuple[float, float]:

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
        if map.start_hub is None:
            return []
        else:
            return [Drone(i, map.start_hub)
                    for i in range(1, map.nb_drones + 1)]
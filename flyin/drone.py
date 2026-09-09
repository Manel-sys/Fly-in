from .map import Connection, Map


class Drone:
    def __init__(self, drone_id: int, drone_zone: str) -> None:
        self.id: int = drone_id
        self.position: str = drone_zone
        self.connection: Connection | None = None

    def get_position(self) -> str:
        return self.position

    def get_id(self) -> int:
        return self.id

    def get_connection(self) -> Connection | None:
        return self.connection

    @staticmethod
    def generate_drone_fleet(map: Map) -> list["Drone"]:
        if map.start_hub is None:
            return []
        else:
            return [Drone(i, map.start_hub) 
                    for i in range(1, map.nb_drones + 1)]

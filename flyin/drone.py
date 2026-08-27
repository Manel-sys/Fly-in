from .map import Connection


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

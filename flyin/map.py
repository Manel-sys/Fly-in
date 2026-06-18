from .validation_models import ZoneModel, ConnectionModel, ZoneType


class MapError(Exception):
    pass


class Zone:
    def __init__(self, data: ZoneModel) -> None:
        self.name: str = data.name
        self.coordinates: tuple[int, int] = data.coordinates
        self.zone_type: ZoneType = data.zone_type
        self.zone_color: str | None = data.zone_color
        self.max_drones: int = data.max_drones
        self.current_drones: int = 0


class Connection:
    def __init__(self, data: ConnectionModel) -> None:
        self.zone1: str = data.zone1
        self.zone2: str = data.zone2
        self.max_link_capacity: int = data.max_link_capacity
        self.current_drones: int = 0


class Map:
    def __init__(self, nb_drones: str) -> None:
        self.set_nb_drones(nb_drones)
        self.start_hub: str | None = None
        self.end_hub: str | None = None
        self.zones: dict[str, Zone] = {}
        self.connections: dict[str, dict[str, Connection]] = {}
        self.coordinates: set[tuple[int, int]] = set()

    def set_nb_drones(self, nb_drones: str) -> None:
        try:
            value: int = int(nb_drones)
        except ValueError:
            raise MapError("Number of drones must "
                           f"be a positive integer, got: '{nb_drones}'")
        if value <= 0:
            raise MapError("Number of drones "
                           f"must be a positive integer, got: '{nb_drones}'")
        self.nb_drones: int = value

    def add_zone(self, zone: ZoneModel) -> None:
        if zone.name in self.zones:
            raise MapError(f"Zone name: '{zone.name}' already exists in map.\n"
                           "Map can not have duplicate zones.")
        if zone.coordinates in self.coordinates:
            raise MapError(f"Duplicate coordinates: '{zone.coordinates}'"
                           " found in map")

        self.zones[zone.name] = Zone(zone)
        self.connections[zone.name] = {}
        self.coordinates.add(zone.coordinates)

    def add_connection(self, connect: ConnectionModel) -> None:
        if connect.zone1 not in self.zones:
            raise MapError("Trying to add connection to undefined zone:"
                           f" '{connect.zone1}'")
        if connect.zone2 not in self.zones:
            raise MapError("Trying to add connection to undefined zone:"
                           f" '{connect.zone2}'")
        if connect.zone2 in self.connections[connect.zone1]:
            raise MapError(f"Connection '<{connect.zone1}>-"
                           f"<{connect.zone2}>' already exists")
        connection: Connection = Connection(connect)
        self.connections[connect.zone1][connect.zone2] = connection
        self.connections[connect.zone2][connect.zone1] = connection

    def add_start_hub(self, start_zone: ZoneModel) -> None:
        self.add_zone(start_zone)
        self.start_hub = start_zone.name

    def add_end_hub(self, end_zone: ZoneModel) -> None:
        self.add_zone(end_zone)
        self.end_hub = end_zone.name

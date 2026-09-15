from .validation_models import ZoneModel, ConnectionModel, ZoneType


class MapError(Exception):
    """Raised when constructing or mutating a Map violates an invariant
    (duplicate zone names/coordinates, connections to undefined zones,
    an invalid drone count, or an unrecognised zone type's weight)."""
    pass


class Zone:
    """A single node in the map: a named location with a type, position,
    optional display color, and a maximum simultaneous drone capacity."""

    def __init__(self, data: ZoneModel) -> None:
        """Build a Zone from its already-validated pydantic model.

        Args:
            data: The validated zone data produced by the parser.
        """

        self.name: str = data.name
        self.coordinates: tuple[int, int] = data.coordinates
        self.zone_type: ZoneType = data.zone_type
        self.zone_color: str | None = data.zone_color
        self.max_drones: int = data.max_drones

    def weight(self) -> int:
        """Return the number of turns it costs to enter this zone.

        Normal and priority zones cost 1 turn; restricted zones cost 2
        turns. Blocked zones have no defined weight, since a drone can
        never legally enter one.

        Returns:
            The turn cost of entering this zone.

        Raises:
            MapError: If this zone's type has no defined movement cost
                (i.e. it is blocked).
        """

        if self.zone_type in (ZoneType.NORMAL, ZoneType.PRIORITY):
            return 1
        elif self.zone_type == ZoneType.RESTRICTED:
            return 2

        raise MapError(f"Cannot calculate weight for {self.zone_type}")

    def __str__(self) -> str:
        """Return a multi-line human-readable summary of this zone's
    fields, used by Map.show_zones() for debugging output."""
        return (f"name: {self.name}"
                f"\ncoordinates: {self.coordinates}"
                f"\nzone_type: {self.zone_type}"
                f"\nzone_color: {self.zone_color}"
                f"\nmax_drones: {self.max_drones}")


class Connection:
    """A bidirectional edge between two zones, with its own capacity
    limiting how many drones may traverse it simultaneously."""

    def __init__(self, data: ConnectionModel) -> None:
        """Build a Connection from its already-validated pydantic model.

        Args:
            data: The validated connection data produced by the parser.
        """

        self.zone1: str = data.zone1
        self.zone2: str = data.zone2
        self.max_link_capacity: int = data.max_link_capacity

    def __str__(self) -> str:
        """Return a single-line human-readable summary of this
    connection's fields, used by Map.show_connections() for debugging
    output."""
        return (f"zone1: {self.zone1}"
                f" | zone2: {self.zone2}"
                f" | max_link_capacity: {self.max_link_capacity}")

    def get_id(self) -> str:
        """Return this connection's canonical id, ``"<zone1>-<zone2>"``,
        as fixed at construction time regardless of travel direction."""
        return f"{self.zone1}-{self.zone2}"


class Map:
    """The full drone-zone network: every zone, every connection, the
    start/end hubs, and the number of drones to schedule.

    ``connections`` stores each connection twice -- once per direction
    (``connections[zone1][zone2]`` and ``connections[zone2][zone1]``,
    both pointing at the same ``Connection`` object) -- so any code that
    needs to enumerate each connection exactly once must deduplicate by
    its ``get_id()``.
    """

    def __init__(self, nb_drones: str) -> None:
        """Create an empty map with the given drone count.

        Args:
            nb_drones: The number of drones, as a string straight from
                the map file (validated and converted to int here).

        Raises:
            MapError: If ``nb_drones`` is not a positive integer.
        """

        self.set_nb_drones(nb_drones)
        self.start_hub: str | None = None
        self.end_hub: str | None = None
        self.zones: dict[str, Zone] = {}
        self.connections: dict[str, dict[str, Connection]] = {}
        self.coordinates: set[tuple[int, int]] = set()

    def set_nb_drones(self, nb_drones: str) -> None:
        """Validate and set the number of drones for this map.

        Args:
            nb_drones: The number of drones, as a string.

        Raises:
            MapError: If ``nb_drones`` cannot be parsed as an int, or is
                not strictly positive.
        """

        try:
            value: int = int(nb_drones)
        except ValueError:
            raise MapError("Number of drones must "
                           f"be a positive integer, got: '{nb_drones}'")
        if value <= 0:
            raise MapError("Number of drones "
                           f"must be a positive integer, got: '{nb_drones}'")
        self.nb_drones: int = value

    def get_nb_drones(self) -> int:
        """Return the number of drones configured for this map."""
        return self.nb_drones

    def add_zone(self, zone: ZoneModel) -> None:
        """Add a regular zone to the map.

        Args:
            zone: The validated zone data to add.

        Raises:
            MapError: If a zone with this name, or at these coordinates,
                already exists on the map.
        """

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
        """Add a bidirectional connection between two existing zones.

        Args:
            connect: The validated connection data to add.

        Raises:
            MapError: If either endpoint zone doesn't exist on the map,
                or if this exact connection already exists.
        """

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
        """Add the map's start zone and record it as ``start_hub``.

        Args:
            start_zone: The validated zone data for the start hub.
        """

        self.add_zone(start_zone)
        self.start_hub = start_zone.name

    def add_end_hub(self, end_zone: ZoneModel) -> None:
        """Add the map's end zone and record it as ``end_hub``.

        Args:
            end_zone: The validated zone data for the end hub.
        """

        self.add_zone(end_zone)
        self.end_hub = end_zone.name

    def get_zones(self) -> list[str]:
        """Return the names of every zone on the map."""
        return [zone for zone in self.zones]

    def get_connections(self) -> set[str]:
        """Return the id of every connection on the map, deduplicated.

        Since each connection is stored twice internally (once per
        direction), this walks the whole structure and collapses
        duplicates via each connection's canonical ``get_id()``.

        Returns:
            The set of unique connection ids on the map.
        """

        connects: set[str] = set()
        for zone1 in self.connections:
            for zone2 in self.connections[zone1]:
                connect = self.connections[zone1][zone2]
                connects.add(connect.get_id())

        return connects

    def get_connection(self, conn_id: str) -> Connection | None:
        """Look up a connection by its canonical id.

        Args:
            conn_id: A connection id in ``"<zone1>-<zone2>"`` form.

        Returns:
            The matching ``Connection``, or ``None`` if no connection
            with that id exists on the map.
        """

        connections: set[str] = self.get_connections()
        if conn_id in connections:
            zone1, zone2 = conn_id.split("-")
            return self.connections[zone1][zone2]

        return None

    def show_zones(self) -> None:
        """Print every zone's details to stdout, for debugging."""
        for zone in self.zones:
            print(self.zones[zone])
            print("---------------")

    def show_connections(self) -> None:
        """Print every connection's details to stdout, once each,
        for debugging."""
        shown: set[str] = set()

        for zone1 in self.connections:
            for zone2 in self.connections[zone1]:
                connect = self.connections[zone1][zone2]

                if connect.get_id() in shown:
                    continue

                print(f"Connection {connect.get_id()}")
                print(connect)
                print("------------------------")
                shown.add(connect.get_id())

from pydantic import BaseModel, Field, field_validator, model_validator
from enum import Enum


class ZoneType(Enum):
    """The four zone types a map file can declare, each with its own
    movement cost and pathfinding behaviour: normal and priority cost 1
    turn to enter (priority is preferred by the pathfinder on ties),
    restricted costs 2 turns, and blocked can never be entered."""

    NORMAL = "normal"
    BLOCKED = "blocked"
    RESTRICTED = "restricted"
    PRIORITY = "priority"


class ZoneModel(BaseModel):
    """Validated data for a single zone definition line from a map
    file, ready to be handed to ``Map.add_zone``/``add_start_hub``/
    ``add_end_hub``.
    """

    name: str
    coordinates: tuple[int, int]
    zone_type: ZoneType = ZoneType.NORMAL
    zone_color: str | None = None
    max_drones: int = Field(default=1, ge=1)

    @field_validator("name")
    @classmethod
    def validate_name(cls, name: str) -> str:
        """Reject zone names containing dashes or spaces, since dashes
        are used as the connection-id separator and spaces would break
        line tokenization.

        Args:
            name: The proposed zone name.

        Returns:
            The unchanged name, if valid.

        Raises:
            ValueError: If the name contains a dash or a space.
        """

        if "-" in name or " " in name:
            raise ValueError(f"Zone name: '{name}' can not include dashes"
                             " or spaces")
        return name

    @field_validator("zone_color")
    @classmethod
    def validate_color(cls, color: str) -> str:
        """Reject zone color values containing spaces.

        Args:
            color: The proposed color value.

        Returns:
            The unchanged color, if valid.

        Raises:
            ValueError: If the color contains a space.
        """

        if color is not None and " " in color:
            raise ValueError(f"Zone color: '{color}' can not include"
                             " spaces")
        return color


class ConnectionModel(BaseModel):
    """Validated data for a single connection definition line from a
    map file, ready to be handed to ``Map.add_connection``.
    """

    zone1: str
    zone2: str
    max_link_capacity: int = Field(default=1, ge=1)

    @field_validator("zone1", "zone2")
    @classmethod
    def validate_zone_name(cls, zone: str) -> str:
        """Reject connection endpoint names containing dashes or
        spaces, for the same reasons as ``ZoneModel.validate_name``.

        Args:
            zone: The proposed endpoint zone name.

        Returns:
            The unchanged name, if valid.

        Raises:
            ValueError: If the name contains a dash or a space.
        """

        if "-" in zone or " " in zone:
            raise ValueError(f"Invalid zone name: '{zone}' cannot include"
                             " dashes or spaces")
        return zone

    @model_validator(mode="after")
    def validate_zones(self) -> "ConnectionModel":
        """Reject a connection whose two endpoints are the same zone.

        Returns:
            The unchanged model, if valid.

        Raises:
            ValueError: If ``zone1`` and ``zone2`` are identical.
        """

        if self.zone1 == self.zone2:
            raise ValueError(f"Connection cannot connect zone '{self.zone1}'"
                             " to itself")

        return self

from pydantic import BaseModel, Field, field_validator, model_validator
from enum import Enum


class ZoneType(Enum):
    NORMAL = "normal"
    BLOCKED = "blocked"
    RESTRICTED = "restricted"
    PRIORITY = "priority"


class ZoneModel(BaseModel):
    name: str
    coordinates: tuple[int, int]
    zone_type: ZoneType = ZoneType.NORMAL
    zone_color: str | None = None
    max_drones: int = Field(default=1, ge=1)

    @field_validator("name")
    @classmethod
    def validate_name(cls, name: str) -> str:
        if "-" in name or " " in name:
            raise ValueError(f"Zone name: '{name}' can not include dashes"
                             " or spaces")
        return name

    @field_validator("zone_color")
    @classmethod
    def validate_color(cls, color: str) -> str:
        if color is not None and " " in color:
            raise ValueError(f"Zone color: '{color}' can not include"
                             " spaces")
        return color


class ConnectionModel(BaseModel):
    zone1: str
    zone2: str
    max_link_capacity: int = Field(default=1, ge=1)

    @field_validator("zone1", "zone2")
    @classmethod
    def validate_zone_name(cls, zone: str) -> str:
        if "-" in zone or " " in zone:
            raise ValueError(f"Invalid zone name: '{zone}' cannot include"
                             " dashes or spaces")
        return zone

    @model_validator(mode="after")
    def validate_zones(self) -> "ConnectionModel":
        if self.zone1 == self.zone2:
            raise ValueError(f"Connection cannot connect zone '{self.zone1}'"
                             " to itself")

        return self

from typing import Any


class FileError(Exception):
    pass


def parse_zone_metadata(line: str) -> dict[str, Any]:
    metadata: dict[str, Any] = {}
    valid_keys: set[str] = {"zone", "color", "max_drones"}
    valid_types: set[str] = {"normal", "blocked", "restricted", "priority"}
    try:
        raw_metadata: str = get_metadata(line)[1:-1]
    except FileError as e:
        raise FileError(e)

    meta_parts: list[str] = raw_metadata.split()
    for part in meta_parts:
        if "=" not in part:
            raise FileError("Invalid format for metadata. Metadata should"
                            " be provided with key=value pairs, "
                            f"for example color=grey, got {part}")

        meta_part: list[str] = part.split("=")
        if len(meta_part) != 2:
            raise FileError(f"Invalid key=value pair: '{part}'")

        key, value = meta_part[0], meta_part[1]
        if not key or not value:
            raise FileError(f"Invalid key=value pair: '{part}'")
        if key not in valid_keys:
            raise FileError("Invalid key provided for metadata. \n"
                            f"Valid keys are: {valid_keys}")

        if key == "zone" and value not in valid_types:
            raise FileError("Invalid zone_type provided in "
                            f"metadata segment '{part}'"
                            f"Available types are: {valid_types}")

        if key == "max_drones":
            if not value.isdigit():
                raise FileError(f"Invalid max_drones value: '{value}'."
                                "Must be a positive integer.")

            metadata[key] = int(value)
        elif key == "zone":
            metadata["zone_type"] = value
        elif key == "color":
            metadata["zone_color"] = value

    return metadata


def get_metadata(line: str) -> str:
    metadata_format: str = ("Metadata should be in the format"
                            " [key=value key=value ...]")

    i: int = 0
    raw_metadata: str = ""
    while i < len(line) and line[i] != "[":
        i += 1

    if i < len(line) and line[i] == "[":
        while i < len(line):
            raw_metadata += line[i]
            i += 1

    if not raw_metadata:
        return ""

    if raw_metadata[-1] != "]":
        raise FileError(f"{metadata_format}\n Got: {raw_metadata}")

    if "[" in raw_metadata[1:-1] or "]" in raw_metadata[1:-1]:
        raise FileError(f"{metadata_format}\n Got: {raw_metadata}")

    return raw_metadata


def get_maindata(tag: str, line: str) -> str:
    i: int = 0
    raw_maindata: str = ""
    main_data_parts: list[str] = []

    while i < len(line) and line[i] not in "[]":
        raw_maindata += line[i]
        i += 1

    main_data_parts = raw_maindata.split()
    print(main_data_parts)

    if tag == "zone":
        if not raw_maindata or len(main_data_parts) != 4:
            raise FileError("Zone definition is incomplete.\n"
                            f"Expected: hub_tag: <name> <x> <y> [metadata]"
                            f"\nGot: {line}")

    if tag == "connection":
        if not raw_maindata or len(main_data_parts) != 2:
            raise FileError("Connection definition is incomplete.\n"
                            f"Expected: connection: <name1> <name2> [metadata]"
                            f"\nGot: {line}")

    return raw_maindata


if __name__ == "__main__":
    try:
        print(get_maindata("zone", "hub: roof1 3 4 [zone=restricted color=red]"))
        print(get_metadata("hub: roof1 3 4 "))
        print()
        print(get_maindata("connection", "connection: corridorA-tunnelB [max_link_capacity=2][more stuff]"))
        print(get_metadata("connection: corridorA-tunnelB [max_link_capacity=2]"))
        print()
        print(parse_zone_metadata("hub: roof1 3 4 [zone=restricted color=red]"))
    except FileError as e:
        print(f"{type(e).__name__}: {e}")

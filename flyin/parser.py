import sys
from pydantic import ValidationError
from .map import Map, MapError
from .validation_models import ZoneModel, ConnectionModel
from typing import Any


class ParserError(Exception):
    pass


class FileError(Exception):
    pass


class Parser:
    usage: str = ("Usage: make run "
                  "[optional_flags]\n"
                  "or: make run-map MAP=<file_path.txt> "
                  "[optional_flags]\n"
                  "or: python3 -m flyin <file_path.txt> "
                  "[optional_flags]\n")

    @classmethod
    def get_metadata(cls, line: str) -> str:
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
            raise FileError(f"{metadata_format}.\n Got: {raw_metadata}")

        if "[" in raw_metadata[1:-1] or "]" in raw_metadata[1:-1]:
            raise FileError(f"{metadata_format}.\n Got: {raw_metadata}")

        return raw_metadata

    @classmethod
    def get_maindata(cls, tag: str, line: str) -> str:
        i: int = 0
        raw_maindata: str = ""
        main_data_parts: list[str] = []

        while i < len(line) and line[i] not in "[]":
            raw_maindata += line[i]
            i += 1

        main_data_parts = raw_maindata.split()

        if tag == "zone":
            if not raw_maindata or len(main_data_parts) != 4:
                raise FileError("Zone definition is invalid.\n"
                                f"Expected: hub_tag: <name> <x> <y> [metadata]"
                                f"\nGot: {line}")

        if tag == "connection":
            if not raw_maindata or len(main_data_parts) != 2:
                raise FileError("Connection definition is invalid.\n"
                                f"Expected: connection: <name1>-<name2>"
                                " [metadata]"
                                f"\nGot: {line}")

        return raw_maindata

    @classmethod
    def parse_zone_metadata(cls, line: str) -> dict[str, Any]:
        metadata: dict[str, Any] = {}
        valid_keys: set[str] = {"zone", "color", "max_drones"}
        valid_types: set[str] = {"normal", "blocked", "restricted", "priority"}

        raw_metadata: str = cls.get_metadata(line)[1:-1]

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
                raise FileError("Invalid key provided for metadata.\n"
                                f"Valid keys are: {valid_keys}")

            if key == "zone" and value not in valid_types:
                raise FileError("Invalid zone_type provided in "
                                f"metadata segment '{part}'"
                                f"Available types are: {valid_types}")

            if key == "max_drones":
                if not value.isdigit():
                    raise FileError(f"Invalid max_drones value: '{value}'."
                                    "Must be a positive integer.")
                elif key in metadata:
                    raise FileError(f"Duplicate key found in metadata {key}")

                metadata[key] = int(value)
            elif key == "zone":
                if "zone_type" in metadata:
                    raise FileError(f"Duplicate key found in metadata {key}")
                metadata["zone_type"] = value
            elif key == "color":
                if "zone_color" in metadata:
                    raise FileError(f"Duplicate key found in metadata {key}")
                metadata["zone_color"] = value

        return metadata

    @classmethod
    def parse_zone_maindata(cls, line: str) -> dict[str, Any]:
        maindata: dict[str, Any] = {}
        valid_hub_tags: set[str] = {"hub:", "start_hub:", "end_hub:"}
        raw_maindata: str = cls.get_maindata("zone", line)

        main_parts: list[str] = raw_maindata.split()
        if main_parts[0] not in valid_hub_tags:
            raise FileError("Invalid hub_tag provided in zone definition."
                            f"\nGot: {main_parts[0]}"
                            f"\nValid tags are: {valid_hub_tags}")

        try:
            x: int = int(main_parts[2])
            y: int = int(main_parts[3])
        except ValueError:
            raise FileError("Invalid coordinates provided in zone definition."
                            f"\nGot: {main_parts[2]} and {main_parts[3]}\n"
                            "Expected two int values")

        maindata["name"] = main_parts[1]
        maindata["coordinates"] = x, y

        return maindata

    @classmethod
    def parse_connection_maindata(cls, line: str) -> dict[str, Any]:
        maindata: dict[str, Any] = {}
        raw_maindata: str = cls.get_maindata("connection", line)

        main_parts: list[str] = raw_maindata.split()
        if main_parts[0] != "connection:":
            raise FileError("Invalid connection_tag in connection definiton."
                            f"\nGot: {main_parts[0]} Expected: 'connection:'")

        if "-" not in main_parts[1]:
            raise FileError("Invalid connection defition."
                            f"\nGot: {main_parts[1]}"
                            "\nExpected: <name1>-<name2>")
        else:
            zone_names: list[str] = main_parts[1].split("-", 1)

            maindata["zone1"] = zone_names[0]
            maindata["zone2"] = zone_names[1]

        return maindata

    @classmethod
    def parse_connection_metadata(cls, line: str) -> dict[str, Any]:
        metadata: dict[str, Any] = {}
        raw_metadata: str = cls.get_metadata(line)[1:-1]

        metaparts: list[str] = raw_metadata.split()

        for part in metaparts:
            if "=" not in part:
                raise FileError("Invalid format for metadata. Metadata should"
                                " be provided with key=value pairs, "
                                f"got {part}")

            meta_part: list[str] = part.split("=")
            if len(meta_part) != 2:
                raise FileError(f"Invalid key=value pair: '{part}'")

            key, value = meta_part[0], meta_part[1]

            if key != "max_link_capacity":
                raise FileError("Invalid key provided for metadata.\n"
                                "Valid keys are: 'max_link_capacity'")
            else:
                if key in metadata:
                    raise FileError(f"Duplicate key found in metadata {key}")

                if not value.isdigit():
                    raise FileError(f"Invalid max_link_capacity value: {value}"
                                    "\nMust be a positive integer.")

                metadata["max_link_capacity"] = value

        return metadata

    @classmethod
    def parse(cls) -> tuple[dict[str, bool], Map]:

        args: list[str] = sys.argv[1:]
        map_path: str | None = None
        count_files: int = 0
        valid_flags: set[str] = {"--no-gui"}

        if len(args) == 0:
            raise ParserError(f"No args provided.\n{cls.usage}"
                              f"optional_flags include {valid_flags}")

        flags: dict[str, bool] = {}

        for arg in args:
            if arg.endswith(".txt"):
                map_path = arg
                count_files += 1
            elif arg in valid_flags:
                flags[arg] = True
            else:
                raise ParserError(f"Invalid argument provided {arg}\n"
                                  f"{cls.usage}"
                                  f"optional_flags include {valid_flags}")

        if count_files == 0:
            raise ParserError(f"No map file provided.\n {cls.usage}")
        if count_files > 1:
            raise ParserError("Only 1 map file must be provided per use.\n"
                              f"{cls.usage}")
        if "--no-gui" not in flags:
            flags["--no-gui"] = True

        return (flags, cls.parse_map(map_path))

    @classmethod
    def parse_map(cls, file: str) -> Map:
        line_number: int = 0
        parsed_map: Map | None = None
        max_drones: int = 0

        try:
            with open(file, "r") as f:
                for raw_line in f:
                    line_number += 1
                    line = raw_line.split("#", 1)[0].strip()

                    if not line:
                        continue

                    parts = line.split()

                    if parsed_map is None:
                        if len(parts) != 2 or parts[0] != "nb_drones:":
                            raise FileError("First line of file should be:\n"
                                            "nb_drones: <positive_int> got "
                                            f"{' '.join(parts)}")

                        try:
                            parsed_map = Map(parts[1].strip())
                            max_drones = parsed_map.get_nb_drones()
                        except MapError as e:
                            raise FileError(e)
                    else:

                        if parts[0] in {"start_hub:", "end_hub:", "hub:"}:
                            maindata = cls.parse_zone_maindata(line)
                            metadata = cls.parse_zone_metadata(line)

                            if (parts[0] == "start_hub:" or
                                    parts[0] == "end_hub:"):
                                metadata["max_drones"] = max_drones

                            zone: ZoneModel = ZoneModel(**maindata, **metadata)

                            if parts[0] == "hub:":
                                parsed_map.add_zone(zone)

                            elif (parts[0] == "start_hub:" and
                                  parsed_map.start_hub):
                                raise FileError("Multiple start_hub"
                                                " found in file")
                            
                            elif parts[0] == "start_hub:":
                                parsed_map.add_start_hub(zone)

                            elif (parts[0] == "end_hub:" and
                                  parsed_map.end_hub):
                                raise FileError("Multiple end_hub"
                                                " found in file")
                            
                            elif parts[0] == "end_hub:":
                                parsed_map.add_end_hub(zone)

                        elif parts[0] == "connection:":
                            maindata = cls.parse_connection_maindata(line)
                            metadata = cls.parse_connection_metadata(line)

                            connect: ConnectionModel = (
                                ConnectionModel(**maindata, **metadata)
                            )

                            parsed_map.add_connection(connect)

                        else:
                            raise FileError("Invalid line found in file: "
                                            f"{line}")

        except (FileError, ValidationError, MapError) as e:
            raise ParserError(f"{type(e).__name__}: "
                              f" \nLine {line_number} -"
                              f" '{line.strip()}': {e}")
        except FileNotFoundError as e:
            raise ParserError(f"{type(e).__name__}: \n{e}")

        return parsed_map

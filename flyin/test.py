def get_metadata(line: str) -> str:
    metadata_format: str = ("Metadata should be in the format"
                            " [key=value key=value ...]")

    i: int = 0
    raw_metadata: str = ""
    while i < len(line) and line[i] != "[":
        i += 1

    if i < len(line) and line[i] == "[":
        while i < len(line) and line[i] != "]":
            raw_metadata += line[i]
            i += 1

        if i < len(line) and line[i] == "]":
            raw_metadata += line[i]

    if not raw_metadata or raw_metadata[-1] != "]":
        raise ValueError(f"{metadata_format} got {raw_metadata}")

    if "[" in raw_metadata[1:-1] or "]" in raw_metadata[1:-1]:
        raise ValueError(f"{metadata_format} got {raw_metadata}")

    return raw_metadata[1:-1]


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
            raise ValueError("Zone definition is incomplete.\n"
                             f"Expected: hub_tag: <name> <x> <y> [metadata]"
                             f"\nGot: {line}")
        
    if tag == "connection":
        if not raw_maindata or len(main_data_parts) != 2:
            raise ValueError("Connection definition is incomplete.\n"
                             f"Expected: connection: <name1> <name2> [metadata]"
                             f"\nGot: {line}")
        
    return raw_maindata


if __name__ == "__main__":
    try:
        print(get_maindata("zone", "hub: roof1 3 4 [zone=restricted color=red]"))
        print(get_metadata("hub: roof1 3 4 [zone=restricted color=red]"))
        print()
        print(get_maindata("connection", "connection: corridorA-tunnelB [max_link_capacity=2]"))
        print(get_metadata("connection: corridorA-tunnelB [max_link_capacity=2]"))
    except ValueError as e:
        print(e)

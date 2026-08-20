from .map import Map
from .parser import Parser, ParserError


def main() -> None:
    print("--------Testing program----------")
    map: Map | None = None
    flags: dict[str, bool] = {}

    try:
        flags, map = Parser.parse()
    except ParserError as e:
        print(e)

    if map:
        print("Showing zones\n")
        map.show_zones()
        print("=====================================")
        print("Showing connections\n")
        map.show_connections()
        print("=====================================")


if __name__ == "__main__":
    main()

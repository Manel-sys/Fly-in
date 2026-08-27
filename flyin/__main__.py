from .map import Map
from .parser import Parser, ParserError
from .solver import Solver


def main() -> None:
    print("--------Testing program----------")
    map: Map | None = None
    flags: dict[str, bool] = {}

    try:
        flags, map = Parser.parse()
    except ParserError as e:
        print(f"Error while parsing: {e}")

    if map:
        print("Showing zones\n")
        map.show_zones()
        print("=====================================")
        print("Showing connections\n")
        map.show_connections()
        print("=====================================")
        print("\nCHECKING SOLVABILITY AND SHORTEST PATH\n")
        solver: Solver = Solver(map)
        distances, previous = solver.dijkstra()
        path = solver.get_path(previous)
        print(path)


if __name__ == "__main__":
    main()

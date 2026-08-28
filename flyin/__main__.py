from .map import Map
from .parser import Parser, ParserError
from .solver import Solver
from .scheduler import ReservationTable


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
        distances, previous = solver.dijkstra(map.start_hub)
        path = solver.get_path(previous, map.start_hub, map.end_hub)
        print("Shortest Path from start to end")
        print(path)
        print("Distances")
        print(distances)
        print("Zone parents")
        print(previous)
        print("\n\n\n")
        print("Testing A*")
        reservations: ReservationTable = ReservationTable(map)
        path_astar = solver.astar_path(map.start_hub, 0, reservations,
                                       distances, 50)

        print(path_astar)


if __name__ == "__main__":
    main()

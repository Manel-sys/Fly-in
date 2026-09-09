from importlib import import_module
from importlib import metadata


def check_package(name: str, description: str) -> bool:
    try:
        import_module(name)
        version = metadata.version(name)
        print(f"[OK] {name} ({version}) - {description} ready")
        return True
    except (ImportError, metadata.PackageNotFoundError):
        print(f"[MISSING] {name} - {description} not ready")
        return False


print("Checking dependencies:")
dependencies = [
                check_package("pydantic", "Data validation package"),
                check_package("pygame", "Vizualization library"),
                ]

if not all(dependencies):
    print("Missing dependencies found!\n")
    print("Exiting now...")
    exit()


from .map import Map # noqa
from .parser import Parser, ParserError # noqa
from .solver import Solver # noqa
from .reservation_table import ReservationTable # noqa
from .scheduler import SchedulerError, Scheduler # noqa
from .drone import Drone # noqa


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

        print("\nTesting Scheduler!!!\n")

        drones = Drone.generate_drone_fleet(map)
        try:
            scheduler = Scheduler(map, 50, drones)
            paths = scheduler.schedule_all()
        except SchedulerError as e:
            print(f"{type(e).__name__}: {e}")

        makespan: int = 0
        for id in paths:
            if makespan < paths[id][-1][1]:
                makespan = paths[id][-1][1]
            print(f"D{id} path: {paths[id]}\n")

        print(f"Makespan = {makespan}")


if __name__ == "__main__":
    main()

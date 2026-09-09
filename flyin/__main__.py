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
from .simulation import Simulation # noqa
from .banner import BANNER # noqa


def main() -> None:

    print(BANNER)
    map: Map | None = None
    flags: dict[str, bool] = {}

    try:
        flags, map = Parser.parse()
    except ParserError as e:
        print(f"Error while parsing: {e}")
        return

    if map:
        drones: list[Drone] = Drone.generate_drone_fleet(map)
        try:
            scheduler: Scheduler = Scheduler(map, 50, drones)
            paths: dict[int, list[tuple[str, int]]] = scheduler.schedule_all()
        except SchedulerError as e:
            print(f"{type(e).__name__}: {e}")
            return
        simulation: Simulation = Simulation(map, drones, paths)
        simulation.run(flags)


if __name__ == "__main__":
    main()

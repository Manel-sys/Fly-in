from importlib import import_module
from importlib import metadata


def check_package(name: str, description: str) -> bool:
    """Check whether a required third-party package is importable.

    Prints a human-readable status line either way, so the person
    running the program can see at a glance which dependencies are
    missing before anything else runs.

    Args:
        name: The importable module/package name (e.g. ``"pygame"``).
        description: A short, human-readable description of what the
            package is used for, shown in the status line.

    Returns:
        ``True`` if the package is installed and importable, ``False``
        otherwise.
    """

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
    """Run the full Fly-In pipeline: parse, schedule, simulate, visualize.

    Prints the banner, parses the map file and CLI flags given on the
    command line, builds the drone fleet, schedules every drone's path,
    then runs the turn-by-turn CLI simulation and, unless ``--no-gui``
    was passed, opens the interactive pygame visualization afterward.

    Parsing or scheduling failures are caught, reported to the user, and
    cause the function to return early without attempting the
    simulation or visualization steps.
    """

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

        if not flags["--no-gui"]:
            from .pygame_view import PygameRenderer
            renderer: PygameRenderer = PygameRenderer(simulation, margin=100,
                                                      width=1200, height=1000)
            renderer.run()


if __name__ == "__main__":
    main()

from .drone import Drone
from .map import Map, Connection


class Simulation:
    """Steps a scheduled fleet of drones through every turn, producing
    CLI output and tracked occupancy/performance data along the way.
    """

    def __init__(self, map: Map, drones: list[Drone],
                 paths: dict[int, list[tuple[str, int]]],
                 ) -> None:
        """Set up a simulation for an already-scheduled fleet.

        Args:
            map: The map the drones are operating on.
            drones: The fleet of drones to simulate.
            paths: Each drone's scheduled path, keyed by drone id.
        """

        self.graph: Map = map
        self.drones: list[Drone] = drones
        self.paths: dict[int, list[tuple[str, int]]] = paths
        self.final_turn: int = max(path[-1][1] for path in paths.values())
        self.zone_occupancy: dict[int, dict[str, int]] = {}
        self.edge_occupancy: dict[int, dict[str, int]] = {}
        self._init_occupancy()

    def _init_occupancy(self) -> None:
        """Pre-populate zero occupancy counts for every zone and
        connection, at every turn from 0 to ``final_turn`` inclusive.

        Ensures every (turn, zone) and (turn, connection) key exists
        up front, so per-turn occupancy tallying in ``run()`` can
        simply increment existing entries rather than needing to
        lazily create them.
        """

        zones: list[str] = self.graph.get_zones()
        edges: set[str] = self.graph.get_connections()

        for t in range(self.final_turn + 1):
            self.zone_occupancy[t] = {}
            self.edge_occupancy[t] = {}
            for zone in zones:
                self.zone_occupancy[t][zone] = 0
            for edge in edges:
                self.edge_occupancy[t][edge] = 0

    def run(self, flags: dict[str, bool]) -> None:
        """Step through every turn of the simulation, printing CLI
        output and tracking occupancy and performance metrics.

        For each turn: advances every drone's state, tallies zone and
        connection occupancy for that turn, prints the turn's movement
        summary (and inline occupancy, if requested), and optionally
        prints a full per-turn occupancy breakdown. After the last
        turn, optionally prints overall performance metrics.

        Args:
            flags: The parsed CLI flags. Recognised keys used here:
                ``"--show-occupancy"``, ``"--show-score"``, and (via
                ``print_turn``) ``"--inline-occupancy"``.
        """

        metrics: EvalMetrics = EvalMetrics(self)

        for t in range(self.final_turn + 1):

            for d in self.drones:
                d.next_turn(self.paths[d.get_id()], t,
                            self.graph)

            for d in self.drones:
                conn = d.get_connection()
                if conn and d.intransit:
                    self.edge_occupancy[t][conn.get_id()] += 1

                elif conn:
                    self.zone_occupancy[t][d.get_position()] += 1
                    self.edge_occupancy[t][conn.get_id()] += 1

                else:
                    self.zone_occupancy[t][d.get_position()] += 1

            metrics.append_nbr_moves(self.print_turn(t, flags))
            if flags["--show-occupancy"]:
                metrics.print_occupancy(t)

        if flags["--show-score"]:
            metrics.show()

    def print_turn(self, turn: int, flags: dict[str, bool]) -> int:
        """Print a single line summarizing which drones moved on a
        given turn.

        Only drones that actually changed zone, or that are mid-transit
        on a restricted move, are listed; drones that are waiting are
        omitted. If ``"--inline-occupancy"`` is set, each listed
        zone/connection is annotated with its current occupancy and
        capacity.

        Args:
            turn: The turn to print a summary for.
            flags: The parsed CLI flags; only ``"--inline-occupancy"``
                is read here.

        Returns:
            The number of drones that moved (or are in transit) on
            this turn.
        """

        move_count: int = 0
        line: list[str] = []
        to_show: set[str] = set()

        for d in self.drones:
            connect: Connection | None = d.get_connection()
            if turn > self.paths[d.get_id()][-1][1]:
                continue

            if d.moved:
                line.append(f"D{d.get_id()}-<{d.get_position()}>")
                to_show.add(d.get_position())
                move_count += 1
            elif connect and d.intransit:
                line.append(f"D{d.get_id()}-<{connect.get_id()}>")
                to_show.add(connect.get_id())
                move_count += 1

        if flags["--inline-occupancy"]:
            for item in to_show:
                conn = self.graph.get_connection(item)
                if conn:
                    line.append(f"({item}, {self.edge_occupancy[turn][item]}"
                                f"/{conn.max_link_capacity})")
                else:
                    line.append(f"({item}, {self.zone_occupancy[turn][item]}"
                                f"/{self.graph.zones[item].max_drones})")

        result: str = " ".join(line)

        print(result)

        return move_count


class EvalMetrics:
    """Accumulates and reports summary performance metrics for a
    completed (or in-progress) ``Simulation`` run: makespan, moves per
    turn, average turns per drone, and total path cost, plus detailed
    per-turn occupancy printing.
    """

    def __init__(self, sim: Simulation) -> None:
        """Initialize metrics tracking for a simulation.

        Args:
            sim: The simulation to compute and report metrics for.
        """

        self.sim: Simulation = sim
        self.moves_per_turn: list[int] = []
        self.total_path_cost: int = sum(path[-1][1] for
                                        path in self.sim.paths.values())
        self.avg_turns_per_drone: int | float = self.set_avg()
        self.makespan: int = self.sim.final_turn

    def append_nbr_moves(self, move_count: int) -> None:
        """Record the number of drones that moved on the most recently
        processed turn.

        Args:
            move_count: The number of drones that moved this turn.
        """

        self.moves_per_turn.append(move_count)

    def set_avg(self) -> int | float:
        """Compute the average path length (in turns) per drone.

        Returns:
            Total path cost across all drones, divided by the number of
            drones.
        """
        return self.total_path_cost / self.sim.graph.nb_drones

    def show(self) -> None:
        """Print the full summary of performance metrics for this
        simulation run: makespan, moves per turn, average turns per
        drone, and total path cost."""

        print("\nSolution Performance Metrics:")
        print(f"+ Makespan = {self.makespan}")
        print("+ Number of drones moved per turn:")
        for t, moves in enumerate(self.moves_per_turn):
            print(f" - Turn {t} = {moves}")
        print(f"Average number of turns per drone: {self.avg_turns_per_drone}")
        print(f"Total path cost = {self.total_path_cost}")

    def print_occupancy(self, turn: int) -> None:
        """Print the full zone and connection occupancy breakdown for a
        given turn.

        Only zones/connections with nonzero occupancy are listed; if
        none are occupied at all, prints ``"None"`` for that section.

        Args:
            turn: The turn to print occupancy for.
        """

        total_zone: int = 0
        total_conn: int = 0

        total_zone = sum(self.sim.zone_occupancy[turn].values())
        total_conn = sum(self.sim.edge_occupancy[turn].values())

        if turn == 0:
            print("---------------------------------------")
        print(f"\nZone occupancy at turn {turn}:")
        for zone, count in self.sim.zone_occupancy[turn].items():
            if count > 0:
                print(f" + Zone <{zone}> = {count}")
        if total_zone == 0:
            print("None")
        print(f"\nConnection occupancy at turn {turn}:")
        for conn_id, count in self.sim.edge_occupancy[turn].items():
            if count > 0:
                print(f" + Connection <{conn_id}> = {count}")
        if total_conn == 0:
            print("None")
        print("---------------------------------------")

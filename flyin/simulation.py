from .drone import Drone
from .map import Map, Connection


class Simulation:
    def __init__(self, map: Map, drones: list[Drone],
                 paths: dict[int, list[tuple[str, int]]],
                 ) -> None:
        self.graph: Map = map
        self.drones: list[Drone] = drones
        self.paths: dict[int, list[tuple[str, int]]] = paths
        self.final_turn: int = max(path[-1][1] for path in paths.values())
        self.zone_occupancy: dict[dict[str, int]] = {}
        self.edge_occupancy: dict[dict[str, int]] = {}

    def run(self, flags: dict[str, bool]) -> None:
        metrics: EvalMetrics = EvalMetrics(self)

        for t in range(self.final_turn + 1):
            self.zone_occupancy[t] = {}
            self.edge_occupancy[t] = {}
            for d in self.drones:
                d.next_turn(self.paths[d.get_id()], t,
                            self.graph)

            for d in self.drones:
                conn = d.get_connection()
                if conn:
                    to_add = self.edge_occupancy[t].setdefault(
                                conn.get_id(), 0)
                    self.edge_occupancy[t][conn.get_id()] = to_add + 1
                elif d.moved:
                    to_add = self.zone_occupancy[t].setdefault(
                            d.get_position(), 0)
                    self.zone_occupancy[t][d.get_position()] = to_add + 1
                elif not d.moved:
                    to_add = self.zone_occupancy[t].setdefault(
                        d.get_position(), 0)
                    self.zone_occupancy[t][d.get_position()] = to_add + 1

            metrics.append_nbr_moves(self.print_turn(t, flags))
            if flags["--show-occupancy"]:
                metrics.print_occupancy(t)

        if flags["--show-score"]:
            metrics.show()

    def print_turn(self, turn: int, flags: dict[str, bool]) -> int:
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
            elif connect:
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
    def __init__(self, sim: Simulation) -> None:
        self.sim: Simulation = sim
        self.moves_per_turn: list[int] = []
        self.total_path_cost: int = sum(path[-1][1] for
                                        path in self.sim.paths.values())
        self.avg_turns_per_drone: int | float = self.set_avg()
        self.makespan: int = self.sim.final_turn

    def append_nbr_moves(self, move_count: int) -> None:
        self.moves_per_turn.append(move_count)

    def set_avg(self) -> int | float:
        return self.total_path_cost / self.sim.graph.nb_drones

    def show(self) -> None:
        print("\nSolution Performance Metrics:")
        print(f"+ Makespan = {self.makespan}")
        print("+ Number of drones moved per turn:")
        for t, moves in enumerate(self.moves_per_turn):
            print(f" - Turn {t} = {moves}")
        print(f"Average number of turns per drone: {self.avg_turns_per_drone}")
        print(f"Total path cost = {self.total_path_cost}")

    def print_occupancy(self, turn: int) -> None:
        zone_occupancy: dict[str, int] = {}
        connection_occupancy: dict[str, int] = {}
        total_zone: int = 0
        total_conn: int = 0

        for zone in self.sim.graph.get_zones():
            zone_occupancy[zone] = 0

        for connect in self.sim.graph.get_connections():
            connection_occupancy[connect] = 0

        for d in self.sim.drones:
            conn = d.get_connection()
            if conn:
                connection_occupancy[conn.get_id()] += 1
            else:
                zone_occupancy[d.get_position()] += 1

        total_zone = sum(zone_occupancy.values())
        total_conn = sum(connection_occupancy.values())

        if turn == 0:
            print("---------------------------------------")
        print(f"\nZone occupancy at turn {turn}:")
        for zone, count in zone_occupancy.items():
            if count > 0:
                print(f" + Zone <{zone}> = {count}")
        if total_zone == 0:
            print("None")
        print(f"\nConnection occupancy at turn {turn}:")
        for conn_id, count in connection_occupancy.items():
            if count > 0:
                print(f" + Connection <{conn_id}> = {count}")
        if total_conn == 0:
            print("None")
        print("---------------------------------------")

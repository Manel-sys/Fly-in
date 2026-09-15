from .map import Map
from .validation_models import ZoneType
from .priority_queue import MinPriorityQueue
from .reservation_table import ReservationTable


class SolverError(Exception):
    """Raised for invalid pathfinding requests: an unknown zone name, a
    missing start zone, or (internally) an unreachable target."""
    pass


class Solver:
    """Pathfinding over a single map: static Dijkstra distances, and
    reservation-aware, time-expanded A* search for one drone at a time.
    """

    def __init__(self, map: Map) -> None:
        """Create a solver bound to a specific map.

        Args:
            map: The map to run pathfinding queries against.
        """
        self.graph: Map = map

    def dijkstra(self, from_zone: str | None) -> tuple[dict[str, int | float],
                                                       dict[str, str | None]]:
        """Compute the static shortest-turn distance from ``from_zone``
        to every other zone, ignoring drone reservations and capacity.

        Blocked zones are never expanded into. Used both to check
        overall map solvability (from the start hub) and to precompute
        the A* heuristic (from the end hub, exploiting the fact that
        connections are bidirectional and each hop's cost depends only
        on the destination zone).

        Args:
            from_zone: The zone to compute distances from.

        Returns:
            A tuple of (distances, previous): ``distances`` maps every
            zone to its shortest-path cost from ``from_zone`` (``inf``
            if unreachable), and ``previous`` maps every zone to its
            predecessor on that shortest path (``None`` for
            unreached/starting zones).

        Raises:
            SolverError: If ``from_zone`` is ``None`` or not a zone on
                the map.
        """

        if from_zone is None:
            raise SolverError("Starting zone cannot be None")

        zones: list[str] = self.graph.get_zones()
        if from_zone not in zones:
            raise SolverError(f"Could not find Zone {from_zone}"
                              " in graph zones.")

        distances: dict[str, int | float] = {zone: float("inf")
                                             for zone in zones}

        previous: dict[str, str | None] = {zone: None for zone in zones}

        distances[from_zone] = 0

        queue: MinPriorityQueue = MinPriorityQueue([(0, from_zone)])

        while not queue.is_empty():
            current_distance, current = queue.pop()

            if current_distance > distances[current]:
                continue

            for neighbour in self.graph.connections[current]:
                if self.graph.zones[neighbour].zone_type == ZoneType.BLOCKED:
                    continue

                weight: int | float = self.graph.zones[neighbour].weight()
                new_distance: int | float = current_distance + weight

                if new_distance < distances[neighbour]:
                    distances[neighbour] = new_distance
                    previous[neighbour] = current

                    queue.push(new_distance, neighbour)

        return distances, previous

    def get_path(self, previous: dict[str, str | None],
                 from_zone: str, to_zone: str) -> list[str]:
        """Reconstruct a static (reservation-free) path from a
        ``dijkstra`` predecessor map.

        Args:
            previous: The predecessor map returned by ``dijkstra``.
            from_zone: The path's starting zone.
            to_zone: The path's destination zone.

        Returns:
            The list of zone names from ``from_zone`` to ``to_zone``,
            inclusive, in travel order.

        Raises:
            SolverError: If either zone isn't on the map, or no path
                exists between them in ``previous``.
        """

        path: list[str] = []
        zones: list[str] = self.graph.get_zones()

        if from_zone not in zones:
            raise SolverError(f"Could not find Zone {from_zone}"
                              " in graph zones.")
        elif to_zone not in zones:
            raise SolverError(f"Could not find Zone {to_zone}"
                              " in graph zones.")

        current: str | None = to_zone
        while current:
            path.append(current)

            if current == from_zone:
                return path[::-1]

            current = previous[current]

        raise SolverError(f"No path exists from {from_zone} to {to_zone}")

    def solvable(self) -> bool:
        """Check whether the map's start hub can statically reach its
        end hub at all, ignoring drone reservations and capacity.

        Returns:
            ``True`` if a path exists from the start hub to the end
            hub; ``False`` if unreachable or the end hub isn't set.
        """

        distances: dict[str, int | float] = {}
        previous: dict[str, str | None] = {}

        distances, previous = self.dijkstra(self.graph.start_hub)

        if self.graph.end_hub is not None:
            return distances[self.graph.end_hub] != float("inf")
        else:
            return False

    def astar_path(self, start_zone: str, turn: int,
                   reservations: ReservationTable,
                   heuristic: dict[str, int | float],
                   horizon: int) -> list[tuple[str, int]] | None:
        """Find the best (turn-minimal) reservation-respecting path for
        a single drone from ``start_zone`` at ``turn``, to the map's end
        hub.

        Performs time-expanded A* search over ``(zone, turn)`` states:
        at each state, either waiting one turn or moving to a neighbour
        is considered a legal successor exactly when the given
        ``reservations`` table says so (``can_wait``/``can_move``), so
        the returned path is guaranteed to be free of zone/connection
        capacity conflicts with anything already committed to
        ``reservations``. Priority-zone moves are preferred over
        equal-cost non-priority moves as a tiebreak. The search is
        bounded by ``horizon``: states at or beyond it are never
        expanded, so an infeasible or excessively congested request
        returns ``None`` rather than searching forever.

        Args:
            start_zone: The zone the drone starts at.
            turn: The turn the drone starts its search from.
            reservations: The current reservation table to search
                against; not mutated by this method.
            heuristic: Precomputed static shortest-turn distance from
                every zone to the end hub (from ``dijkstra``, run from
                the end hub), used as the A* lower-bound estimate.
            horizon: The maximum turn any explored state may reach.

        Returns:
            The best (zone, turn) path found, from the start state to
            the end hub, or ``None`` if no path exists within the
            horizon given the current reservations.
        """

        start_state: tuple[str, int] = (start_zone, turn)
        queue: MinPriorityQueue = MinPriorityQueue([(heuristic[start_zone],
                                                     (0, start_state))])

        g_score: dict[tuple[str, int], int] = {start_state: turn}
        previous: dict[tuple[str, int],
                       tuple[str, int] | None] = {start_state: None}
        closed: set[tuple[str, int]] = set()

        while not queue.is_empty():
            _, (_, current) = queue.pop()
            zone, t = current

            if current in closed:
                continue
            closed.add(current)

            if zone == self.graph.end_hub:
                return self._reconstruct(previous, current)

            if t >= horizon:
                continue

            if reservations.can_wait(t, zone):
                self._try_relax(current, (zone, t + 1),
                                1, g_score, previous, heuristic,
                                queue, closed)

            for zone2 in self.graph.connections[zone]:
                ok, arrival = reservations.can_move(t, zone, zone2)
                if ok:
                    cost: int = arrival - t
                    neighbour: tuple[str, int] = (zone2, arrival)

                    self._try_relax(current, neighbour, cost, g_score,
                                    previous, heuristic, queue, closed)

        return None

    def _try_relax(self, current: tuple[str, int],
                   neighbour: tuple[str, int],
                   cost: int, g_score: dict[tuple[str, int], int],
                   previous: dict[tuple[str, int], tuple[str, int] | None],
                   heuristic: dict[str, int | float],
                   queue: MinPriorityQueue, closed: set[tuple[str, int]]
                   ) -> None:
        """Relax a single A* successor: if this route to ``neighbour``
        is better than any known so far, record it and push it onto the
        open set.

        No-ops if ``neighbour`` is already closed, or if the newly
        computed cost isn't an improvement over ``neighbour``'s
        previously-known best cost. Priority-zone neighbours get a
        small tiebreak advantage in the open set, so among equal-cost
        candidates they are explored first.

        Args:
            current: The state being expanded.
            neighbour: The candidate successor state.
            cost: The turn cost of moving from ``current`` to
                ``neighbour``.
            g_score: The best known cost-so-far per state; updated
                in place.
            previous: The predecessor map used for path reconstruction;
                updated in place.
            heuristic: Precomputed static distance-to-goal per zone.
            queue: The A* open set; pushed to if this is an improving
                route.
            closed: The set of already-finalized states.
        """

        if neighbour in closed:
            return

        zone_type: ZoneType = self.graph.zones[neighbour[0]].zone_type
        new_g_score: int = g_score[current] + cost

        if new_g_score < g_score.get(neighbour, float("inf")):
            g_score[neighbour] = new_g_score
            previous[neighbour] = current

            f = new_g_score + heuristic[neighbour[0]]
            if zone_type == ZoneType.PRIORITY:
                penalty: int = 0
            else:
                penalty = 1

            queue.push(f, (penalty, neighbour))

    def _reconstruct(self,
                     previous: dict[tuple[str, int], tuple[str, int] | None],
                     end: tuple[str, int],
                     ) -> list[tuple[str, int]]:
        """Walk an A* predecessor map backward from a goal state to
        rebuild the full path.

        Args:
            previous: The predecessor map built during A* search.
            end: The goal state to reconstruct the path to.

        Returns:
            The full (zone, turn) path from the start state to ``end``,
            in travel order.
        """

        path: list[tuple[str, int]] = []
        current: tuple[str, int] | None = end
        while current is not None:
            path.append(current)
            current = previous[current]

        return path[::-1]

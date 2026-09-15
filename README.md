*This project has been created as part of the 42 curriculum by manferre.*

# Fly-In

## Description

**Fly-In** is a multi-drone pathfinding and scheduling simulator. Given a
map made up of zones and the connections between them, and a fleet of
drones all starting at the same hub, the goal is to move every drone from
the **start hub** to the **end hub** in the fewest possible simulation
turns, while respecting per-zone occupancy limits, per-connection
capacity limits, and the different movement costs associated with
different zone types (`normal`, `priority`, `restricted`, `blocked`).

Concretely, the project:

- Parses a custom, human-readable text format describing a map (zones,
  connections, colors, capacities, and the number of drones to route).
- Schedules a collision-free, capacity-respecting path for every drone
  using a **reservation-table-based, time-expanded A\*** search, run
  sequentially per drone (prioritized planning).
- Replays the resulting schedule turn by turn on the terminal, with
  optional per-turn occupancy reporting and summary performance metrics
  (makespan, moves per turn, average path length).
- Optionally opens an interactive **pygame** visualization of the same
  schedule, with animated drone sprites, colored zones/connections, and
  both continuous auto-play and manual whole-turn stepping.

The project is written entirely in Python, is fully typed and checked
under `mypy --strict` (see `pyproject.toml`), and validates all map-file
input through [pydantic](https://docs.pydantic.dev/) models before any
of it reaches the scheduler.

## Instructions

### Requirements

- Python >= 3.10 (the codebase itself targets 3.12-style syntax, such as
  `X | None` unions, throughout).
- [`uv`](https://docs.astral.sh/uv/) — used to manage the virtual
  environment and dependencies; the `Makefile`'s `install` target will
  install it automatically if it isn't already present.
- [`pydantic`](https://pypi.org/project/pydantic/) — used to validate
  every zone and connection parsed from a map file.
- [`pygame`](https://pypi.org/project/pygame/) — required for the
  graphical visualization; the program still runs fully in `--no-gui`
  mode.

Dev-only dependencies (`flake8`, `mypy`, `build`) are declared separately
and are only needed for linting/packaging, not for running the
simulator itself.

### Installation

```bash
make install
```

This installs `uv` if needed, then syncs the project's virtual
environment and dependencies from `pyproject.toml`.

If you'd rather not use `uv`, a plain `pip` install works too:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Running the project

```bash
make run ARGS="[flags]"
```

Runs the simulator against the default map (`maps/default.txt`). To use
a different map:

```bash
make run-map MAP=<path_to_map_file.txt> ARGS="[flags]"
```

Or, directly with Python (inside an activated environment):

```bash
python3 -m flyin <path_to_map_file.txt> [flags]
```

### Other Makefile targets

| Target | Effect |
|---|---|
| `make install` | Install `uv` (if needed) and sync all dependencies. |
| `make run ARGS="..."` | Run the simulator against the default map. |
| `make run-map MAP=<path> ARGS="..."` | Run the simulator against a specific map. |
| `make debug MAP=<path> ARGS="..."` | Run the simulator under `pdb` for step-through debugging. |
| `make lint` | Run `flake8` and `mypy` (non-strict, with a few explicit checks enabled). |
| `make lint-strict` | Run `flake8` and `mypy --strict`. |
| `make build` | Build the distributable package via `python -m build`. |
| `make clean` | Remove `__pycache__`, `.mypy_cache`, and compiled `.pyc` files. |

### Available flags (`ARGS`)

| Flag | Effect |
|---|---|
| `--no-gui` | Skip the pygame visualization; run the CLI simulation only. |
| `--show-score` | Print a summary of performance metrics (makespan, moves per turn, average turns per drone, total path cost) once the simulation finishes. |
| `--show-occupancy` | Print a full zone/connection occupancy breakdown after every turn. |
| `--inline-occupancy` | Annotate each drone's movement line with the occupancy/capacity of the zone or connection it just moved into. |

### Map file format

A map file describes the network of zones a drone fleet operates on:

```
nb_drones: 5
start_hub: hub 0 0 [color=green]
end_hub: goal 10 10 [color=yellow]
hub: roof1 3 4 [zone=restricted color=red]
hub: roof2 6 2 [zone=normal color=blue]
hub: corridorA 4 3 [zone=priority color=green max_drones=2]
connection: hub-roof1
connection: corridorA-tunnelB [max_link_capacity=2]
```

- `nb_drones:` must be the first non-comment line.
- Zones are declared with `hub:`, `start_hub:`, or `end_hub:`, followed
  by a name, x and y integer coordinates, and optional `[key=value]`
  metadata (`zone`, `color`, `max_drones`).
- Connections are declared with `connection: <name1>-<name2>`, with
  optional `[max_link_capacity=N]` metadata.
- `#` starts a comment; blank lines are ignored.

Sample maps are provided under `maps/`. Invalid or unsolvable maps are
rejected with a descriptive error before any scheduling is attempted.

### Controls (pygame visualization)

| Key | Effect |
|---|---|
| `Space` | Toggle between continuous auto-play and manual mode. |
| `→` | Step forward one turn (manual mode only). |
| `←` | Step backward one turn (manual mode only). |
| `Q` / window close | Quit. |

### Development tooling

The project is checked with `flake8` and `mypy` (in `--strict` mode, via
`make lint-strict`, or with a slightly relaxed rule set via `make lint`).
Both are declared as dev dependencies in `pyproject.toml` and installed
automatically by `make install`.

## Algorithm choices and implementation strategy

### Parsing and validation

The map file is parsed by a hand-written, line-oriented parser
(`parser.py`) into `pydantic` models (`ZoneModel`, `ConnectionModel`),
which validate structural constraints (no dashes/spaces in names, valid
zone types, positive capacities, no self-loop connections) before the
data is handed to `Map` to build the actual graph (`map.py`). Keeping
validation in pydantic models, separate from the graph itself, means the
graph's own invariants (no duplicate zones, no duplicate coordinates, no
connections to undefined zones) only ever need to be checked once, at
insertion time.

### Static solvability check

Before scheduling begins, a plain Dijkstra pass (`Solver.dijkstra`,
`solver.py`) checks that the end hub is statically reachable from the
start hub at all — ignoring drone reservations and capacity entirely.
This is a cheap, fast sanity check that rejects genuinely impossible maps
(e.g. the end hub is isolated behind only `blocked` zones) immediately,
before any per-drone search is attempted.

### Reservation-table-based multi-drone scheduling

The core scheduling problem is a form of **cooperative pathfinding**:
many drones share a single map, and their paths must not violate zone
capacity (`max_drones`) or connection capacity (`max_link_capacity`) at
any shared turn. This project solves it with **prioritized planning**:

1. A `ReservationTable` (`reservation_table.py`) tracks, per `(zone,
   turn)` and per `(connection, turn)`, how many drones currently occupy
   that slot, and exposes atomic `can_move`/`commit_move` and
   `can_wait`/`commit_wait` operations. A restricted-zone move correctly
   reserves the connection across *every* turn of its multi-turn transit
   and only reserves the destination zone at the true arrival turn — so
   a drone can never be "interrupted" mid-transit, matching the subject's
   movement rules exactly.
2. `Scheduler` (`scheduler.py`) plans one drone at a time, in a fixed
   order: it runs A* for a drone against the *current* state of the
   shared reservation table, then commits the resulting path before
   planning the next drone. This means later drones automatically see —
   and route around, or wait for — the reservations earlier drones have
   already made.

This design is deliberately **not** globally makespan-optimal: earlier
drones always take the individually-cheapest path available to them,
even if a different choice would have produced a better *overall*
finishing time for the whole fleet. True global optimality (e.g. via
Conflict-Based Search) requires reasoning about combinations of paths
across all agents jointly, which is exponentially more expensive.
Prioritized planning was chosen specifically because it stays
**polynomial per drone** (each drone's search is a single A* run) and
therefore **scales linearly with fleet size** — a deliberate
efficiency/optimality trade-off, made explicit here rather than left
implicit.

### Time-expanded A\*

Since two drones occupying the same zone at the same turn is a real
constraint, plain Dijkstra over zones alone can't express *when* a move
is legal. `Solver.astar_path` instead searches over `(zone, turn)`
states — a graph "unrolled" across time:

- **g(state)** is the number of turns elapsed so far.
- **h(state)** is the precomputed *static* Dijkstra distance from that
  zone to the end hub (run once, from the end hub, before any drone is
  scheduled, and reused by every drone's search) — an admissible
  heuristic, since reservations can only ever force *extra* waiting, not
  fewer turns, relative to the unconstrained map.
- Successors of a state are generated purely by asking the reservation
  table what's currently legal (`can_wait`, `can_move`); a restricted
  move jumps directly from the departure state to the arrival state two
  turns later, with no intermediate "mid-transit" search state, since a
  drone cannot be redirected while in transit.
- Priority-zone moves are preferred over equal-cost normal moves via a
  small tiebreak value carried alongside each queue entry, since the
  subject requires priority zones to be preferred in pathfinding even
  though they cost the same single turn as a normal zone.

The priority queue itself (`priority_queue.py`) is a small, from-scratch
binary min-heap, generic over any `(priority, payload)` shape — reused
identically by both the static Dijkstra pass and the time-expanded A\*
search.

### Complexity

For a map with `V` zones, `E` connections, and a search horizon of `H`
turns, one drone's A* search runs in roughly `O(E · H · log(V · H))` —
the direct time-expanded analogue of ordinary Dijkstra/A*'s `O(E log
V)`, with the extra `H` factor being the cost of reasoning about time.
Scheduling `N` drones sequentially is therefore `O(N · E · H · log(V ·
H))` — **linear in the number of drones**, which is what keeps the
approach practical for a large fleet, at the cost of not guaranteeing a
globally optimal makespan.

### Turn-by-turn simulation and reporting

Once every drone has a scheduled path, `Simulation` (`simulation.py`)
replays the whole fleet turn by turn: `Drone.next_turn` re-scans a
drone's path each call to determine its position, whether it just
moved, and whether it's currently mid-transit on a restricted move — a
deliberately **stateless** design (no manually-tracked path index) that
trades a small, negligible amount of recomputation for simpler,
harder-to-desynchronize state. Per-turn zone/connection occupancy is
tallied and can be reported in detail (`--show-occupancy`) or inline
next to each drone's movement (`--inline-occupancy`), and overall
performance metrics are available via `--show-score`.

## Visual representation

The project offers two layers of visual feedback, per the subject's
requirement for either or both terminal and graphical output:

### Terminal output

Every turn, the CLI prints exactly which drones moved (and where), with
waiting drones intentionally omitted to keep the output focused on
what's actually changing. `--show-occupancy` additionally prints a full
per-turn breakdown of zone and connection occupancy; `--inline-occupancy`
folds that same information directly into each movement line instead.

### Graphical visualization (pygame)

`PygameRenderer` (`pygame_view.py`) renders the same schedule
interactively:

- **Zones and connections** are drawn once, precomputed at construction
  time from the map's own coordinates (auto-scaled and centered to fit
  the window regardless of the map's coordinate range), and simply
  replayed every frame — so per-frame rendering cost stays proportional
  to the number of drones, not the size of the map.
- **Zone color** follows the map file's explicit `color=` metadata when
  present, falling back to a color derived from zone type (green for
  priority, red for restricted, gray shades for normal/blocked)
  otherwise — so a viewer can read zone type visually even on maps
  where the author didn't specify colors.
- **Drones** are drawn as animated sprites (idle and walking animations,
  falling back to plain circles if the sprite sheets can't be loaded),
  smoothly interpolated between turns using a continuous "fractional
  turn" value rather than snapping discretely — so a normal move glides
  across its connection over one turn, and a restricted move visibly
  takes twice as long, directly communicating the zone-type cost
  difference the subject describes.
- **Overlapping drones** (multiple drones genuinely sharing a zone at
  the same turn) are automatically fanned out into a small ring rather
  than stacking exactly on top of one another, so a cluster of drones
  stays visually distinguishable and countable.
- **Playback modes**: continuous auto-play, or manual whole-turn
  stepping (forward/backward), toggled with the space bar without
  visually jumping any drone's position — useful for pausing and closely
  inspecting a specific turn rather than only watching the schedule play
  out in real time.
- An on-screen **turn counter** and **controls reference** keep the
  current state and available interactions visible at all times.

Together, these give a viewer both a quick, glanceable read of the
overall schedule (auto-play) and a precise, inspectable view of any
individual turn (manual mode) — directly supporting the subject's
requirement that the visual representation meaningfully enhance
understanding of the simulation, not just illustrate it after the fact.

## Resources

- [Multi-agent pathfinding - Wikipedia](https://en.wikipedia.org/wiki/Multi-agent_pathfinding) - Used for understanding the conceptual difficulties of the problem and the common approaches to it
- [Dijkstra's algorithm - Wikipedia](https://en.wikipedia.org/wiki/Dijkstra%27s_algorithm) - Used for the implementation of Dijkstra's algorithm
- [A* search algorithm - Wikipedia](https://en.wikipedia.org/wiki/A*_search_algorithm) - Used for the implementation of A* search algorithm
- [Priority Queue - GeeksforGeeks](https://www.geeksforgeeks.org/dsa/priority-queue-set-1-introduction/)
- [Pygame documentation](https://www.pygame.org/docs/) - used for the
  graphical visualization.

### AI usage

An AI assistant (Claude) was used throughout this project as a design
and debugging aid, in the following ways:

- **Architecture and design discussion**: talking through the split
  between `Solver` (stateless pathfinding), `Scheduler` (multi-drone
  orchestration and commitment), and `Simulation`/`PygameRenderer`
  (playback and display), including why each layer should not depend on
  the ones above it (e.g. `Solver` has no knowledge of drones,
  `Simulation` has no knowledge of pygame).
- **Algorithm explanation and verification**: working through, step by
  step, how time-expanded A* and the reservation table interact —
  including manually traced examples with two and three drones sharing
  a restricted connection — to confirm the scheduling logic (waiting vs.
  rerouting) behaves correctly before relying on it, and clarifying the
  complexity/optimality trade-offs of prioritized planning versus a
  globally-optimal approach.
- **Debugging**: diagnosing several concrete bugs, including a swapped
  argument order in `ReservationTable`, an off-by-one in
  `Drone.next_turn`'s arrival-turn detection, a missing `_commit_path`
  call in the scheduler, a circular import between `map.py` and
  `drone.py`, and several `mypy` type errors around `Optional` pygame
  objects (`Surface | None`, `Font | None`, `Clock | None`).
  All fixes were reviewed and understood before being applied.
- **Code review and refactors**: reviewing hand-written code for
  correctness (e.g. the `MinPriorityQueue` generalization for A*'s
  richer payload shape, the pygame renderer's auto-play/manual-mode
  toggle keeping drone positions continuous across the switch) and
  discussing trade-offs between alternative implementations (e.g.
  stateless vs. indexed path-segment lookup in `Drone.next_turn` and
  `Drone.get_render_position`).
- **Documentation**: generating the docstrings across the project's
  Python modules, and this README, based on the finished code and the
  design decisions discussed during development.

The AI assistant was used as a design-discussion partner and debugging
aid rather than as a source of unreviewed code.

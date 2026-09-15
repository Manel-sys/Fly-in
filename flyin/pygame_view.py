import pygame
import math
from .simulation import Simulation
from .validation_models import ZoneType
from .banner import BANNER


NAMED_COLORS: dict[str, tuple[int, int, int]] = {
    "red": (200, 0, 0),
    "green": (0, 200, 0),
    "blue": (0, 100, 200),
    "yellow": (200, 200, 0),
    "gray": (120, 120, 120),
    "grey": (120, 120, 120),
    "black": (20, 20, 20),
    "white": (255, 255, 255),
    "orange": (200, 120, 0),
    "purple": (150, 0, 150),
    "cyan": (0, 255, 255),
}

TYPE_COLORS: dict[ZoneType, tuple[int, int, int]] = {
    ZoneType.NORMAL: (200, 200, 200),
    ZoneType.PRIORITY: (0, 200, 0),
    ZoneType.RESTRICTED: (200, 0, 0),
    ZoneType.BLOCKED: (80, 80, 80),
}


class RendererError(Exception):
    """Raised when a draw method is called before ``PygameRenderer.run()``
    has initialized pygame's screen/clock/font objects."""

    def __init__(self, msg: str = "Renderer not initialized: "
                 "call run() first") -> None:
        """Create a RendererError, optionally with a custom message.

        Args:
            msg: The error message. Defaults to a generic message
                indicating the renderer hasn't been initialized yet,
                if not given explicitly at the raise site.
        """
        super().__init__(msg)


class PygameRenderer:
    """Drives an interactive pygame window that plays back a scheduled
    ``Simulation``.

    Owns the pygame window, clock, and fonts; precomputes all static
    map geometry (zone screen positions/colors, connection line
    endpoints) once at construction so per-frame rendering only ever
    re-derives each drone's current position. Supports continuous
    auto-play and manual whole-turn stepping, toggled with the space
    bar, and falls back to plain colored circles for drones if the
    configured sprite sheets can't be loaded.
    """

    def __init__(self, simulation: Simulation, seconds_per_turn: float = 1.0,
                 fps: int = 60, width: int = 800, height: int = 600,
                 margin: int = 50,
                 drone_size: int = 30,
                 drone_idle_path: str = "assets/Idle.png",
                 drone_walk_path: str = "assets/Walk.png") -> None:
        """Configure a renderer for the given scheduled simulation.

        Precomputes the map's screen-space bounds/scale and every zone
        and connection's screen position immediately; pygame itself
        (window, clock, fonts, sprite loading) is only initialized once
        ``run()`` is called.

        Args:
            simulation: The already-scheduled simulation to play back.
            seconds_per_turn: How many real seconds one simulated turn
                takes to animate through in auto-play mode.
            fps: Target frame rate cap for the render loop.
            width: Window width in pixels.
            height: Window height in pixels.
            margin: Minimum empty space, in pixels, kept around the
                drawn map on every edge of the window.
            drone_size: Side length, in pixels, drones are scaled to
                when drawn (whether as sprites or fallback circles).
            drone_idle_path: Path to the idle-animation sprite sheet
                (a single row of equal-width frames).
            drone_walk_path: Path to the walk-animation sprite sheet
                (a single row of equal-width frames).
        """

        self.sim = simulation
        self.seconds_per_turn = seconds_per_turn
        self.fps = fps
        self.width = width
        self.height = height
        self.margin = margin

        self.drone_size = drone_size
        self.idle_sheet_path = drone_idle_path
        self.walk_sheet_path = drone_walk_path
        self.idle_frames: list[pygame.Surface] = []
        self.walk_frames: list[pygame.Surface] = []
        self.sprites_loaded: bool = False
        self.anim_frame_duration = 0.15
        self.anim_time = 0.0

        self.screen: pygame.Surface | None = None
        self.clock: pygame.time.Clock | None = None
        self.font: pygame.font.Font | None = None

        self.auto_play: bool = True
        self.elapsed: float = 0.0
        self.current_turn: int = 0

        self.min_x: float = 0.0
        self.min_y: float = 0.0
        self.scale: float = 1.0
        self.offset_x: float = 0.0
        self.offset_y: float = 0.0

        self.zone_positions: dict[str, tuple[int, int]] = {}
        self.zone_colors: dict[str, tuple[int, int, int]] = {}
        self.connection_lines: list[tuple[tuple[int, int],
                                          tuple[int, int]]] = []

        self._compute_bounds_and_scale()
        self._precompute_geometry()

    def _compute_bounds_and_scale(self) -> None:
        """Compute the map's coordinate bounds and the pixel scale/offset
        needed to fit and center it within the window.

        Picks the smaller of the width-fitting and height-fitting scale
        factors so the whole map fits without stretching, then computes
        an additional centering offset so any leftover space (when the
        map's aspect ratio doesn't match the window's) is distributed
        evenly rather than left in one corner.
        """

        zones = self.sim.graph.zones.values()
        xs = [zone.coordinates[0] for zone in zones]
        ys = [zone.coordinates[1] for zone in zones]

        self.min_x = min(xs)
        self.min_y = min(ys)
        max_x = max(xs)
        max_y = max(ys)

        span_x = max(max_x - self.min_x, 1)
        span_y = max(max_y - self.min_y, 1)

        available_width = self.width - 2 * self.margin
        available_height = self.height - 2 * self.margin

        scale_x = available_width / span_x
        scale_y = available_height / span_y

        self.scale = min(scale_x, scale_y)

        used_width = span_x * self.scale
        used_height = span_y * self.scale

        self.offset_x = self.margin + (available_width - used_width) / 2
        self.offset_y = self.margin + (available_height - used_height) / 2

    def _to_screen(self, coordinates: tuple[float, float]) -> tuple[int, int]:
        """Convert a map coordinate into a pixel position on screen.

        Args:
            coordinates: An (x, y) map-space coordinate. May be
                fractional (e.g. an interpolated drone position).

        Returns:
            The corresponding (x, y) pixel position, using the
            precomputed bounds, scale, and centering offset.
        """

        x, y = coordinates
        px = self.offset_x + int((x - self.min_x) * self.scale)
        py = self.offset_y + int((y - self.min_y) * self.scale)
        return int(px), int(py)

    def _zone_color(self, zone_color: str | None,
                    zone_type: ZoneType) -> tuple[int, int, int]:
        """Resolve the display color for a zone.

        Prefers the zone's own explicit ``color=`` setting (looked up
        in ``NAMED_COLORS``, case-insensitively) when present; falls
        back to a color derived from the zone's type otherwise, or if
        the given color name isn't recognised.

        Args:
            zone_color: The zone's explicit color name, or ``None``.
            zone_type: The zone's type, used as a fallback.

        Returns:
            An RGB tuple to draw the zone with.
        """

        if zone_color is not None:
            return (NAMED_COLORS.get(zone_color.lower(),
                                     TYPE_COLORS.get(zone_type,
                                                     (255, 255, 255))))

        return TYPE_COLORS.get(zone_type, (255, 255, 255))

    def _precompute_geometry(self) -> None:
        """Precompute every zone's screen position/color and every
        connection's screen-space line endpoints, once.

        Populates ``zone_positions``, ``zone_colors`` and
        ``connection_lines`` so per-frame drawing never needs to
        recompute static map geometry. Connections are deduplicated
        (the underlying map stores each one twice, once per direction)
        so each is only added to ``connection_lines`` once.
        """

        graph = self.sim.graph

        for name, zone in graph.zones.items():
            self.zone_positions[name] = self._to_screen(zone.coordinates)
            self.zone_colors[name] = self._zone_color(zone.zone_color,
                                                      zone.zone_type)

        drawn: set[str] = set()
        for zone1 in graph.connections:
            for zone2 in graph.connections[zone1]:
                conn = graph.connections[zone1][zone2]
                if conn.get_id() in drawn:
                    continue
                drawn.add(conn.get_id())

                start = self.zone_positions[zone1]
                end = self.zone_positions[zone2]
                self.connection_lines.append((start, end))

    def _slice_sheet(self, path: str, count: int) -> list[pygame.Surface]:
        """Load a sprite sheet and slice it into ``count`` equal-width
        frames from a single row, scaled to ``drone_size``.

        Args:
            path: Path to the sprite sheet image.
            count: Number of equal-width frames the sheet is divided
                into.

        Returns:
            The list of individual frame surfaces, in left-to-right
            order.

        Raises:
            pygame.error: If the file can't be loaded as an image.
            FileNotFoundError: If the file doesn't exist.
        """

        sheet = pygame.image.load(path).convert_alpha()
        sheet_width, sheet_height = sheet.get_size()
        frame_width = sheet_width // count
        frame_height = sheet_height

        frames = []
        for i in range(count):
            rect = pygame.Rect(i * frame_width, 0, frame_width, frame_height)
            frame = sheet.subsurface(rect).copy()
            frame = pygame.transform.scale(frame, (self.drone_size,
                                                   self.drone_size))
            frames.append(frame)

        return frames

    def _is_drone_moving(self, path: list[tuple[str, int]],
                         frac_turn: float) -> bool:
        """Determine whether a drone is mid-move (as opposed to
        waiting) at a given continuous turn value.

        Used to pick between the idle and walk animation for a drone
        each frame. A drone is considered moving if the path segment
        covering ``frac_turn`` connects two different zones.

        Args:
            path: The drone's full path.
            frac_turn: The (possibly fractional) turn being rendered.

        Returns:
            ``True`` if the drone is moving between zones at this
            instant, ``False`` if it's waiting or the turn is out of
            the path's range.
        """

        for i in range(len(path) - 1):
            zone1, t1 = path[i]
            zone2, t2 = path[i + 1]
            if t1 <= frac_turn <= t2:
                return zone1 != zone2

        return False

    def _spread_offset(self, index: int) -> tuple[int, int]:
        """Compute a small pixel offset to visually separate drones that
        share the exact same rendered position this frame.

        The first drone at a position (``index == 0``) is drawn exactly
        centered; each subsequent drone is pushed outward at an
        increasing radius and rotating angle, fanning overlapping
        drones into a small ring instead of stacking them exactly on
        top of one another.

        Args:
            index: How many other drones have already been placed at
                this same base position this frame.

        Returns:
            An (dx, dy) pixel offset to add to the drone's base
            position.
        """

        if index == 0:
            return (0, 0)

        angle = index * 2.4
        radius = 6 + index * 3
        return (int(radius * math.cos(angle)), int(radius * math.sin(angle)))

    def run(self) -> None:
        """Open the pygame window and run the visualization until the
        user quits.

        Initializes pygame, loads (or falls back gracefully from) the
        drone sprite sheets, shows the banner splash screen, then runs
        the main loop: handle input, advance the animation clock in
        auto-play mode, and redraw every frame until the window is
        closed or the quit key is pressed.
        """

        pygame.init()
        self.screen = pygame.display.set_mode((self.width, self.height))
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont(None, 28)

        try:
            self.idle_frames = self._slice_sheet(self.idle_sheet_path, 4)
            self.walk_frames = self._slice_sheet(self.walk_sheet_path, 4)
            self.sprites_loaded = True
        except (pygame.error, FileNotFoundError) as e:
            print(f"Could not load drone sprites ({e});"
                  " falling back to circles.")
            self.sprites_loaded = False

        self._show_banner_screen()

        running = True
        while running:
            dt = self.clock.tick(self.fps) / 1000.0
            running = self._handle_events()

            if self.auto_play:
                self._advance_auto(dt)

            self.anim_time += dt
            self._draw_frame()

        pygame.quit()

    def _handle_events(self) -> bool:
        """Process all pending pygame events for this frame.

        Handles window close, the quit key, the auto/manual mode
        toggle, and (only while in manual mode) the step
        forward/backward keys.

        Returns:
            ``False`` if the window should close (quit requested),
            ``True`` otherwise.
        """

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_q:
                    return False
                elif event.key == pygame.K_SPACE:
                    self._toggle_mode()

                elif not self.auto_play:
                    if event.key == pygame.K_RIGHT:
                        self._step(1)
                    elif event.key == pygame.K_LEFT:
                        self._step(-1)

        return True

    def _toggle_mode(self) -> None:
        """Switch between auto-play and manual step mode without
        visually jumping the drones' positions.

        When switching to manual mode, the current animated time is
        snapped to the nearest whole turn. When switching back to
        auto-play, the animation clock is set so playback resumes from
        exactly the turn manual mode was left on.
        """

        if self.auto_play:
            self.current_turn = min(
                                round(self.elapsed / self.seconds_per_turn),
                                self.sim.final_turn)
            self.auto_play = False
        else:
            self.elapsed = self.current_turn * self.seconds_per_turn
            self.auto_play = True

    def _step(self, delta: int) -> None:
        """Move the manual-mode turn cursor by one whole turn, clamped
        to the simulation's valid turn range.

        Args:
            delta: ``1`` to step forward, ``-1`` to step backward.
        """

        new_turn = self.current_turn + delta
        self.current_turn = max(0, min(self.sim.final_turn, new_turn))

    def _advance_auto(self, dt: float) -> None:
        """Advance the auto-play animation clock by this frame's real
        elapsed time, capped at the simulation's final turn.

        Args:
            dt: Real seconds elapsed since the previous frame.
        """

        max_elapsed = self.sim.final_turn * self.seconds_per_turn
        self.elapsed = min(self.elapsed + dt, max_elapsed)

    def _draw_frame(self) -> None:
        """Draw one complete frame: background, connections, zones,
        drones, and the on-screen overlays, then present it.

        Raises:
            RendererError: If called before ``run()`` has initialized
                the screen.
        """

        if self.screen is None:
            raise RendererError("Renderer not initialized")

        self.screen.fill((30, 30, 45))
        self._draw_connections()
        self._draw_zones()
        self._draw_drones()
        self._draw_turn_counter()
        self._draw_controls_help()

        pygame.display.flip()

    def _draw_connections(self) -> None:
        """Draw every precomputed connection line.

        Raises:
            RendererError: If called before ``run()`` has initialized
                the screen.
        """

        if self.screen is None:
            raise RendererError()

        for start, end in self.connection_lines:
            pygame.draw.line(self.screen, (100, 100, 100), start, end, 2)

    def _draw_zones(self) -> None:
        """Draw every precomputed zone marker at its screen position,
        in its resolved color.

        Raises:
            RendererError: If called before ``run()`` has initialized
                the screen.
        """

        if self.screen is None:
            raise RendererError()

        for name, pos in self.zone_positions.items():

            color = self.zone_colors[name]
            pygame.draw.circle(self.screen, color, pos, 16)

    def _draw_drones(self) -> None:
        """Draw every drone at its current interpolated (or
        whole-turn, in manual mode) position.

        Computes the shared time value driving every drone's position
        this frame, spreads out any drones sharing the exact same base
        position via ``_spread_offset``, and draws either the
        appropriate animated sprite frame (idle or walk, depending on
        whether the drone is moving) or a plain fallback circle if
        sprites failed to load.

        Raises:
            RendererError: If called before ``run()`` has initialized
                the screen.
        """

        if self.screen is None:
            raise RendererError()

        if self.auto_play:
            frac_turn = self.elapsed / self.seconds_per_turn
        else:
            frac_turn = self.current_turn

        positions_seen: dict[tuple[int, int], int] = {}

        for d in self.sim.drones:
            path = self.sim.paths[d.get_id()]
            x, y = d.get_render_position(path, frac_turn, self.sim.graph)
            base_pos = self._to_screen((x, y))

            count = positions_seen.get(base_pos, 0)
            positions_seen[base_pos] = count + 1

            dx, dy = self._spread_offset(count)
            pos = (base_pos[0] + dx, base_pos[1] + dy)

            if self.sprites_loaded:
                if self._is_drone_moving(path, frac_turn):
                    frames = self.walk_frames
                else:
                    frames = self.idle_frames

                frame_index = (int(self.anim_time / self.anim_frame_duration)
                               % len(frames))
                sprite = frames[frame_index]
                rect = sprite.get_rect(center=pos)
                self.screen.blit(sprite, rect)
            else:
                pygame.draw.circle(self.screen, (255, 255, 0), pos, 8)

    def _draw_turn_counter(self) -> None:
        """Draw the current turn and playback mode in the top-right
        corner of the window.

        Raises:
            RendererError: If called before ``run()`` has initialized
                the screen and font.
        """

        if self.font is None or self.screen is None:
            raise RendererError()

        if self.auto_play:
            frac_turn = self.elapsed / self.seconds_per_turn
        else:
            frac_turn = self.current_turn

        current = min(int(frac_turn), self.sim.final_turn)

        mode_label = "auto" if self.auto_play else "manual"
        text = f"Turn {current} / {self.sim.final_turn} ({mode_label})"
        surface = self.font.render(text, True, (255, 255, 255))

        text_rect = surface.get_rect()
        text_rect.topright = (self.width - 10, 10)

        self.screen.blit(surface, text_rect)

    def _draw_controls_help(self) -> None:
        """Draw the keyboard controls reference text along the bottom
        of the window.

        Raises:
            RendererError: If called before ``run()`` has initialized
                the screen and font.
        """

        if self.screen is None or self.font is None:
            raise RendererError()

        lines = [
            "Press SPACE to toggle auto-play / manual mode",
            "Press LEFT ARROW to step back one turn (manual mode)",
            "Press RIGHT ARROW to step forward one turn (manual mode)",
            "Press Q to exit"
                ]

        line_height = 18
        start_y = self.height - (len(lines) * line_height) - 10

        for i, line in enumerate(lines):
            surface = self.font.render(line, True, (200, 200, 200))
            text_rect = surface.get_rect()
            text_rect.midbottom = (self.width // 2,
                                   start_y + (i + 1) * line_height)
            self.screen.blit(surface, text_rect)

    def _show_banner_screen(self) -> None:
        """Show the ASCII-art banner as a blocking splash screen until
        the user presses any key (or closes the window).

        Renders every banner line with a monospace font, left-aligned
        to a single shared x position (rather than each line centered
        independently), so the picture's column alignment is preserved.

        Raises:
            RendererError: If called before ``run()`` has initialized
                the screen and clock.
        """

        if self.screen is None or self.clock is None:
            raise RendererError()

        mono_font = pygame.font.SysFont("couriernew", 16)
        lines = BANNER.strip("\n").split("\n")

        line_height = mono_font.get_linesize()
        rendered = [mono_font.render(line, True,
                                     (255, 255, 255)) for line in lines]
        max_width = max(surface.get_width() for surface in rendered)

        total_height = line_height * len(lines)
        start_x = (self.width - max_width) // 2
        start_y = (self.height - total_height) // 2

        waiting = True
        while waiting:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    raise SystemExit
                elif event.type == pygame.KEYDOWN:
                    waiting = False

            self.screen.fill((30, 30, 45))

            for i, surface in enumerate(rendered):
                self.screen.blit(surface, (start_x, start_y + i * line_height))

            hint = mono_font.render("Press any key to start", True,
                                    (150, 150, 150))
            hint_rect = hint.get_rect()
            hint_rect.midbottom = (self.width // 2, self.height - 20)
            self.screen.blit(hint, hint_rect)

            pygame.display.flip()
            self.clock.tick(30)

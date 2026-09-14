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
    def __init__(self, msg: str = "Renderer not initialized: "
                 "call run() first") -> None:
        super().__init__(msg)


class PygameRenderer:
    def __init__(self, simulation: Simulation, seconds_per_turn: float = 1.0,
                 fps: int = 60, width: int = 800, height: int = 600,
                 margin: int = 50,
                 drone_size: int = 30,
                 drone_idle_path: str = "assets/Idle.png",
                 drone_walk_path: str = "assets/Walk.png") -> None:

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
        x, y = coordinates
        px = self.offset_x + int((x - self.min_x) * self.scale)
        py = self.offset_y + int((y - self.min_y) * self.scale)
        return int(px), int(py)

    def _zone_color(self, zone_color: str | None,
                    zone_type: ZoneType) -> tuple[int, int, int]:

        if zone_color is not None:
            return (NAMED_COLORS.get(zone_color.lower(),
                                     TYPE_COLORS.get(zone_type,
                                                     (255, 255, 255))))

        return TYPE_COLORS.get(zone_type, (255, 255, 255))

    def _precompute_geometry(self) -> None:
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
        for i in range(len(path) - 1):
            zone1, t1 = path[i]
            zone2, t2 = path[i + 1]
            if t1 <= frac_turn <= t2:
                return zone1 != zone2

        return False

    def _spread_offset(self, index: int) -> tuple[int, int]:
        if index == 0:
            return (0, 0)

        angle = index * 2.4
        radius = 6 + index * 3
        return (int(radius * math.cos(angle)), int(radius * math.sin(angle)))

    def run(self) -> None:
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
        if self.auto_play:
            self.current_turn = min(
                                round(self.elapsed / self.seconds_per_turn),
                                self.sim.final_turn)
            self.auto_play = False
        else:
            self.elapsed = self.current_turn * self.seconds_per_turn
            self.auto_play = True

    def _step(self, delta: int) -> None:
        new_turn = self.current_turn + delta
        self.current_turn = max(0, min(self.sim.final_turn, new_turn))

    def _advance_auto(self, dt: float) -> None:
        max_elapsed = self.sim.final_turn * self.seconds_per_turn
        self.elapsed = min(self.elapsed + dt, max_elapsed)

    def _draw_frame(self) -> None:
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
        if self.screen is None:
            raise RendererError()

        for start, end in self.connection_lines:
            pygame.draw.line(self.screen, (100, 100, 100), start, end, 2)

    def _draw_zones(self) -> None:
        if self.screen is None:
            raise RendererError()

        for name, pos in self.zone_positions.items():

            color = self.zone_colors[name]
            pygame.draw.circle(self.screen, color, pos, 16)

    def _draw_drones(self) -> None:
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

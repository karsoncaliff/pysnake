import itertools
import json
import math
import random
import sys
from collections import deque
from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path

import pygame as pg
import pygame_menu as pgm

SETTINGS_FILE = Path("settings.json")


class Direction(Enum):
    LEFT = auto()
    RIGHT = auto()
    UP = auto()
    DOWN = auto()


HORIZONTAL_DIRS = {Direction.LEFT, Direction.RIGHT}
VERTICAL_DIRS = {Direction.UP, Direction.DOWN}

DIRECTION_OFFSETS = {
    Direction.LEFT: pg.Vector2(-1, 0),
    Direction.RIGHT: pg.Vector2(1, 0),
    Direction.UP: pg.Vector2(0, -1),
    Direction.DOWN: pg.Vector2(0, 1),
}


@dataclass
class Snake:
    direction: Direction
    body: deque[pg.Vector2]

    @property
    def head(self) -> pg.Vector2:
        return self.body[-1]

    def reverse(self) -> None:
        self.body.reverse()
        match self.direction:
            case Direction.LEFT:
                self.direction = Direction.RIGHT
            case Direction.RIGHT:
                self.direction = Direction.LEFT
            case Direction.UP:
                self.direction = Direction.DOWN
            case Direction.DOWN:
                self.direction = Direction.UP


@dataclass
class Stone:
    position: pg.Vector2
    remaining: int
    initial_remaining: int


class Game:
    SCORE_FONT = None
    SCORE_FONT_SIZE = 24
    SCORE_POSITION = (15, 15)

    MENU_TEXT_COLOR = pg.Color(148, 156, 171)
    MENU_TEXT_MUTED_COLOR = pg.Color(97, 104, 118)

    BACKGROUND_COLOR = pg.Color(18, 20, 26)
    SCORE_COLOR = pg.Color(230, 237, 243)
    WALL_COLOR = pg.Color(45, 51, 59)
    WALL_BORDER_COLOR = pg.Color(80, 88, 102)
    STONE_COLOR = pg.Color(60, 64, 72)
    STONE_ACCENT_COLOR = pg.Color(95, 101, 112)
    FOOD_COLOR = pg.Color(255, 75, 75)
    FOOD_GLOW_COLOR = pg.Color(255, 75, 75, 60)

    SNAKE_HEAD_COLOR = pg.Color(88, 166, 255)
    SNAKE_TAIL_COLOR = pg.Color(41, 116, 205)

    def __init__(self) -> None:
        pg.init()
        self._load_settings()

        init_flags = pg.FULLSCREEN if self._fullscreen else (pg.SCALED | pg.RESIZABLE)
        init_w = 0 if self._fullscreen else self._windowed_width
        init_h = 0 if self._fullscreen else self._windowed_height

        self._screen = pg.display.set_mode((init_w, init_h), init_flags)

        actual_w, actual_h = pg.display.get_window_size()
        self._width = actual_w
        self._height = actual_h
        if not self._fullscreen:
            self._windowed_width = actual_w
            self._windowed_height = actual_h

        self._cell_size = self._calc_cell_size(self._width, self._height)

        pg.display.set_caption("PySnake")
        self._clock = pg.Clock()
        self._font = pg.Font(self.SCORE_FONT, self.SCORE_FONT_SIZE)

        self._inputs: list[Direction] = []
        self._snake: Snake
        self._foods: list[pg.Vector2] = []
        self._walls: list[pg.Vector2] = []
        self._stones: list[Stone] = []
        self._snake_colors: list[pg.Color] = []

        self._running = False
        self._paused = False
        self._grace = 0.0
        self._score = 0
        self._last_score = -1

        self._bg_surface: pg.Surface
        self._food_glow_surface: pg.Surface
        self._score_surface: pg.Surface
        self._shadow_surface: pg.Surface
        self._pause_surface: pg.Surface

        self._build_caches()
        self._setup()

    @property
    def _tick_delta(self) -> float:
        return 1.0 / (10.0 * self._snake_speed)

    def _load_settings(self) -> None:
        self._fullscreen = False
        self._width = 800
        self._height = 600
        self._windowed_width = 800
        self._windowed_height = 600
        self._cell_size = 50
        self._frame_rate = 200
        self._food_count = 2
        self._snake_speed = 0.8
        self._grace_period = 0.13
        self._border_enabled = True
        self._overlap_enabled = False
        self._walls_enabled = False
        self._teleport_enabled = False
        self._reversal_enabled = False
        self._stones_enabled = False

        if SETTINGS_FILE.exists():
            try:
                with open(SETTINGS_FILE, "r") as f:
                    data = json.load(f)

                self._fullscreen = data.get("fullscreen", self._fullscreen)
                self._width = data.get("width", self._width)
                self._height = data.get("height", self._height)
                self._windowed_width = data.get("windowed_width", self._windowed_width)
                self._windowed_height = data.get("windowed_height", self._windowed_height)
                self._cell_size = data.get("cell_size", self._cell_size)
                self._frame_rate = data.get("frame_rate", self._frame_rate)
                self._food_count = data.get("food_count", self._food_count)
                self._snake_speed = data.get("snake_speed", self._snake_speed)
                self._grace_period = data.get("grace_period", self._grace_period)
                self._border_enabled = data.get("border_enabled", self._border_enabled)
                self._overlap_enabled = data.get("overlap_enabled", self._overlap_enabled)
                self._walls_enabled = data.get("walls_enabled", self._walls_enabled)
                self._teleport_enabled = data.get("teleport_enabled", self._teleport_enabled)
                self._reversal_enabled = data.get("reversal_enabled", self._reversal_enabled)
                self._stones_enabled = data.get("stones_enabled", self._stones_enabled)
            except (json.JSONDecodeError, OSError):
                pass

    def _save_settings(self) -> None:
        data = {
            "fullscreen": self._fullscreen,
            "width": self._width,
            "height": self._height,
            "windowed_width": self._windowed_width,
            "windowed_height": self._windowed_height,
            "cell_size": self._cell_size,
            "frame_rate": self._frame_rate,
            "food_count": self._food_count,
            "snake_speed": self._snake_speed,
            "grace_period": self._grace_period,
            "border_enabled": self._border_enabled,
            "overlap_enabled": self._overlap_enabled,
            "walls_enabled": self._walls_enabled,
            "teleport_enabled": self._teleport_enabled,
            "reversal_enabled": self._reversal_enabled,
            "stones_enabled": self._stones_enabled,
        }
        try:
            with open(SETTINGS_FILE, "w") as f:
                json.dump(data, f, indent=4)
        except OSError:
            pass

    def _build_caches(self) -> None:
        self._bg_surface = pg.Surface((self._width, self._height))
        self._bg_surface.fill(self.BACKGROUND_COLOR)
        grid_color = (25, 29, 36)

        for x in range(0, self._width, self._cell_size):
            pg.draw.line(self._bg_surface, grid_color, (x, 0), (x, self._height))
        for y in range(0, self._height, self._cell_size):
            pg.draw.line(self._bg_surface, grid_color, (0, y), (self._width, y))

        radius = self._cell_size // 2
        self._food_glow_surface = pg.Surface(
            (self._cell_size * 2, self._cell_size * 2), pg.SRCALPHA
        )
        pg.draw.circle(
            self._food_glow_surface,
            self.FOOD_GLOW_COLOR,
            (self._cell_size, self._cell_size),
            radius,
        )

        pause_font = pg.Font(self.SCORE_FONT, 36)
        self._pause_surface = pause_font.render("PAUSED (Press P/Space to Resume)", True, self.SCORE_COLOR)

        self._last_score = -1

    def _update_snake_colors(self) -> None:
        body_len = len(self._snake.body)
        self._snake_colors.clear()

        for i in range(body_len):
            factor = i / max(1, body_len - 1)
            r = int(self.SNAKE_TAIL_COLOR.r + (self.SNAKE_HEAD_COLOR.r - self.SNAKE_TAIL_COLOR.r) * factor)
            g = int(self.SNAKE_TAIL_COLOR.g + (self.SNAKE_HEAD_COLOR.g - self.SNAKE_TAIL_COLOR.g) * factor)
            b = int(self.SNAKE_TAIL_COLOR.b + (self.SNAKE_HEAD_COLOR.b - self.SNAKE_TAIL_COLOR.b) * factor)
            self._snake_colors.append(pg.Color(r, g, b))

    def _setup(self) -> None:
        theme = pgm.Theme(
            background_color=self.BACKGROUND_COLOR,
            focus_background_color=(0, 0, 0, 20),
            title=True,
            title_background_color=self.SNAKE_HEAD_COLOR,
            title_bar_style=pgm.widgets.MENUBAR_STYLE_UNDERLINE,
            title_close_button=False,
            title_font=pgm.font.FONT_BEBAS,
            title_font_color=self.SCORE_COLOR,
            title_font_size=40,
            title_offset=(10, 0),
            widget_font=pgm.font.FONT_OPEN_SANS,
            widget_font_color=self.MENU_TEXT_COLOR,
            widget_font_size=24,
            widget_margin=(0, 20),
            widget_alignment=pgm.locals.ALIGN_CENTER,
            selection_color=self.SNAKE_HEAD_COLOR,
            cursor_color=self.SNAKE_HEAD_COLOR,
            scrollbar_color=self.BACKGROUND_COLOR,
            scrollbar_slider_color=self.WALL_BORDER_COLOR,
            scrollbar_slider_hover_color=self.SNAKE_HEAD_COLOR,
            scrollbar_thick=8,
        )

        self._rules = pgm.Menu(
            "Rules", self._width, self._height, theme=theme, mouse_motion_selection=True
        )
        self._rules.add.button(
            "Back",
            pgm.events.BACK,
            font_color=self.MENU_TEXT_MUTED_COLOR,
            font_size=20,
        )
        self._rules.add.vertical_margin(10)

        rule_options = [
            ("Border: ", self._border_enabled, self._toggle_border),
            ("Overlap: ", self._overlap_enabled, self._toggle_overlap),
            ("Walls: ", self._walls_enabled, self._toggle_walls),
            ("Teleport: ", self._teleport_enabled, self._toggle_portals),
            ("Reversal: ", self._reversal_enabled, self._toggle_reversal),
            ("Stones: ", self._stones_enabled, self._toggle_stones),
        ]
        for label, default, callback in rule_options:
            self._rules.add.toggle_switch(
                label,
                default,
                onchange=callback,
                state_color=(self.STONE_COLOR, self.SNAKE_HEAD_COLOR),
                slider_color=self.SCORE_COLOR,
                switch_border_color=pg.Color(14, 15, 20),
                switch_border_width=2,
                state_text_font_color=((210, 214, 222), (20, 22, 28)),
                width=140,
            )

        self._settings = pgm.Menu(
            "Settings",
            self._width,
            self._height,
            theme=theme,
            mouse_motion_selection=True,
        )
        self._settings.add.button(
            "Back",
            pgm.events.BACK,
            font_color=self.MENU_TEXT_MUTED_COLOR,
            font_size=20,
        )
        self._settings.add.vertical_margin(6)
        self._settings.add.toggle_switch("Fullscreen", self._fullscreen, onchange=self._toggle_fullscreen)

        settings_inputs = [
            ("Width", self._width, pgm.locals.INPUT_INT, self._set_width),
            ("Height", self._height, pgm.locals.INPUT_INT, self._set_height),
            ("Cell Size", self._cell_size, pgm.locals.INPUT_INT, self._set_cell_size),
            ("Max FPS", self._frame_rate, pgm.locals.INPUT_INT, self._set_frame_rate),
            ("Food", self._food_count, pgm.locals.INPUT_INT, self._set_food_count),
            ("Speed", self._snake_speed, pgm.locals.INPUT_FLOAT, self._set_snake_speed),
            ("Grace", self._grace_period, pgm.locals.INPUT_FLOAT, self._set_grace_period),
        ]

        for title, default, in_type, callback in settings_inputs:
            is_visual = title in ("Width", "Height", "Cell Size")
            setattr(self, title + "_input", self._settings.add.text_input(
                title + ": ",
                default=default,
                input_type=in_type,
                onreturn=callback if is_visual else None,
                onchange=callback if not is_visual else None,
                background_color=self.WALL_COLOR,
                border_color=self.WALL_BORDER_COLOR,
                border_width=1,
                padding=(8, 16, 8, 16),
            ))

        self._menu = pgm.Menu(
            "PySnake",
            self._width,
            self._height,
            theme=theme,
            mouse_motion_selection=True,
            onclose=self._quit,
        )
        self._menu.add.button(
            "Play",
            self._run,
            font_size=34,
            font_name=pgm.font.FONT_OPEN_SANS_BOLD,
            font_color=self.SCORE_COLOR,
            selection_color=self.SNAKE_HEAD_COLOR,
        )
        self._menu.add.vertical_margin(22)
        self._menu.add.button("Rules", self._rules)
        self._menu.add.button("Settings", self._settings)
        self._menu.add.vertical_margin(22)
        self._menu.add.button("Quit", self._quit, selection_color=pg.Color(255, 75, 75))

    def open(self) -> None:
        self._menu.mainloop(self._screen)
        self._save_settings()

    def _quit(self) -> None:
        self._save_settings()
        pg.quit()
        sys.exit()

    def _calc_cell_size(self, width: int, height: int) -> int:
        g = math.gcd(width, height)
        if g == 0:
            return self._cell_size
        divs = []
        for i in range(1, int(g ** 0.5) + 1):
            if g % i == 0:
                divs.append(i)
                if i != g // i:
                    divs.append(g // i)
        if divs:
            if divs == [1] and self._cell_size > 1:
                return self._cell_size
            return min(divs, key=lambda x: abs(x - self._cell_size))
        return self._cell_size

    def _resize(self, width: int, height: int) -> None:
        if self._fullscreen:
            flags = pg.FULLSCREEN
            self._screen = pg.display.set_mode((0, 0), flags)
        else:
            flags = pg.SCALED | pg.RESIZABLE
            self._screen = pg.display.set_mode((width, height), flags)
            self._windowed_width = width
            self._windowed_height = height

        new_width, new_height = pg.display.get_window_size()
        self._cell_size = self._calc_cell_size(new_width, new_height)

        self._width = new_width
        self._height = new_height
        self._menu.resize(new_width, new_height)
        self._rules.resize(new_width, new_height)
        self._settings.resize(new_width, new_height)

        try:
            getattr(self, "Width_input").set_value(new_width)
            getattr(self, "Height_input").set_value(new_height)
            getattr(self, "Cell Size_input").set_value(self._cell_size)
        except Exception:
            pass

        self._build_caches()
        self._save_settings()

    def _handle_events(self) -> None:
        last_dir = self._inputs[-1] if self._inputs else self._snake.direction
        for event in pg.event.get():
            if event.type == pg.QUIT:
                self._save_settings()
                pg.quit()
                sys.exit()
            elif event.type == pg.VIDEORESIZE and not self._fullscreen:
                self._resize(event.w, event.h)
            elif event.type == pg.KEYDOWN:
                match event.key:
                    case pg.K_ESCAPE:
                        self._running = False
                    case pg.K_p | pg.K_SPACE:
                        self._paused = not self._paused
                    case pg.K_LEFT if not self._paused and last_dir not in HORIZONTAL_DIRS:
                        self._inputs.append(Direction.LEFT)
                    case pg.K_RIGHT if not self._paused and last_dir not in HORIZONTAL_DIRS:
                        self._inputs.append(Direction.RIGHT)
                    case pg.K_UP if not self._paused and last_dir not in VERTICAL_DIRS:
                        self._inputs.append(Direction.UP)
                    case pg.K_DOWN if not self._paused and last_dir not in VERTICAL_DIRS:
                        self._inputs.append(Direction.DOWN)

    def _handle_collision(self, direction: Direction) -> bool:
        next_pos = self._snake.head + (DIRECTION_OFFSETS[direction] * self._cell_size)
        collided = False

        if self._border_enabled:
            collided = not (0 <= next_pos.x < self._width and 0 <= next_pos.y < self._height)

        if not self._overlap_enabled and not collided:
            body_iter = iter(self._snake.body)
            next(body_iter, None)
            if next_pos in body_iter:
                collided = True

        if self._walls_enabled and not collided:
            collided = next_pos in self._walls

        if self._stones_enabled and not collided:
            for stone in self._stones:
                if next_pos == stone.position:
                    collided = True
                    break

        if collided:
            self._grace += self._tick_delta
            if self._grace >= self._grace_period:
                self._running = False
            return False

        self._grace = 0.0
        return True

    def _has_space(self) -> bool:
        total = (self._width // self._cell_size) * (self._height // self._cell_size)
        taken = len(self._snake.body) + len(self._walls) + len(self._stones)
        return taken < total

    def _is_empty(self, pos: pg.Vector2) -> bool:
        return pos not in self._snake.body and pos not in self._walls

    def _random_pos(self) -> pg.Vector2:
        max_col = (self._width // self._cell_size) - 1
        max_row = (self._height // self._cell_size) - 1

        for _ in range(1000):
            pos = pg.Vector2(
                random.randint(0, max_col) * self._cell_size,
                random.randint(0, max_row) * self._cell_size,
            )
            if self._is_empty(pos):
                return pos
        return pg.Vector2(-self._cell_size, -self._cell_size)

    def _eat_food(self, i: int) -> None:
        self._foods.pop(i)

        if self._reversal_enabled:
            self._snake.reverse()
        if self._teleport_enabled and self._foods:
            idx = i % len(self._foods)
            self._snake.body[-1] = self._foods[idx]
            self._foods.pop(idx)
            if self._has_space():
                self._foods.append(self._random_pos())

        if self._walls_enabled and self._has_space():
            self._walls.append(self._random_pos())

        if self._stones_enabled:
            for stone in self._stones:
                stone.remaining -= 1
            self._stones = [s for s in self._stones if s.remaining > 0]
            if self._has_space():
                for pos in itertools.islice(self._snake.body, 1, None):
                    if any(s.position == pos for s in self._stones):
                        continue
                    init_rem = random.randint(1, 8)
                    self._stones.append(Stone(pos, init_rem, init_rem))

        if self._has_space():
            self._foods.append(self._random_pos())
        self._update_snake_colors()

    def _update(self) -> None:
        if self._inputs:
            self._snake.direction = self._inputs.pop(0)

        next_pos = self._snake.head + (DIRECTION_OFFSETS[self._snake.direction] * self._cell_size)

        if not self._border_enabled and not (0 <= next_pos.x < self._width and 0 <= next_pos.y < self._height):
            if next_pos.x < 0 and self._snake.direction == Direction.LEFT:
                next_pos = pg.Vector2(self._width - self._cell_size, next_pos.y)
            elif next_pos.x >= self._width and self._snake.direction == Direction.RIGHT:
                next_pos = pg.Vector2(0, next_pos.y)
            elif next_pos.y < 0 and self._snake.direction == Direction.UP:
                next_pos = pg.Vector2(next_pos.x, self._height - self._cell_size)
            elif next_pos.y >= self._height and self._snake.direction == Direction.DOWN:
                next_pos = pg.Vector2(next_pos.x, 0)

        self._snake.body.append(next_pos)

        for i, food in enumerate(self._foods):
            if next_pos == food:
                self._eat_food(i)
                return

        self._snake.body.popleft()

    def _draw(self) -> None:
        self._screen.blit(self._bg_surface, (0, 0))

        for pos in self._foods:
            rect = pg.Rect((pos.x, pos.y), (self._cell_size, self._cell_size))
            rect = rect.inflate(-(self._cell_size // 10), -(self._cell_size // 10))
            pg.draw.rect(self._screen, self.FOOD_COLOR, rect, border_radius=3)

        for pos in self._walls:
            rect = pg.Rect((pos.x, pos.y), (self._cell_size, self._cell_size))
            pg.draw.rect(self._screen, self.WALL_COLOR, rect, border_radius=3)
            pg.draw.rect(self._screen, self.WALL_BORDER_COLOR, rect, width=1, border_radius=3)

        for stone in self._stones:
            rect = pg.Rect((stone.position.x, stone.position.y), (self._cell_size, self._cell_size))
            ratio = stone.remaining / max(1, stone.initial_remaining)

            r = int(self.STONE_COLOR.r * (0.3 + 0.7 * ratio))
            g = int(self.STONE_COLOR.g * (0.3 + 0.7 * ratio))
            b = int(self.STONE_COLOR.b * (0.3 + 0.7 * ratio))
            stone_col = pg.Color(r, g, b)

            ar = int(self.STONE_ACCENT_COLOR.r * (0.3 + 0.7 * ratio))
            ag = int(self.STONE_ACCENT_COLOR.g * (0.3 + 0.7 * ratio))
            ab = int(self.STONE_ACCENT_COLOR.b * (0.3 + 0.7 * ratio))
            accent_col = pg.Color(ar, ag, ab)

            pg.draw.rect(self._screen, stone_col, rect, border_radius=4)
            inner_rect = rect.inflate(-6, -6)
            pg.draw.rect(self._screen, accent_col, inner_rect, border_radius=2)

        body_len = len(self._snake.body)
        for i, pos in enumerate(self._snake.body):
            rect = pg.Rect((pos.x, pos.y), (self._cell_size, self._cell_size))
            segment_color = self._snake_colors[i] if i < len(self._snake_colors) else self.SNAKE_HEAD_COLOR

            if i == body_len - 1:
                pg.draw.rect(self._screen, segment_color, rect, border_radius=4)
            else:
                rect = rect.inflate(-(self._cell_size // 10), -(self._cell_size // 10))
                pg.draw.rect(self._screen, segment_color, rect, border_radius=3)

        self._score = body_len - 3
        if self._score != self._last_score:
            self._score_surface = self._font.render(f"Score: {self._score}", True, self.SCORE_COLOR)
            self._shadow_surface = self._font.render(f"Score: {self._score}", True, (0, 0, 0))
            self._last_score = self._score

        shadow_pos = (self.SCORE_POSITION[0] + 1, self.SCORE_POSITION[1] + 1)
        self._screen.blit(self._shadow_surface, shadow_pos)
        self._screen.blit(self._score_surface, self.SCORE_POSITION)

        if self._paused:
            overlay = pg.Surface((self._width, self._height), pg.SRCALPHA)
            overlay.fill((0, 0, 0, 120))
            self._screen.blit(overlay, (0, 0))

            pause_rect = self._pause_surface.get_rect(center=(self._width // 2, self._height // 2))
            self._screen.blit(self._pause_surface, pause_rect.topleft)

        pg.display.flip()

    def _prepare(self) -> None:
        self._score = 0
        self._inputs.clear()
        self._grace = 0.0
        self._paused = False

        start_x = (self._width // 2) // self._cell_size * self._cell_size
        start_y = (self._height // 2) // self._cell_size * self._cell_size

        self._snake = Snake(
            direction=Direction.RIGHT,
            body=deque([pg.Vector2(start_x + (self._cell_size * i), start_y) for i in range(3)]),
        )
        self._update_snake_colors()

        self._foods.clear()
        for _ in range(self._food_count):
            self._foods.append(self._random_pos())

        self._walls.clear()
        self._stones.clear()
        self._clock.tick()

    def _run(self) -> None:
        self._prepare()
        delta = 0.0
        self._running = True

        while self._running:
            self._handle_events()

            if self._paused:
                self._clock.tick(self._frame_rate)
                self._draw()
                continue

            delta += self._clock.tick(self._frame_rate) / 1000.0

            while delta >= self._tick_delta:
                next_dir = self._inputs[0] if self._inputs else self._snake.direction
                if self._handle_collision(next_dir):
                    self._update()
                delta -= self._tick_delta

            self._draw()

    def _toggle_fullscreen(self, value: bool) -> None:
        self._fullscreen = value
        if value:
            self._resize(0, 0)
        else:
            self._resize(self._windowed_width, self._windowed_height)

    def _set_width(self, value: int) -> None:
        if not self._fullscreen:
            self._resize(value, self._height)

    def _set_height(self, value: int) -> None:
        if not self._fullscreen:
            self._resize(self._width, value)

    def _set_cell_size(self, value: int) -> None:
        if value <= 0:
            return
        self._cell_size = value
        cols = max(1, round(self._width / self._cell_size))
        rows = max(1, round(self._height / self._cell_size))
        new_width = cols * self._cell_size
        new_height = rows * self._cell_size

        if self._fullscreen:
            return

        flags = pg.SCALED | pg.RESIZABLE
        self._screen = pg.display.set_mode((new_width, new_height), flags)
        self._width = new_width
        self._height = new_height
        self._windowed_width = new_width
        self._windowed_height = new_height
        self._menu.resize(new_width, new_height)
        self._rules.resize(new_width, new_height)
        self._settings.resize(new_width, new_height)

        try:
            getattr(self, "Width_input").set_value(new_width)
            getattr(self, "Height_input").set_value(new_height)
            getattr(self, "Cell Size_input").set_value(self._cell_size)
        except Exception:
            pass

        self._build_caches()
        self._save_settings()

    def _set_frame_rate(self, value: int) -> None:
        self._frame_rate = value
        self._save_settings()

    def _set_food_count(self, value: int) -> None:
        self._food_count = value
        self._save_settings()

    def _set_snake_speed(self, value: float) -> None:
        self._snake_speed = value
        self._save_settings()

    def _set_grace_period(self, value: float) -> None:
        self._grace_period = value
        self._save_settings()

    def _toggle_border(self, value: bool) -> None:
        self._border_enabled = value
        self._save_settings()

    def _toggle_overlap(self, value: bool) -> None:
        self._overlap_enabled = value
        self._save_settings()

    def _toggle_walls(self, value: bool) -> None:
        self._walls_enabled = value
        self._save_settings()

    def _toggle_portals(self, value: bool) -> None:
        self._teleport_enabled = value
        self._save_settings()

    def _toggle_reversal(self, value: bool) -> None:
        self._reversal_enabled = value
        self._save_settings()

    def _toggle_stones(self, value: bool) -> None:
        self._stones_enabled = value
        self._save_settings()


if __name__ == "__main__":
    game = Game()
    game.open()

# PySnake 🐍

[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-green.svg)](https://www.python.org/downloads)

A feature-rich, highly polished, and customizable Snake game built with
[Python](https://www.python.org/downloads), [pygame-ce](https://github.com/pygame-community/pygame-ce),
and [pygame-menu](https://github.com/ppizarror/pygame-menu), featuring a modern dark theme, robust settings, and modular
gameplay rule modifiers.

---

## Rules

- **Basic**: The fundamental rules of snake.
    - **Border**: Choose whether hitting screen boundaries causes a game over or wraps around.
    - **Overlap**: Toggle whether the snake can collide with its own body.
- **Advanced**: These rules trigger whenever your snake eats food.
    - **Walls**: Dynamically spawn static obstacles.
    - **Teleport**: Warp your snake's head directly to a food's coordinates.
    - **Reversal**: Automatically reverse the snake's body order and direction.
    - **Stones**: Introduce degradable obstacle stones on former body segments that wear down over time.

---

## Dependencies

- [Python 3.10+](https://www.python.org/downloads)
- [pygame-ce](https://github.com/pygame-community/pygame-ce)
- [pygame-menu](https://github.com/ppizarror/pygame-menu)

---

## Installation & Setup

1. Ensure you have Python installed on your system.
2. Install the required dependencies:
   ```bash
   pip install pygame-ce
   pip install pygame-menu --no-deps
   ```
3. Place `main.py` in your working directory.

---

## Running the Game

Execute the main script from your terminal:

```bash
python main.py
```

---

## Controls

| Key                | Action                                  |
|:-------------------|:----------------------------------------|
| **Arrow Keys**     | Steer the Snake (Left, Right, Up, Down) |
| **P** or **Space** | Pause / Resume Game                     |
| **Esc**            | Return to Menu / Quit                   |

---

## Configuration

All user preferences and rule modifications are saved automatically in `settings.json` upon modifying settings in the
menu or exiting the application.
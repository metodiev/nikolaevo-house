#!/usr/bin/env python3
"""
Лист A-04 — отворена дървена веранда 1,80 × 8,20 m по източната фасада.

Чертежът показва къщата схематично и верандата: подова скара, подпори,
парапет и стъпало. Размери в mm; координати от северозападния ъгъл на къщата.

Стартиране:  python generate_veranda_plan.py
"""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "tools"))

from svgkit import Canvas  # noqa: E402

OUT = HERE / "plans"

L, D = 12000, 8200          # къща
T = 350                     # външна стена

VX0, VY0 = L, 0             # веранда — по цялата източна фасада
VD, VL = 1800, D
VX1, VY1 = VX0 + VD, VY0 + VL
POST = 100                  # сечение на подпората
POST_X1 = VX1 - 140
POST_X2 = POST_X1 + POST
RAIL_X = (POST_X1 + POST_X2) / 2
RAIL_FROM = 2300            # парапетът започва след входа

ROOMS = [
    (350, 350, 3500, 2350, "БАНЯ"),
    (3650, 350, 6800, 2350, "МОКРО"),
    (350, 2500, 6800, 3600, "КОРИДОР"),
    (350, 3750, 3500, 7850, "СПАЛНЯ 1"),
    (3650, 3750, 6800, 7850, "СПАЛНЯ 2"),
    (6950, 350, 9630, 2570, "КУХНЯ"),
    (9750, 350, 11650, 2450, "АНТРЕ"),
    (6950, 2570, 11650, 7850, "ХОЛ + ТРАПЕЗАРИЯ"),
]

POSTS_Y = (60, 2100, 4100, 6100, VL - 160)


def draw_shell(c: Canvas) -> None:
    """Къща + веранда в план."""
    c.rect(0, 0, L, D, "wall")
    for x1, y1, x2, y2, name in ROOMS:
        c.rect(x1, y1, x2 - x1, y2 - y1, "sym-l")
        c.text((x1 + x2) / 2, (y1 + y2) / 2, name, "lbl-f")
    c.rect(T, T, L - 2 * T, D - 2 * T, "soft")

    # веранда — подова скара с дъски
    c.rect(VX0, VY0, VD, VL, "soft")
    for y in range(400, VL, 400):
        c.line(VX0, y, VX1, y, "ghost")

    # парапет и подпори
    c.line(RAIL_X, RAIL_FROM, RAIL_X, VY1 - 60, "door")
    for y in POSTS_Y:
        c.rect(POST_X1, y, POST, POST, "sym-f")

    # стъпало при входа
    c.rect(VX1, 200, 550, 1700, "sym-l")


def draw_furniture(c: Canvas) -> None:
    """Пейка до стената на къщата."""
    c.rect(VX0 + 40, 5900, 440, 1500, "sym-f")


def build() -> Canvas:
    c = Canvas(100, "A-04 Веранда — 1:100")
    u = c.u

    draw_shell(c)
    draw_furniture(c)

    # размери
    c.dim_h(VX0, VX1, -u(10), "1800")
    c.dim_v(VY0, VY1, VX1 + u(14), "8200")

    # надписи — надлъжно по верандата
    c.text(VX0 + VD / 2, 1600, "ВЕРАНДА", "lbl", rot=-90)
    c.text(VX0 + VD / 2, 4000, "1,80 × 8,20 = 14,76 m²", "lbl-s", rot=-90)
    c.text(VX0 + VD / 2, 6300, "отворена, дървена", "lbl-s", rot=-90)

    ny = D + u(24)
    notes = [
        "1. Отворена веранда по цялата източна фасада — собствена конструкция, без намеса в ICF стените.",
        "2. Дървена: подова скара, подпори 100 × 100 mm на ~2,0 m, парапет 1,00 m.",
        "3. Собствен едноскатен покрив: 2,90 m при къщата → 2,45 m при външния ръб.",
        "4. Стъпало при северния край — до входната врата В1.",
        "5. Входната врата В1 и прозорците П7 и П9 са под навеса.",
    ]
    for i, text in enumerate(notes):
        c.text(0, ny + i * u(5.4), text, "note", "start")

    c.title_block(
        -u(6), ny + u(36), 15000,
        [
            "NIKOLAEVO HOUSE — ВЕРАНДА",
            "План 1:100 · лист A-04",
            "Размери в mm. Концепция за обсъждане, не е строителен чертеж.",
        ],
        "A-04",
        "Мащаб 1:100",
    )
    return c


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    path = build().render((-1500, -2400, 18000, 19500), OUT / "A-04-veranda.svg")
    print(f"Веранда — записан файл:\n  {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""
Схеми на обзавеждането за едноетажната ICF къща.

Генерира (в furniture/plans/):
    F-01-obzor.svg   общ план с обзавеждане, 1:100
    F-02-dnevna.svg  хол + трапезария + кухня, 1:50
    F-03-spalni.svg  двете спални, 1:50
    F-04-mokri.svg   баня + мокро помещение + антре, 1:50

Координатна система: x — на изток от западната фасада, y — на юг от северната
фасада (същата като в architecture/02-areas.md). В SVG y расте надолу, затова
северът е отгоре и координатите се пренасят директно.

Всички размери са в mm.

Употреба:
    python generate_furniture.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from svgkit import Canvas, px  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

OUT = Path(__file__).resolve().parent / "plans"

# =========================================================================
# 1. ГЕОМЕТРИЯ НА СГРАДАТА (mm)
# =========================================================================

L, D, T = 12_000, 8_200, 350

# Вътрешни повърхности на помещенията: (x1, y1, x2, y2)
ROOMS = {
    "bath":  (350, 350, 3500, 2350),
    "wet":   (3650, 350, 6800, 2350),
    "corr":  (350, 2500, 6800, 3600),
    "bed1":  (350, 3750, 3500, 7850),
    "bed2":  (3650, 3750, 6800, 7850),
    "day":   (6950, 350, 11650, 7850),
    "entry": (9750, 350, 11650, 2450),
}

# Прегради — плътни участъци, без отворите
PARTITIONS = [
    (350, 2350, 2200, 2500), (3100, 2350, 6800, 2500),
    (350, 3600, 900, 3750), (1800, 3600, 4700, 3750),
    (5600, 3600, 6800, 3750),
    (6800, 350, 6950, 2500), (6800, 3600, 6950, 7850),
    (3500, 350, 3650, 2350),
    (3500, 3750, 3650, 7850),
    (9630, 350, 9750, 2450),
    (9630, 2450, 10400, 2570), (11300, 2450, 11650, 2570),
]

DOORS = [
    (11650, 700, 12000, 1750, "В1"),
    (10400, 2450, 11300, 2570, "В2"),
    (2200, 2350, 3100, 2500, "В5"),
    (3800, 2350, 4700, 2500, "В6"),
    (900, 3600, 1800, 3750, "В3"),
    (4700, 3600, 5600, 3750, "В4"),
]

WINDOWS = [
    (1175, 7850, 2675, 8200, "П1"),
    (4475, 7850, 5975, 8200, "П2"),
    (7900, 7850, 10700, 8200, "П3"),
    (1625, 0, 2225, 350, "П4"),
    (4925, 0, 5525, 350, "П5"),
    (7690, 0, 8890, 350, "П6"),
    (11650, 3500, 12000, 5100, "П7"),
    (0, 5200, 350, 6200, "П8"),
]


# =========================================================================
# 2. СИМВОЛИ
# =========================================================================


def label(c: Canvas, x, y, text, cls="lbl-f") -> None:
    if text:
        c.text(x, y, text, cls)


def plate_label(c: Canvas, x, y, text, cls="lbl") -> None:
    """Надпис с бяла подложка — за общия план, където има много линии."""
    w = len(text) * c.u(1.35)
    c.rect(x - w / 2, y - c.u(2.4), w, c.u(3.4), "plate")
    c.text(x, y, text, cls)


def bed(c: Canvas, x, y, w, h, head="E", text=None) -> None:
    """Легло: табла, две възглавници, прегъвка на завивката."""
    c.rect(x, y, w, h, "sym-f")
    bar = 90
    if head in ("E", "W"):
        hx = x + w - bar if head == "E" else x
        c.rect(hx, y, bar, h, "sym")
        px1 = hx - 400 if head == "E" else hx + bar
        c.rect(px1, y + h * 0.08, 340, h * 0.38, "sym")
        c.rect(px1, y + h * 0.54, 340, h * 0.38, "sym")
        fold = px1 - 120 if head == "E" else px1 + 460
        c.line(fold, y + 50, fold, y + h - 50, "sym-l")
    else:
        hy = y + h - bar if head == "S" else y
        c.rect(x, hy, w, bar, "sym")
        py1 = hy - 400 if head == "S" else hy + bar
        c.rect(x + w * 0.08, py1, w * 0.38, 340, "sym")
        c.rect(x + w * 0.54, py1, w * 0.38, 340, "sym")
        fold = py1 - 120 if head == "S" else py1 + 460
        c.line(x + 50, fold, x + w - 50, fold, "sym-l")
    if text:
        label(c, x + w / 2, y + h / 2 + 300, text)


def sofa(c: Canvas, x, y, w, h, back="E", seats=3, text=None) -> None:
    """Диван с облегалка и два подлакътника."""
    c.rect(x, y, w, h, "sym-f")
    bar, arm = 170, 140
    if back in ("E", "W"):
        bx = x + w - bar if back == "E" else x
        c.rect(bx, y, bar, h, "sym")
        c.rect(x, y, w, arm, "sym")
        c.rect(x, y + h - arm, w, arm, "sym")
        seat_y, seat_h = y + arm, h - 2 * arm
        step = seat_h / seats
        for i in range(1, seats):
            c.line(x + 40, seat_y + i * step, bx, seat_y + i * step, "sym-l")
    else:
        by = y + h - bar if back == "S" else y
        c.rect(x, by, w, bar, "sym")
        c.rect(x, y, arm, h, "sym")
        c.rect(x + w - arm, y, arm, h, "sym")
        seat_x, seat_w = x + arm, w - 2 * arm
        step = seat_w / seats
        for i in range(1, seats):
            c.line(seat_x + i * step, y + 40, seat_x + i * step, by, "sym-l")
    if text:
        label(c, x + w / 2, y + h / 2 + 300, text)


def armchair(c: Canvas, x, y, w, h, back="E", text=None) -> None:
    sofa(c, x, y, w, h, back=back, seats=1, text=text)


def table(c: Canvas, x, y, w, h, text=None) -> None:
    c.rect(x, y, w, h, "sym-f")
    c.rect(x + 60, y + 60, w - 120, h - 120, "sym-l")
    if text:
        label(c, x + w / 2, y + h / 2 + 60, text)


def chair(c: Canvas, x, y, size=450, facing="N") -> None:
    c.rect(x, y, size, size, "sym")
    bar = 80
    if facing == "N":
        c.rect(x, y + size - bar, size, bar, "sym")
    elif facing == "S":
        c.rect(x, y, size, bar, "sym")
    elif facing == "E":
        c.rect(x, y, bar, size, "sym")
    else:
        c.rect(x + size - bar, y, bar, size, "sym")


def dining_set(c: Canvas, x, y, w, h, text=None) -> None:
    table(c, x, y, w, h, text)
    s, g = 450, 70
    lx = x + w * 0.20
    rx = x + w * 0.80 - s
    chair(c, lx, y - s - g, s, "S")
    chair(c, rx, y - s - g, s, "S")
    chair(c, lx, y + h + g, s, "N")
    chair(c, rx, y + h + g, s, "N")
    chair(c, x - s - g, y + h / 2 - s / 2, s, "E")
    chair(c, x + w + g, y + h / 2 - s / 2, s, "W")


def wardrobe(c: Canvas, x, y, w, h, door="S", text=None) -> None:
    c.rect(x, y, w, h, "sym-f")
    o = 70
    if door == "S":
        c.line(x + o, y + h - 2 * o, x + w - o, y + h - 2 * o, "sym-l")
        c.line(x + w / 2, y + o, x + w / 2, y + h - 2 * o, "sym-l")
    elif door == "N":
        c.line(x + o, y + 2 * o, x + w - o, y + 2 * o, "sym-l")
    elif door == "E":
        c.line(x + w - 2 * o, y + o, x + w - 2 * o, y + h - o, "sym-l")
    else:
        c.line(x + 2 * o, y + o, x + 2 * o, y + h - o, "sym-l")
    if text:
        label(c, x + w / 2, y + h / 2 + 60, text)


def counter(c: Canvas, x, y, w, h, text=None) -> None:
    c.rect(x, y, w, h, "sym-f")
    c.rect(x + 40, y + 40, w - 80, h - 80, "sym-l")
    if text:
        label(c, x + w / 2, y + h / 2 + 60, text)


def sink(c: Canvas, x, y, w, h) -> None:
    c.rect(x, y, w, h, "sym")
    c.circle(x + w / 2, y + h / 2, min(w, h) * 0.26, "sym-l")


def hob(c: Canvas, x, y, w, h) -> None:
    c.rect(x, y, w, h, "sym")
    r = min(w, h) * 0.18
    for dx in (0.28, 0.72):
        for dy in (0.28, 0.72):
            c.circle(x + w * dx, y + h * dy, r, "sym-l")


def fridge(c: Canvas, x, y, w, h, text="") -> None:
    c.rect(x, y, w, h, "sym-f")
    c.line(x + w * 0.5, y + 40, x + w * 0.5, y + h - 40, "sym-l")
    if text:
        label(c, x + w / 2, y + h / 2 + 60, text)


def washer(c: Canvas, x, y, w, h, text="") -> None:
    c.rect(x, y, w, h, "sym-f")
    c.circle(x + w / 2, y + h / 2, min(w, h) * 0.28, "sym-l")
    if text:
        label(c, x + w / 2, y + h / 2 + 60, text)


def wc(c: Canvas, x, y, w, h, facing="E", text="") -> None:
    tank = 170
    if facing == "E":
        c.rect(x, y, tank, h, "sym-f")
        c.ellipse(x + tank + (w - tank) * 0.55, y + h / 2,
                  (w - tank) * 0.45, h * 0.40, "sym")
    elif facing == "W":
        c.rect(x + w - tank, y, tank, h, "sym-f")
        c.ellipse(x + (w - tank) * 0.45, y + h / 2,
                  (w - tank) * 0.45, h * 0.40, "sym")
    else:
        c.rect(x, y, w, tank, "sym-f")
        c.ellipse(x + w / 2, y + tank + (h - tank) * 0.55,
                  w * 0.40, (h - tank) * 0.42, "sym")
    if text:
        label(c, x + w / 2, y + h / 2 + 60, text)


def basin(c: Canvas, x, y, w, h, text=None) -> None:
    c.rect(x, y, w, h, "sym-f")
    c.ellipse(x + w / 2, y + h / 2, w * 0.32, h * 0.32, "sym")
    if text:
        label(c, x + w / 2, y + h / 2 + 60, text)


def shower(c: Canvas, x, y, w, h, text="") -> None:
    c.rect(x, y, w, h, "sym-f")
    c.circle(x + 140, y + 140, 60, "sym-l")
    c.line(x + w - 70, y + 70, x + w - 70, y + h - 70, "soft")
    c.line(x + 70, y + h - 70, x + w - 70, y + h - 70, "soft")
    if text:
        label(c, x + w / 2, y + h / 2 + 120, text)


def tv(c: Canvas, x, y, w, h, text="") -> None:
    c.rect(x, y, w, h, "el-f")
    if text:
        label(c, x + w + 440, y + h / 2, text)


def rug(c: Canvas, x, y, w, h) -> None:
    c.rect(x, y, w, h, "soft")


def plant(c: Canvas, cx, cy, r=180) -> None:
    c.circle(cx, cy, r, "sym-l")
    c.line(cx, cy - r, cx, cy + r, "sym-l")
    c.line(cx - r, cy, cx + r, cy, "sym-l")


# =========================================================================
# 3. ОБВИВКА НА СГРАДАТА
# =========================================================================


def draw_shell(c: Canvas) -> None:
    """Външни стени, прегради, отвори — общо за всички листове."""
    c.rect(0, 0, L, T, "wall")
    c.rect(0, D - T, L, T, "wall")
    c.rect(0, T, T, D - 2 * T, "wall")
    c.rect(L - T, T, T, D - 2 * T, "wall")

    for x1, y1, x2, y2, _ in WINDOWS:
        c.rect(x1, y1, x2 - x1, y2 - y1, "win")

    for x1, y1, x2, y2 in PARTITIONS:
        c.rect(x1, y1, x2 - x1, y2 - y1, "part")

    for x1, y1, x2, y2, code in DOORS:
        c.rect(x1, y1, x2 - x1, y2 - y1, "win")
        c.text((x1 + x2) / 2, (y1 + y2) / 2 - 240, code, "code")


# =========================================================================
# 4. ОБЗАВЕЖДАНЕ ПО ПОМЕЩЕНИЯ
# =========================================================================


def furnish_day(c: Canvas, text: bool = False) -> None:
    """Кухня (Г-образен плот), трапезария и хол."""
    counter(c, 6950, 350, 1950, 600, "ПЛОТ" if text else None)
    counter(c, 6950, 950, 600, 1500, None)
    sink(c, 7700, 400, 700, 500)
    hob(c, 7000, 1600, 500, 500)
    fridge(c, 8950, 350, 650, 700, "ХЛАД." if text else "")

    # горни шкафове — високо ниво
    c.rect(6950, 350, 1950, 300, "ghost")
    c.rect(6950, 950, 300, 1500, "ghost")

    dining_set(c, 7700, 2750, 1400, 900, "ТРАПЕЗА" if text else None)

    counter(c, 6950, 4350, 400, 1700, None)      # ТВ плот
    tv(c, 6960, 4500, 90, 1400, "ТВ" if text else "")
    sofa(c, 9200, 4200, 900, 2200, back="E", seats=3,
         text="ДИВАН" if text else None)
    armchair(c, 10150, 4300, 850, 850, back="E",
             text="ФОТЬОЙЛ" if text else None)
    table(c, 7900, 4900, 1100, 600, "ХОЛНА МАСА" if text else None)
    rug(c, 7700, 4450, 2100, 1500)
    plant(c, 11250, 7550, 190)

    if text:
        label(c, 8050, 1120, "МИВКА", "lbl-s")
        label(c, 7250, 2300, "КОТЛОНИ", "lbl-s")


def furnish_bed1(c: Canvas, text: bool = False) -> None:
    wardrobe(c, 1900, 3750, 1600, 550, door="S",
             text="ГАРДЕРОБ 1600" if text else None)
    bed(c, 1500, 4750, 2000, 1600, head="E",
        text="ЛЕГЛО 1600×2000" if text else None)
    c.rect(3050, 4350, 450, 400, "sym")
    c.rect(3050, 6350, 450, 400, "sym")
    c.rect(350, 6600, 450, 1200, "sym-f")
    rug(c, 700, 5000, 700, 1200)
    if text:
        label(c, 575, 7250, "СКРИН", "lbl-s")
        label(c, 3275, 4550, "нощно", "lbl-s")


def furnish_bed2(c: Canvas, text: bool = False) -> None:
    wardrobe(c, 5600, 3750, 1200, 550, door="S",
             text="ГАРДЕРОБ 1200" if text else None)
    bed(c, 3650, 4900, 2000, 1600, head="W",
        text="ЛЕГЛО 1600×2000" if text else None)
    c.rect(3650, 4500, 400, 450, "sym")
    c.rect(3650, 6500, 400, 450, "sym")
    c.rect(4300, 7300, 1200, 450, "sym-f")
    if text:
        label(c, 4900, 7600, "СКРИН", "lbl-s")


def furnish_bath(c: Canvas, text: bool = False) -> None:
    shower(c, 400, 400, 1150, 850, "ДУШ" if text else "")
    wc(c, 400, 1300, 800, 450, facing="E")
    basin(c, 1000, 1820, 1000, 500, "МИВКА + ШКАФ" if text else None)
    c.rect(1000, 2330, 1000, 30, "sym-l")
    rug(c, 1900, 1450, 600, 400)
    if text:
        label(c, 750, 1550, "WC", "lbl-s")


def furnish_wet(c: Canvas, text: bool = False) -> None:
    washer(c, 3650, 350, 600, 600, "ПЕРАЛНЯ" if text else "")
    washer(c, 4300, 350, 600, 600, "СУШИЛНЯ" if text else "")
    counter(c, 5500, 350, 1300, 600, "ПЛОТ" if text else None)
    sink(c, 5700, 400, 500, 450)
    c.rect(3650, 1000, 400, 400, "sym-f")       # стелаж
    c.rect(6150, 1500, 600, 600, "sym-f")       # бойлер
    c.rect(5000, 1700, 600, 600, "ghost")       # вентилация
    if text:
        label(c, 3850, 1250, "СТЕЛАЖ", "lbl-s")
        label(c, 6450, 1850, "БОЙЛЕР", "lbl-s")
        label(c, 5300, 2050, "ВЕНТИЛАЦИЯ", "lbl-s")


def furnish_entry(c: Canvas, text: bool = False) -> None:
    wardrobe(c, 9750, 500, 400, 900, door="E", text=None)
    c.rect(9750, 1600, 450, 500, "sym-f")       # пейка
    c.rect(9850, 2440, 500, 30, "el-f")         # табло
    if text:
        c.text(9950, 950, "ГАРДЕРОБ", "lbl-s", rot=-90)
        label(c, 9975, 1980, "ПЕЙКА", "lbl-s")
        label(c, 10100, 2230, "ТАБЛО", "lbl-s")


# =========================================================================
# 5. ЛИСТОВЕ
# =========================================================================


def build_overview() -> Canvas:
    c = Canvas(100, "F-01 Обзавеждане — общ план 1:100")
    u = c.u

    draw_shell(c)
    furnish_day(c)
    furnish_bed1(c)
    furnish_bed2(c)
    furnish_bath(c)
    furnish_wet(c)
    furnish_entry(c)

    plate_label(c, 2850, 900, "БАНЯ")
    plate_label(c, 5400, 1450, "МОКРО / КИЛЕР")
    plate_label(c, 3600, 3050, "КОРИДОР")
    plate_label(c, 850, 4650, "СПАЛНЯ 1")
    plate_label(c, 6250, 4650, "СПАЛНЯ 2")
    plate_label(c, 8300, 7000, "ХОЛ + КУХНЯ")
    plate_label(c, 10950, 1150, "АНТРЕ")

    nx, ny, ns = L + u(12), u(4), u(5.0)
    c.poly([(nx, ny - ns), (nx + ns * 0.55, ny + ns), (nx, ny + ns * 0.35),
            (nx - ns * 0.55, ny + ns)], "wall-l")
    c.text(nx, ny - ns - u(3.0), "С", "lbl")

    ly = D + u(8)
    c.text(0, ly, "ЛЕГЕНДА", "sub", "start")
    c.rect(0, ly + u(4), u(9), u(5), "sym-f")
    c.text(u(12), ly + u(7.6), "мебел / санитария", "note", "start")
    c.rect(0, ly + u(12), u(9), u(5), "ghost")
    c.text(u(12), ly + u(15.6), "високо ниво — горни шкафове, вентилация",
           "note", "start")
    c.rect(0, ly + u(20), u(9), u(5), "soft")
    c.text(u(12), ly + u(23.6), "килим", "note", "start")
    c.rect(0, ly + u(28), u(9), u(5), "el-f")
    c.text(u(12), ly + u(31.6), "електрическо табло", "note", "start")

    c.title_block(
        -u(10), D + u(42), L + u(22),
        [
            "NIKOLAEVO HOUSE — ОБЗАВЕЖДАНЕ",
            "Общ план с обзавеждане · лист F-01",
            "Ориентировъчна схема — размерите на мебелите са примерни.",
            "Не е проект за изработка на мебели. Размери в mm.",
        ],
        "F-01",
        "Мащаб 1:100",
    )
    return c


def build_day() -> Canvas:
    c = Canvas(50, "F-02 Дневна зона — 1:50")
    u = c.u

    draw_shell(c)
    furnish_day(c, text=True)

    # скрива частта от спалня 2 вляво от преградата
    c.rect(-px(1.0), -px(1.0), px(7.80), px(11.0), "mask")

    plate_label(c, 8300, 6900, "ХОЛ + ТРАПЕЗАРИЯ + КУХНЯ 30,8 m²")

    c.dim_h(6950, 11650, D + u(10), "4700", D)
    c.dim_v(350, 2450, 6950 - u(9), "2100")
    c.dim_v(2450, 7850, 6950 - u(9), "5400")

    nx, ny = 6950, D + u(16)
    notes = [
        "1. Кухня: Г-образен плот 600 mm. Мивка под прозореца, котлони на западния плот.",
        "2. Хладилник 650 mm в североизточния ъгъл на кухнята.",
        "3. Трапезария 1400 × 900 с 6 стола между кухнята и хола.",
        "4. Диван 2200 mm с облегалка на изток, срещу телевизора на западната преграда.",
        "5. Пред плъзгащата врата (П3) остава свободна зона поне 1200 mm.",
        "6. Горните шкафове (пунктир) са на височина 1400–2200 mm.",
    ]
    for i, text in enumerate(notes):
        c.text(nx, ny + i * u(5.0), text, "note", "start")

    c.title_block(
        px(6.40), ny + u(40), 5200,
        [
            "NIKOLAEVO HOUSE — ОБЗАВЕЖДАНЕ",
            "Дневна зона · лист F-02",
            "Размери в mm. Мебелите са с примерни размери.",
        ],
        "F-02",
        "Мащаб 1:50",
    )
    return c


def build_bedrooms() -> Canvas:
    c = Canvas(50, "F-03 Спални — 1:50")
    u = c.u

    draw_shell(c)
    furnish_bed1(c, text=True)
    furnish_bed2(c, text=True)

    # скрива коридора и останалите помещения над спалните
    c.rect(-px(1.0), -px(1.0), px(14.0), px(4.65), "mask")

    plate_label(c, 1000, 4650, "СПАЛНЯ 1 · 3150 × 4100")
    plate_label(c, 4300, 4650, "СПАЛНЯ 2 · 3150 × 4100")

    c.dim_h(350, 3500, D + u(10), "3150", D)
    c.dim_v(3750, 7850, 350 - u(9), "4100")

    ny = D + u(16)
    notes = [
        "1. Леглото е с табла на вътрешната преграда — без прозорец зад главата.",
        "2. Гардероб с плъзгащи врати: 1600 mm в спалня 1, 1200 mm в спалня 2.",
        "3. Нощни шкафчета от двете страни на леглото.",
        "4. Скрин в спалня 1 на югозападната стена; в спалня 2 — под прозореца.",
        "5. Свободен проход около леглото ≥ 700 mm.",
    ]
    for i, text in enumerate(notes):
        c.text(350, ny + i * u(5.0), text, "note", "start")

    c.title_block(
        350, ny + u(36), 6450,
        [
            "NIKOLAEVO HOUSE — ОБЗАВЕЖДАНЕ",
            "Спални · лист F-03",
            "Размери в mm. Мебелите са с примерни размери.",
        ],
        "F-03",
        "Мащаб 1:50",
    )
    return c


def build_wet() -> Canvas:
    c = Canvas(50, "F-04 Баня, мокро помещение и антре — 1:50")
    u = c.u

    draw_shell(c)
    furnish_bath(c, text=True)
    furnish_wet(c, text=True)
    furnish_entry(c, text=True)

    # скрива всичко под северната лента (коридор, спални)
    c.rect(-px(1.0), px(2.58), px(14.0), px(6.0), "mask")

    plate_label(c, 2550, 1400, "БАНЯ · 3150 × 2000")
    plate_label(c, 5250, 1250, "МОКРО / КИЛЕР · 3150 × 2000")
    plate_label(c, 10800, 900, "АНТРЕ · 1900 × 2100")
    plate_label(c, 8300, 1400, "КУХНЯ — виж лист F-02")

    ny = 2700 + u(14)
    notes = [
        "1. Баня: душ 1200 × 900 в северозападния ъгъл, WC до западната стена.",
        "2. Мивка с шкаф 1000 mm срещу вратата; огледало на южната стена.",
        "3. Мокро помещение: пералня и сушилня до прозореца, плот и мивка в източния край.",
        "4. Бойлер 600 × 600 в югоизточния ъгъл; вентилация на високо ниво (пунктир).",
        "5. Антре: гардероб 400 mm и пейка до входа; табло на южната стена до вратата.",
    ]
    for i, text in enumerate(notes):
        c.text(350, ny + i * u(5.0), text, "note", "start")

    c.title_block(
        350, ny + u(36), 11300,
        [
            "NIKOLAEVO HOUSE — ОБЗАВЕЖДАНЕ",
            "Баня, мокро помещение, антре · лист F-04",
            "Размери в mm. Санитарията е с примерни размери.",
        ],
        "F-04",
        "Мащаб 1:50",
    )
    return c


# =========================================================================
# 6. MAIN
# =========================================================================


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    jobs = [
        (build_overview, "F-01-obzor.svg", (-px(0.7), -px(1.0), px(15.0), px(16.4))),
        (build_day, "F-02-dnevna.svg", (px(6.30), -px(0.5), px(5.7), px(13.2))),
        (build_bedrooms, "F-03-spalni.svg", (-px(0.45), px(3.40), px(7.9), px(8.4))),
        (build_wet, "F-04-mokri.svg", (-px(0.4), -px(0.5), px(12.6), px(8.1))),
    ]
    print("Обзавеждане — записани файлове:")
    for builder, name, viewbox in jobs:
        path = builder().render(viewbox, OUT / name)
        print(f"  {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""
Генерира скиците за ICF доставчика (папка icf/plans).

Чертежите се строят от един-единствен модел на данните (стени + отвори), така
че планът, фасадите и количествата винаги са съгласувани помежду си. При
промяна на размер се редактира само секция 2 и скриптът се стартира отново.

Изходни файлове (в icf/plans/):
    icf-plan.svg        план на ICF стените, 1:100
    icf-elevations.svg  четирите фасади с отворите, 1:100
    icf-details.svg     детайли: ъгъл, отвор, преграда, надгреда, 1:30
    icf-courses.svg     редене на блокове + ъглов захват, 1:40

Употреба:
    python generate_icf_drawings.py

Забележка: това са концептуални скици за оферта, а не работен проект.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# =========================================================================
# 1. КОНСТАНТИ
# =========================================================================

# --- Геометрия на сградата (m) -------------------------------------------
HOUSE_L = 12.00          # изток–запад
HOUSE_D = 8.20           # север–юг

# --- ICF стена (работно допускане — уточнява се по избраната система) ----
WALL_T = 0.35            # обща дебелина
EPS_T = 0.08             # един слой EPS
CORE_T = 0.15            # бетонно ядро

# Височина на стената до стрехата (m). Фронтоните НЕ са ICF.
WALL_H = 3.00

# Модул на блока — само за илюстрация, потвърждава се от доставчика
BLOCK_L = 0.50
BLOCK_H = 0.25

# --- Мащаби ---------------------------------------------------------------
SCALE_PLAN = 100
SCALE_ELEV = 100
SCALE_DETAIL = 40
SCALE_COURSES = 40

OUT_DIR = Path(__file__).resolve().parent / "plans"

# =========================================================================
# 2. МОДЕЛ НА ДАННИТЕ  ← редактира се само тук
# =========================================================================


@dataclass(frozen=True)
class Opening:
    """Отвор в ICF стена. offset се мери от референтния ъгъл на стената."""

    code: str
    wall: str
    offset: float        # m от референтния ъгъл
    width: float         # m
    sill: float          # m — височина на подпрозореца
    height: float        # m — височина на отвора
    kind: str            # "window" | "door" | "slider"
    optional: bool = False

    @property
    def head(self) -> float:
        return self.sill + self.height

    @property
    def area(self) -> float:
        return self.width * self.height


@dataclass(frozen=True)
class Wall:
    """Външна ICF стена."""

    code: str
    name: str
    facade: str          # south | north | east | west
    length: float        # m по външния габарит
    ref_corner: str      # откъде се мерят отворите


WALLS = [
    Wall("W1", "Южна", "south", HOUSE_L, "западен ъгъл"),
    Wall("W2", "Северна", "north", HOUSE_L, "западен ъгъл"),
    Wall("W3", "Западна", "west", HOUSE_D, "северен ъгъл"),
    Wall("W4", "Източна", "east", HOUSE_D, "северен ъгъл"),
]

OPENINGS = [
    # --- юг ---
    Opening("O1", "W1", 1.175, 1.50, 0.80, 1.40, "window"),          # спалня 1
    Opening("O2", "W1", 4.475, 1.50, 0.80, 1.40, "window"),          # спалня 2
    Opening("O3", "W1", 7.900, 2.80, 0.00, 2.25, "slider"),          # хол → тераса
    # --- север ---
    Opening("O4", "W2", 1.625, 0.60, 1.60, 0.60, "window"),          # баня
    Opening("O5", "W2", 4.925, 0.60, 1.50, 0.60, "window"),          # мокро помещение
    Opening("O6", "W2", 7.690, 1.20, 1.00, 1.40, "window"),          # кухня
    # --- изток (offset от северния ъгъл) ---
    Opening("O7", "W4", 0.700, 1.05, 0.00, 2.10, "door"),            # вход
    Opening("O8", "W4", 3.500, 1.60, 0.80, 1.40, "window"),          # трапезария
    # --- запад (опция; offset от северния ъгъл: y 5,20–6,20) ---
    Opening("O9", "W3", 5.200, 1.00, 0.80, 1.40, "window", True),    # спалня 1
]

# Вътрешни прегради (НЕ са ICF) — само за контекст в плана.
# (x1, y1, x2, y2) в m; y се мери от южната фасада.
PARTITIONS = [
    (6.80, 0.35, 6.95, 7.85),     # дневна / спална зона
    (3.50, 6.20, 3.65, 7.85),     # баня / мокро
    (0.35, 5.70, 6.80, 5.85),     # северна лента / коридор
    (0.35, 4.45, 6.80, 4.60),     # коридор / спални
    (3.50, 0.35, 3.65, 4.45),     # между спалните
    (9.63, 5.75, 9.75, 7.85),     # антре — западна стена
    (9.63, 5.63, 11.65, 5.75),    # антре — южна стена
]

# =========================================================================
# 3. ПОМОЩНИ ФУНКЦИИ
# =========================================================================


def esc(text: str) -> str:
    """Екранира специални символи за XML."""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def fmt(value: float, digits: int = 0) -> str:
    """Число с десетична запетая. digits=0 → цяло число."""
    if digits == 0:
        return f"{value:.0f}".replace(".", ",")
    return f"{value:.{digits}f}".replace(".", ",")


def px(meters: float) -> float:
    """Реален размер в метри → чертожни единици (1 единица = 1 mm реалност)."""
    return meters * 1000.0


class Canvas:
    """
    Малък SVG конструктор.

    Две различни мерни единици, които не бива да се бъркат:
      * `px(m)` — реален размер (сградата), 1 единица = 1 mm от сградата;
      * `u(mm)`  — мярка върху хартията, превърната в единици по мащаба.

    Всичко, което е геометрия на сградата, минава през px(); всичко, което е
    отстъп на текст, легенда или рамка — през u().
    """

    def __init__(self, scale: int, title: str, desc: str = ""):
        self.scale = scale
        self.title = title
        self.desc = desc
        self.els: list[str] = []

    # --- мащабиране -------------------------------------------------------
    def u(self, paper_mm: float) -> float:
        """Милиметри върху хартията → чертожни единици."""
        return paper_mm * self.scale

    # --- примитиви --------------------------------------------------------
    def line(self, x1, y1, x2, y2, cls="wall-l") -> None:
        self.els.append(
            f'<line class="{cls}" x1="{x1:.1f}" y1="{y1:.1f}" '
            f'x2="{x2:.1f}" y2="{y2:.1f}"/>'
        )

    def rect(self, x, y, w, h, cls="wall") -> None:
        self.els.append(
            f'<rect class="{cls}" x="{x:.1f}" y="{y:.1f}" '
            f'width="{max(w, 0.1):.1f}" height="{max(h, 0.1):.1f}"/>'
        )

    def poly(self, pts, cls="wall-l", closed=True) -> None:
        points = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
        tag = "polygon" if closed else "polyline"
        self.els.append(f'<{tag} class="{cls}" points="{points}"/>')

    def text(self, x, y, s, cls="lbl", anchor="middle", rot=0.0) -> None:
        tr = f' transform="rotate({rot:.1f} {x:.1f} {y:.1f})"' if rot else ""
        self.els.append(
            f'<text class="{cls}" x="{x:.1f}" y="{y:.1f}" '
            f'text-anchor="{anchor}"{tr}>{esc(s)}</text>'
        )

    # --- размери ----------------------------------------------------------
    def dim_h(self, x1, x2, y, label, ext_from=None) -> None:
        """Хоризонтален размер с наклонени чертички и текст над линията."""
        t = self.u(0.75)
        self.line(x1, y, x2, y, "dim")
        self.line(x1 - t, y + t, x1 + t, y - t, "dim")
        self.line(x2 - t, y + t, x2 + t, y - t, "dim")
        if ext_from is not None:
            self.line(x1, ext_from, x1, y, "dim")
            self.line(x2, ext_from, x2, y, "dim")
        if abs(x2 - x1) > self.u(3.2):
            self.text((x1 + x2) / 2, y - self.u(1.0), label, "dimt")

    def dim_v(self, y1, y2, x, label, ext_from=None, side="left") -> None:
        """Вертикален размер. y1/y2 са в екранни координати (надолу)."""
        t = self.u(0.75)
        self.line(x, y1, x, y2, "dim")
        self.line(x - t, y1 + t, x + t, y1 - t, "dim")
        self.line(x - t, y2 + t, x + t, y2 - t, "dim")
        if ext_from is not None:
            self.line(ext_from, y1, x, y1, "dim")
            self.line(ext_from, y2, x, y2, "dim")
        if abs(y2 - y1) > self.u(3.2):
            dx = -self.u(1.1) if side == "left" else self.u(1.1)
            self.text(x + dx, (y1 + y2) / 2, label, "dimt", rot=-90)

    # --- рамка -------------------------------------------------------------
    def title_block(self, x, y, w, lines, sheet, scale_text) -> None:
        """Описателна рамка: заглавие, лист/мащаб и бележки."""
        h1 = self.u(8.0)
        h2 = self.u(7.0)
        h3 = self.u(5.2) * (len(lines) - 2) + self.u(4.0)
        total = h1 + h2 + h3

        self.els.append(
            f'<rect class="tb" x="{x:.1f}" y="{y:.1f}" '
            f'width="{w:.1f}" height="{total:.1f}"/>'
        )
        self.line(x, y + h1, x + w, y + h1, "tb")
        self.line(x, y + h1 + h2, x + w, y + h1 + h2, "tb")

        split = x + w - self.u(62)
        self.line(split, y, split, y + h1 + h2, "tb")

        self.text(x + self.u(3), y + h1 * 0.66, lines[0], "tbmain", "start")
        self.text(x + self.u(3), y + h1 + h2 * 0.68, lines[1], "tbsub", "start")
        self.text(split + self.u(3), y + h1 * 0.64, sheet, "tbsmall", "start")
        self.text(split + self.u(3), y + h1 + h2 * 0.68, scale_text,
                  "tbsmall", "start")

        for i, note in enumerate(lines[2:]):
            self.text(
                x + self.u(3),
                y + h1 + h2 + self.u(4.0) + i * self.u(5.2),
                note, "tbsmall", "start",
            )

    # --- рендер ------------------------------------------------------------
    def style(self) -> str:
        s = self.scale

        def q(mm: float) -> str:
            return f"{mm * s:.2f}"

        return (
            '<style type="text/css"><![CDATA[\n'
            f'.wall    {{ fill:#e3e3e3; stroke:#111; stroke-width:{q(0.30)}; }}\n'
            f'.wall-l  {{ fill:none; stroke:#111; stroke-width:{q(0.22)}; }}\n'
            f'.open    {{ fill:#fff; stroke:#111; stroke-width:{q(0.26)}; }}\n'
            f'.openopt {{ fill:#fff; stroke:#111; stroke-width:{q(0.26)}; '
            f'stroke-dasharray:{q(1.0)} {q(0.6)}; }}\n'
            f'.core    {{ fill:none; stroke:#111; stroke-width:{q(0.16)}; }}\n'
            f'.axis    {{ fill:none; stroke:#777; stroke-width:{q(0.13)}; '
            f'stroke-dasharray:{q(1.6)} {q(0.5)} {q(0.3)} {q(0.5)}; }}\n'
            f'.part    {{ fill:none; stroke:#9a9a9a; stroke-width:{q(0.18)}; '
            f'stroke-dasharray:{q(1.0)} {q(0.5)}; }}\n'
            f'.hidden  {{ fill:none; stroke:#aaa; stroke-width:{q(0.16)}; '
            f'stroke-dasharray:{q(0.7)} {q(0.5)}; }}\n'
            f'.dim     {{ fill:none; stroke:#666; stroke-width:{q(0.14)}; }}\n'
            f'.dimt    {{ fill:#333; font-size:{q(2.0)}px; text-anchor:middle; }}\n'
            f'.lbl     {{ fill:#111; font-size:{q(2.7)}px; text-anchor:middle; }}\n'
            f'.lbl-s   {{ fill:#555; font-size:{q(2.05)}px; text-anchor:middle; }}\n'
            f'.code    {{ fill:#111; font-size:{q(2.1)}px; font-weight:bold; '
            'text-anchor:middle; }\n'
            f'.ttl     {{ fill:#111; font-size:{q(4.2)}px; font-weight:bold; '
            'text-anchor:middle; }\n'
            f'.sub     {{ fill:#555; font-size:{q(2.3)}px; text-anchor:middle; }}\n'
            f'.note    {{ fill:#222; font-size:{q(2.05)}px; }}\n'
            f'.tb      {{ fill:none; stroke:#111; stroke-width:{q(0.25)}; }}\n'
            f'.tbmain  {{ fill:#111; font-size:{q(3.0)}px; font-weight:bold; }}\n'
            f'.tbsub   {{ fill:#333; font-size:{q(2.4)}px; }}\n'
            f'.tbsmall {{ fill:#444; font-size:{q(1.95)}px; }}\n'
            f'.plate   {{ fill:#ffffff; stroke:none; }}\n'
            ']]></style>'
        )

    def render(self, viewbox, filename: str) -> Path:
        """Записва SVG. Листът се оразмерява автоматично по мащаба."""
        x, y, w, h = viewbox
        parts = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            f'<svg xmlns="http://www.w3.org/2000/svg" '
            f'width="{w / self.scale:.1f}mm" height="{h / self.scale:.1f}mm" '
            f'viewBox="{x:.0f} {y:.0f} {w:.0f} {h:.0f}" '
            'font-family="DejaVu Sans, Liberation Sans, Arial, sans-serif">',
            f"<title>{esc(self.title)}</title>",
        ]
        if self.desc:
            parts.append(f"<desc>{esc(self.desc)}</desc>")
        parts.append(self.style())
        parts.append(
            f'<rect x="{x:.0f}" y="{y:.0f}" width="{w:.0f}" height="{h:.0f}" '
            'fill="#ffffff"/>'
        )
        parts.extend(self.els)
        parts.append("</svg>")

        path = OUT_DIR / filename
        path.write_text("\n".join(parts), encoding="utf-8")
        return path


# =========================================================================
# 4. ПЛАН НА ICF СТЕНИТЕ (1:100)
# =========================================================================


def y_screen(ym: float) -> float:
    """y се мери от южната фасада на север → обръща се за екрана."""
    return px(HOUSE_D - ym)


def build_plan() -> Canvas:
    c = Canvas(SCALE_PLAN, "План на ICF стените — 1:100")

    u = c.u
    L = px(HOUSE_L)
    D = px(HOUSE_D)
    T = px(WALL_T)

    # --- стени ------------------------------------------------------------
    c.rect(0, y_screen(WALL_T), L, T)             # W1 юг
    c.rect(0, 0, L, T)                            # W2 север
    c.rect(0, T, T, D - 2 * T)                    # W3 запад
    c.rect(L - T, T, T, D - 2 * T)                # W4 изток

    # --- бетонно ядро: две линии в средата на стената ---------------------
    # Чертае се ПРЕДИ отворите, за да не пресича белите им полета.
    c1 = px(EPS_T)
    c2 = px(EPS_T + CORE_T)
    c.line(c1, 0, c1, D, "core")
    c.line(c2, 0, c2, D, "core")
    c.line(0, c1, L, c1, "core")
    c.line(0, c2, L, c2, "core")

    # --- отвори -----------------------------------------------------------
    for op in OPENINGS:
        cls = "openopt" if op.optional else "open"
        if op.wall == "W1":
            c.rect(px(op.offset), y_screen(WALL_T), px(op.width), T, cls)
        elif op.wall == "W2":
            c.rect(px(op.offset), 0, px(op.width), T, cls)
        elif op.wall == "W3":
            c.rect(0, px(op.offset), T, px(op.width), cls)
        else:
            c.rect(L - T, px(op.offset), T, px(op.width), cls)

    # --- оси --------------------------------------------------------------
    a = T / 2
    c.line(0, y_screen(WALL_T) + a, L, y_screen(WALL_T) + a, "axis")
    c.line(0, a, L, a, "axis")
    c.line(a, 0, a, D, "axis")
    c.line(L - a, 0, L - a, D, "axis")

    # --- вътрешни прегради (не са ICF) ------------------------------------
    for x1, y1, x2, y2 in PARTITIONS:
        c.poly(
            [
                (px(x1), y_screen(y1)),
                (px(x2), y_screen(y1)),
                (px(x2), y_screen(y2)),
                (px(x1), y_screen(y2)),
            ],
            "part",
        )

    # --- надписи ----------------------------------------------------------
    def wall_name(x, y, text, rot=0.0) -> None:
        """Надпис върху стената — с бяла подложка, за да не се губи в щриховката."""
        w = len(text) * c.u(1.35)
        h = c.u(3.0)
        if rot:
            c.rect(x - h * 0.55, y - w / 2, h, w, "plate")
        else:
            c.rect(x - w / 2, y - c.u(2.2), w, h, "plate")
        c.text(x, y, text, "code", rot=rot)

    wall_name(px(1.9), y_screen(WALL_T) + T * 0.72, "W1 · ЮЖНА")
    wall_name(px(1.9), T * 0.72, "W2 · СЕВЕРНА")
    wall_name(T * 0.60, px(HOUSE_D / 2), "W3", rot=-90)
    wall_name(L - T * 0.60, px(HOUSE_D / 2), "W4", rot=-90)

    for op in OPENINGS:
        mid_w = px(op.offset + op.width / 2)
        if op.wall == "W1":
            c.text(mid_w, y_screen(WALL_T) + T * 1.55, op.code, "code")
        elif op.wall == "W2":
            c.text(mid_w, -T * 0.55, op.code, "code")
        elif op.wall == "W3":
            c.text(-T * 0.55, px(op.offset + op.width / 2), op.code, "code", rot=-90)
        else:
            c.text(L + T * 0.55, px(op.offset + op.width / 2), op.code, "code", rot=-90)

    # --- размерни вериги ---------------------------------------------------
    def chain_x(wall_code: str, y: float, ext_from: float) -> None:
        bounds = [0.0]
        for op in OPENINGS:
            if op.wall == wall_code:
                bounds += [op.offset, op.offset + op.width]
        bounds = sorted(bounds) + [HOUSE_L]
        for a_, b_ in zip(bounds, bounds[1:]):
            c.dim_h(px(a_), px(b_), y, fmt((b_ - a_) * 1000), ext_from)

    def chain_y(wall_code: str, x: float, ext_from: float, side: str) -> None:
        bounds = [0.0]
        for op in OPENINGS:
            if op.wall == wall_code:
                bounds += [op.offset, op.offset + op.width]
        bounds = sorted(bounds) + [HOUSE_D]
        for a_, b_ in zip(bounds, bounds[1:]):
            c.dim_v(px(a_), px(b_), x, fmt((b_ - a_) * 1000), ext_from, side)

    chain_x("W2", -u(12), 0.0)                    # север
    c.dim_h(0, L, -u(26), fmt(HOUSE_L * 1000))

    chain_x("W1", D + u(12), D)                   # юг
    c.dim_h(0, L, D + u(26), fmt(HOUSE_L * 1000))

    chain_y("W3", -u(12), 0.0, "left")            # запад
    c.dim_v(0, D, -u(26), fmt(HOUSE_D * 1000), side="left")

    chain_y("W4", L + u(12), L, "right")          # изток
    c.dim_v(0, D, L + u(26), fmt(HOUSE_D * 1000), side="right")

    c.text(0, D + u(38),
           "Размери по вертикалните стени (W3, W4) — от северната фасада",
           "lbl-s", "start")

    # --- север -------------------------------------------------------------
    nx, ny, ns = L + u(46), -u(4), u(5.0)
    c.poly(
        [(nx, ny - ns), (nx + ns * 0.55, ny + ns), (nx, ny + ns * 0.35),
         (nx - ns * 0.55, ny + ns)]
    )
    c.text(nx, ny - ns - u(3.0), "С", "lbl")
    c.text(nx, ny + ns + u(5.0), "север", "lbl-s")

    # --- легенда -----------------------------------------------------------
    ly = D + u(48)
    c.text(0, ly, "ЛЕГЕНДА", "sub", "start")
    entries = [
        ("wall", "ICF стена 350 mm"),
        ("open", "отвор — прозорец или врата"),
        ("openopt", "отвор — опция (O9)"),
        ("axis", "ос на стената"),
        ("part", "вътрешна преграда — НЕ е ICF"),
    ]
    for i, (style, label) in enumerate(entries):
        y = ly + u(6.0) + i * u(7.0)
        if style in ("wall", "open", "openopt"):
            c.rect(0, y - u(2.2), u(11.0), u(4.4), style)
        else:
            c.line(0, y, u(11.0), y, style)
        c.text(u(14.0), y + u(1.6), label, "note", "start")

    # --- таблица на стените -------------------------------------------------
    tx = u(62)
    c.text(tx, ly, "СТЕНИ", "sub", "start")
    headers = ("код / име", "дължина × височина", "отвори мерени от")
    offsets = (0.0, u(30), u(66))
    for head, off in zip(headers, offsets):
        c.text(tx + off, ly + u(6.0), head, "lbl-s", "start")
    for i, wall in enumerate(WALLS):
        y = ly + u(12.0) + i * u(7.0)
        c.text(tx, y, f"{wall.code}  {wall.name}", "note", "start")
        c.text(tx + offsets[1], y,
               f"{fmt(wall.length * 1000)} × {fmt(WALL_H * 1000)} mm",
               "note", "start")
        c.text(tx + offsets[2], y, wall.ref_corner, "note", "start")

    # --- описателна рамка ---------------------------------------------------
    c.title_block(
        -u(30), D + u(96), L + u(60),
        [
            "NIKOLAEVO HOUSE — ПАКЕТ ЗА ICF ДОСТАВЧИК",
            "План на ICF стените · лист ICF-01",
            f"Стени: 4 бр. външни, дебелина {fmt(WALL_T * 1000)} mm, "
            f"височина до стреха {fmt(WALL_H * 1000)} mm",
            "Отвори: 8 бр. + 1 опция · вътрешните прегради не са ICF",
            "Размери в mm. Скица за оферта — не е работен проект.",
        ],
        "ICF-01",
        f"Мащаб 1:{SCALE_PLAN}",
    )

    return c


# =========================================================================
# 5. ФАСАДИ (1:100, 2 × 2)
# =========================================================================

# Кой край е отляво при изглед отвън + функция за огледална позиция
ELEV_VIEW = {
    "south": ("ИЗТОК", "ЗАПАД", lambda op: HOUSE_L - (op.offset + op.width)),
    "north": ("ЗАПАД", "ИЗТОК", lambda op: op.offset),
    "east": ("СЕВЕР", "ЮГ", lambda op: op.offset),
    "west": ("ЮГ", "СЕВЕР", lambda op: HOUSE_D - (op.offset + op.width)),
}


def build_elevations() -> Canvas:
    c = Canvas(SCALE_ELEV, "Фасади на ICF стените — 1:100")
    u = c.u

    col = {"south": 0.0, "north": u(140), "east": 0.0, "west": u(140)}
    row = {"south": 0.0, "north": 0.0, "east": u(78), "west": u(78)}

    for wall in WALLS:
        x0 = col[wall.facade]
        y_top = row[wall.facade] + u(7.0)          # горен ръб на стената
        length = px(wall.length)
        height = px(WALL_H)
        y_base = y_top + height                     # линия на терена

        left_name, right_name, screen = ELEV_VIEW[wall.facade]

        c.text(x0, row[wall.facade] + u(2.5),
               f"{wall.code} · {wall.name.upper()} ФАСАДА", "code", "start")

        c.rect(x0, y_top, length, height)

        ops = [op for op in OPENINGS if op.wall == wall.code]
        for op in ops:
            cls = "openopt" if op.optional else "open"
            sx = x0 + px(screen(op))
            sy = y_base - px(op.head)
            c.rect(sx, sy, px(op.width), px(op.height), cls)
            c.text(sx + px(op.width) / 2, sy - u(1.2), op.code, "code")

        c.line(x0 - u(3), y_base, x0 + length + u(3), y_base)

        c.text(x0, y_top - u(1.5), left_name, "lbl-s", "start")
        c.text(x0 + length, y_top - u(1.5), right_name, "lbl-s", "end")

        # размери по ширина
        bounds = [0.0]
        for op in ops:
            bounds += [screen(op), screen(op) + op.width]
        bounds = sorted(set(bounds)) + [wall.length]
        for a_, b_ in zip(bounds, bounds[1:]):
            c.dim_h(x0 + px(a_), x0 + px(b_), y_base + u(8),
                    fmt((b_ - a_) * 1000), y_base)
        c.dim_h(x0, x0 + length, y_base + u(16), fmt(wall.length * 1000))

        # височина на стената
        c.dim_v(y_top, y_base, x0 - u(5), fmt(WALL_H * 1000), x0)

        # таблица на отворите
        ty = y_base + u(25)
        c.text(x0, ty, "код", "lbl-s", "start")
        c.text(x0 + u(12), ty, "ширина × височина", "lbl-s", "start")
        c.text(x0 + u(52), ty, "подпрозорец", "lbl-s", "start")
        c.text(x0 + u(80), ty, "горен ръб", "lbl-s", "start")
        for i, op in enumerate(ops):
            y = ty + u(4.2) + i * u(4.2)
            suffix = "  (опция)" if op.optional else ""
            c.text(x0, y, op.code, "note", "start")
            c.text(x0 + u(12), y,
                   f"{fmt(op.width * 1000)} × {fmt(op.height * 1000)}{suffix}",
                   "note", "start")
            c.text(x0 + u(52), y, fmt(op.sill * 1000), "note", "start")
            c.text(x0 + u(80), y, fmt(op.head * 1000), "note", "start")

    c.title_block(
        -u(16), u(163), u(296),
        [
            "NIKOLAEVO HOUSE — ПАКЕТ ЗА ICF ДОСТАВЧИК",
            "Фасади на ICF стените · лист ICF-02",
            "Изгледи отвън. Размери в mm, височини от кота ±0,00 (терен).",
            "Стената е до кота +3000. Фронтоните над нея НЕ са ICF — лека конструкция.",
            "O9 е опция — да се оферира отделно.  Скица за оферта, не е работен проект.",
        ],
        "ICF-02",
        f"Мащаб 1:{SCALE_ELEV}",
    )

    return c


# =========================================================================
# 6. ДЕТАЙЛИ (1:30)
# =========================================================================


def build_details() -> Canvas:
    c = Canvas(SCALE_DETAIL, "Детайли на ICF възела — 1:30")
    u = c.u
    T = px(WALL_T)

    cw = px(1.62)                # ширина на клетка
    gap = u(16)

    # ---------------- Д1: външен ъгъл 90° (план) ----------------
    x, y = 0.0, u(10)
    c.text(x, y - u(3), "Д1 · ВЪНШЕН ЪГЪЛ 90° — ПЛАН", "code", "start")
    c.rect(x, y, T, px(1.30))
    c.rect(x, y, px(1.30), T)
    c.line(x + px(EPS_T), y + px(EPS_T + CORE_T),
           x + px(EPS_T), y + px(1.30), "core")
    c.line(x + px(EPS_T + CORE_T), y + px(EPS_T),
           x + px(1.30), y + px(EPS_T), "core")
    c.line(x + px(EPS_T + CORE_T), y + px(EPS_T + CORE_T),
           x + px(1.30), y + px(EPS_T + CORE_T), "core")
    c.line(x + px(EPS_T + CORE_T), y + px(EPS_T + CORE_T),
           x + px(EPS_T + CORE_T), y + px(1.30), "core")
    c.text(x, y + px(1.30) + u(6), "непрекъснато ядро,", "lbl-s", "start")
    c.text(x, y + px(1.30) + u(10), "доп. армировка в ъгъла", "lbl-s", "start")
    c.dim_h(x, x + T, y - u(7), fmt(WALL_T * 1000))
    c.dim_v(y, y + T, x - u(7), fmt(WALL_T * 1000), side="left")

    # ---------------- Д2: ръб на отвор (план) ----------------
    x = cw + gap
    y = u(10)
    c.text(x, y - u(3), "Д2 · РЪБ НА ОТВОР — ПЛАН", "code", "start")
    c.rect(x, y, px(0.95), T)
    c.line(x + px(0.95), y - u(3), x + px(0.95), y + T + u(3))
    c.text(x, y + T + u(7), "стена", "lbl-s", "start")
    c.text(x + px(1.05), y + T * 0.5 + u(1), "отвор →", "lbl-s", "start")
    c.text(x, y + T + u(13), "затварящ блок / челен капак", "lbl-s", "start")
    c.text(x, y + T + u(17), "по системата на доставчика", "lbl-s", "start")

    # ---------------- Д3: преграда към ICF стена (план) ----------------
    x = 0.0
    y = px(1.75) + u(22)
    c.text(x, y - u(3), "Д3 · ПРЕГРАДА КЪМ ICF СТЕНА — ПЛАН", "code", "start")
    c.rect(x, y, px(1.30), T)
    c.line(x + px(0.55), y + T, x + px(0.55), y + T + px(0.60), "part")
    c.line(x + px(0.67), y + T, x + px(0.67), y + T + px(0.60), "part")
    c.line(x + px(0.55), y + T + px(0.60), x + px(0.67), y + T + px(0.60), "part")
    c.text(x + px(0.61), y + T + px(0.60) + u(5),
           "преграда 120 mm", "lbl-s", "start")
    c.text(x, y + T + px(0.60) + u(13),
           "не прекъсва ядрото и не носи покрива", "lbl-s", "start")

    # ---------------- Д4: надгреда над отвор (разрез) ----------------
    x = cw + gap
    y = px(1.75) + u(22)
    c.text(x, y - u(3), "Д4 · НАДГРЕДА НАД ОТВОР — РАЗРЕЗ", "code", "start")
    c.rect(x, y, T, px(0.55))                       # стена над отвора
    c.line(x, y + px(0.55), x, y + px(1.40), "hidden")
    c.line(x + T, y + px(0.55), x + T, y + px(1.40), "hidden")
    c.line(x, y + px(1.40), x + T, y + px(1.40), "hidden")
    c.text(x + T / 2, y + px(0.98), "отвор", "lbl-s", rot=-90)
    c.text(x + T + u(3), y + px(0.62), "надгреда по", "lbl-s", "start")
    c.text(x + T + u(3), y + px(0.62) + u(4.5), "конструктивен", "lbl-s", "start")
    c.text(x + T + u(3), y + px(0.62) + u(9.0), "проект", "lbl-s", "start")
    c.dim_v(y, y + px(0.55), x - u(7), "≥550", side="left")

    # ---------------- бележки ----------------
    ny = px(1.75) + u(22) + px(1.60) + u(16)
    c.text(0, ny, "БЕЛЕЖКИ", "sub", "start")
    notes = [
        "1. Дебелината 350 mm е работно допускане — уточнява се по избраната ICF система (250–400 mm).",
        "2. Армировката и класът бетон се определят от конструктор, не от доставчика на панелите.",
        "3. Отворите се оформят в кофража — не се изрязват след бетониране.",
        "4. Надгредата над плъзгащата врата O3 (2800 mm) е задължителна — да влезе в офертата.",
        "5. Размери в mm. Детайлите са схематични, не са работни чертежи.",
    ]
    for i, line in enumerate(notes):
        c.text(0, ny + u(8) + i * u(5.5), line, "note", "start")

    c.title_block(
        -u(8), ny + u(34), u(152),
        [
            "NIKOLAEVO HOUSE — ПАКЕТ ЗА ICF ДОСТАВЧИК",
            "Детайли на ICF възела · лист ICF-03",
            "Концептуални схеми за оферта — не са работни детайли.",
        ],
        "ICF-03",
        f"Мащаб 1:{SCALE_DETAIL}",
    )

    return c


# =========================================================================
# 7. РЕДЕНЕ НА БЛОКОВЕ (1:40)
# =========================================================================


def build_courses() -> Canvas:
    c = Canvas(SCALE_COURSES, "Редене на блокове — 1:40")
    u = c.u

    courses = int(round(WALL_H / BLOCK_H))
    wall_len = px(4.0)

    # --- стена с курсове ----------------------------------------------------
    x0, y0 = 0.0, u(10)
    c.text(x0, y0 - u(3), "ТИПОВО РЕДЕНЕ — ПОКАЗАН УЧАСТЪК 4,00 m", "code", "start")

    c.rect(x0, y0, wall_len, px(WALL_H), "wall-l")
    for i in range(courses + 1):
        c.line(x0, y0 + i * px(BLOCK_H), x0 + wall_len,
               y0 + i * px(BLOCK_H), "core")

    for i in range(courses):
        y_top = y0 + i * px(BLOCK_H)
        y_bot = y_top + px(BLOCK_H)
        pos = BLOCK_L / 2 if i % 2 else 0.0
        while pos < 4.0 - 1e-6:
            if pos > 1e-6:
                c.line(x0 + px(pos), y_top, x0 + px(pos), y_bot, "core")
            pos += BLOCK_L

    c.dim_v(y0, y0 + px(WALL_H), x0 - u(7), fmt(WALL_H * 1000), x0)
    c.dim_h(x0, x0 + wall_len, y0 - u(9), "4000", y0)

    # модул по височина — размерът е вдясно от стената
    c.dim_v(y0, y0 + px(BLOCK_H), x0 + wall_len + u(9), fmt(BLOCK_H * 1000))
    c.text(x0 + wall_len + u(11), y0 + px(BLOCK_H) + u(7),
           f"модул {fmt(BLOCK_H * 1000)}", "lbl-s", "start")

    # --- ъглов захват --------------------------------------------------------
    gx = px(5.30)
    gy = y0
    c.text(gx, gy - u(3), "ЪГЛОВ ЗАХВАТ — ПЛАН", "code", "start")
    c.rect(gx, gy, px(WALL_T), px(0.90), "wall")
    c.rect(gx, gy, px(0.90), px(WALL_T), "wall")
    # непрекъснато ядро през ъгъла
    c.line(gx + px(EPS_T + CORE_T), gy + px(EPS_T + CORE_T),
           gx + px(0.90), gy + px(EPS_T + CORE_T), "core")
    c.line(gx + px(EPS_T + CORE_T), gy + px(EPS_T + CORE_T),
           gx + px(EPS_T + CORE_T), gy + px(0.90), "core")
    c.text(gx, gy + px(0.90) + u(8), "непрекъснато ядро;", "lbl-s", "start")
    c.text(gx, gy + px(0.90) + u(8) + u(4.5), "блоковете се редуват по височина",
           "lbl-s", "start")

    # --- бележки -------------------------------------------------------------
    nx = 0.0
    ny = y0 + px(WALL_H) + u(18)
    c.text(nx, ny, "ВАЖНО ЗА ОФЕРТАТА", "sub", "start")
    notes = [
        "1. Модулът 0,50 × 0,25 m е примерен — реалният се дава от доставчика.",
        "2. Броят блокове зависи от модула и от разположението на отворите.",
        "3. Да се посочи процент отпадък от рязане.",
        "4. Ъглите и Т-възлите се решават с елементи от системата.",
        "5. Реденето започва от ъгъл.",
    ]
    for i, line in enumerate(notes):
        c.text(nx, ny + u(8) + i * u(5.5), line, "note", "start")

    c.title_block(
        -u(8), ny + u(38), u(168),
        [
            "NIKOLAEVO HOUSE — ПАКЕТ ЗА ICF ДОСТАВЧИК",
            "Редене на блокове · лист ICF-04",
            "Схематично — модулът се потвърждава от доставчика.",
        ],
        "ICF-04",
        f"Мащаб 1:{SCALE_COURSES}",
    )

    return c


# =========================================================================
# 8. КОНТРОЛНА СМЕТКА
# =========================================================================


def quantities() -> dict:
    """Изчислява количествата, които се показват и в документацията."""
    perimeter = 2 * (HOUSE_L + HOUSE_D)
    axis_perimeter = 2 * ((HOUSE_L - WALL_T) + (HOUSE_D - WALL_T))
    gross = axis_perimeter * WALL_H
    base = [op for op in OPENINGS if not op.optional]
    optional = [op for op in OPENINGS if op.optional]
    open_area = sum(op.area for op in base)
    net = gross - open_area
    return {
        "perimeter": perimeter,
        "axis_perimeter": axis_perimeter,
        "gross": gross,
        "openings": open_area,
        "net": net,
        "concrete": net * CORE_T,
        "eps": net * 2 * EPS_T,
        "optional_area": sum(op.area for op in optional),
        "open_count": len(base),
        "opt_count": len(optional),
    }


def report() -> None:
    q = quantities()
    print("ICF КОНТРОЛНА СМЕТКА")
    print(f"  Външен контур:            {q['perimeter']:.2f} m")
    print(f"  Контур по ос:             {q['axis_perimeter']:.2f} m")
    print(f"  Височина на стена:        {WALL_H:.2f} m")
    print(f"  Брутна площ (по ос):      {q['gross']:.2f} m²")
    print(f"  Отвори ({q['open_count']} бр.):            {q['openings']:.2f} m²")
    print(f"  Нетна площ ICF стена:     {q['net']:.2f} m²")
    print(f"  Бетон в ядрото:           {q['concrete']:.2f} m³")
    print(f"  EPS (2 × {EPS_T * 1000:.0f} mm):          {q['eps']:.2f} m³")
    print(f"  Опция ({q['opt_count']} бр.):              {q['optional_area']:.2f} m²")

    print("\n  Отвори по стени:")
    for wall in WALLS:
        ops = [op for op in OPENINGS if op.wall == wall.code]
        print(f"    {wall.code} {wall.name}:")
        for op in ops:
            flag = " (опция)" if op.optional else ""
            print(
                f"      {op.code}  {fmt(op.width * 1000):>5} × "
                f"{fmt(op.height * 1000):>4}  подпрозорец "
                f"{fmt(op.sill * 1000):>4}{flag}"
            )


# =========================================================================
# 9. MAIN
# =========================================================================


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    report()

    jobs = [
        (build_plan, "icf-plan.svg",
         (-px(3.2), -px(3.2), px(21.2), px(24.8))),
        (build_elevations, "icf-elevations.svg",
         (-px(2.6), -px(2.2), px(30.6), px(22.8))),
        (build_details, "icf-details.svg",
         (-px(1.2), -px(0.4), px(6.6), px(8.5))),
        (build_courses, "icf-courses.svg",
         (-px(1.2), -px(0.7), px(9.4), px(7.6))),
    ]

    print("\nЗаписани файлове:")
    for builder, name, viewbox in jobs:
        path = builder().render(viewbox, name)
        print(f"  {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

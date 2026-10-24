#!/usr/bin/env python3
"""
Концептуален план на едноетажна ICF къща — DXF.

Чертае СЪЩАТА къща като останалите чертежи в проекта:
    12,00 × 8,20 m по външните стени = 98,40 m² застроена площ
    външни ICF стени 0,35 m, вътрешни прегради 0,15 m (0,12 m при антрето)

Координатна система: начало — външен югозападен ъгъл, x на изток, y на север.

Слоеве
------
    WALLS       стени и прегради
    DOORS       врати (крило + дъга)
    WINDOWS     прозорци и плъзгаща врата
    ROOMS       контури на помещенията + надписи с площ
    DIMENSIONS  размерни вериги, рамка, север

Употреба
--------
    python generate_plan.py              # DXF + PNG + SVG
    python generate_plan.py --no-image   # само DXF

Зависимости
-----------
    ezdxf          (задължителна)
    matplotlib     (само за експорт на изображения)

Забележка: концептуален чертеж, не строителен проект.
"""

from __future__ import annotations

import argparse
import math
import sys
from dataclasses import dataclass
from pathlib import Path

import ezdxf
from ezdxf import units
from ezdxf.enums import TextEntityAlignment

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# =========================================================================
# 1. КОНСТАНТИ
# =========================================================================

# --- Външни габарити (m) --------------------------------------------------
HOUSE_LENGTH = 12.00            # изток–запад
HOUSE_DEPTH = 8.20              # север–юг
BUILT_AREA = HOUSE_LENGTH * HOUSE_DEPTH       # 98,40 m²

# --- Конструкция ----------------------------------------------------------
WALL_EXT = 0.35                 # външна ICF стена
WALL_INT = 0.15                 # вътрешна преграда
WALL_THIN = 0.12                # преграда при антрето
DOOR_WIDTH = 0.90               # стандартна вътрешна врата
WALL_H = 3.00                   # височина до стреха (за контекст)

# --- Текстове и изход -----------------------------------------------------
TEXT_ROOM = 0.19
TEXT_INFO = 0.13
TEXT_DIM = 0.14

LAYER_WALLS = "WALLS"
LAYER_DOORS = "DOORS"
LAYER_WINDOWS = "WINDOWS"
LAYER_ROOMS = "ROOMS"
LAYER_DIMENSIONS = "DIMENSIONS"

DXF_NAME = "house.dxf"
IMAGE_NAME = "house"

TEXT_STYLE = "ICF"
TEXT_FONT = "LiberationSans-Regular.ttf"

COLOR_LINE = 7
COLOR_ROOM = 7
COLOR_WALL_FILL = 9

# Очаквани площи — за контрол в report()
EXPECTED = {
    "built": 98.40,
    "interior": 84.75,
    "net": 80.28,
}


# =========================================================================
# 2. МОДЕЛИ
# =========================================================================


@dataclass(frozen=True)
class Room:
    """Правоъгълно помещение по вътрешни стени."""

    name: str
    x1: float
    y1: float
    x2: float
    y2: float

    @property
    def width(self) -> float:
        return self.x2 - self.x1

    @property
    def height(self) -> float:
        return self.y2 - self.y1

    @property
    def area(self) -> float:
        return self.width * self.height


@dataclass(frozen=True)
class Wall:
    """Стена като правоъгълник + отвори по дългата ѝ ос."""

    x1: float
    y1: float
    x2: float
    y2: float
    openings: tuple[tuple[float, float], ...] = ()

    @property
    def is_horizontal(self) -> bool:
        return (self.x2 - self.x1) >= (self.y2 - self.y1)


# --- Помещения (y от юг) ---------------------------------------------------
ROOMS = [
    Room("СПАЛНЯ 1", 0.35, 0.35, 3.50, 4.45),
    Room("СПАЛНЯ 2", 3.65, 0.35, 6.80, 4.45),
    Room("ХОЛ + ТРАПЕЗАРИЯ", 6.95, 0.35, 11.65, 5.63),
    Room("КУХНЯ", 6.95, 5.63, 9.63, 7.85),
    Room("КОРИДОР", 0.35, 4.60, 6.80, 5.70),
    Room("БАНЯ", 0.35, 5.85, 3.50, 7.85),
    Room("МОКРО / КИЛЕР", 3.65, 5.85, 6.80, 7.85),
    Room("АНТРЕ", 9.75, 5.75, 11.65, 7.85),
]

# --- Стени ----------------------------------------------------------------
WALLS = [
    # външни
    Wall(0.0, 0.0, HOUSE_LENGTH, WALL_EXT,
         ((1.175, 2.675), (4.475, 5.975), (7.900, 10.700))),      # юг
    Wall(0.0, HOUSE_DEPTH - WALL_EXT, HOUSE_LENGTH, HOUSE_DEPTH,
         ((1.625, 2.225), (4.925, 5.525), (7.690, 8.890))),       # север
    Wall(0.0, WALL_EXT, WALL_EXT, HOUSE_DEPTH - WALL_EXT,
         ((2.00, 3.00),)),                                        # запад
    Wall(HOUSE_LENGTH - WALL_EXT, WALL_EXT, HOUSE_LENGTH, HOUSE_DEPTH - WALL_EXT,
         ((3.10, 4.70), (6.45, 7.50))),                           # изток
    # вътрешни
    Wall(3.50, 5.85, 3.65, 7.85),                                 # баня / мокро
    Wall(3.50, 0.35, 3.65, 4.45),                                 # между спалните
    Wall(6.80, 5.70, 6.95, 7.85),                                 # дневна / мокро
    Wall(6.80, 0.35, 6.95, 4.60),                                 # дневна / спални
    Wall(0.35, 5.70, 6.80, 5.85,
         ((2.20, 3.10), (3.80, 4.70))),                           # врати баня / мокро
    Wall(0.35, 4.45, 6.80, 4.60,
         ((0.90, 1.80), (4.70, 5.60))),                           # врати спални
    Wall(9.63, 5.75, 9.75, 7.85),                                 # антре — запад
    Wall(9.63, 5.63, 11.65, 5.75, ((10.40, 11.30),)),             # антре — юг
]

# --- Врати: (панта, ширина, посока по стената, страна на отваряне) ---------
DOORS = [
    ((11.65, 7.50), 1.05, (0.0, -1.0), -1.0),   # входна, отваря се в антрето
    ((3.10, 5.85), DOOR_WIDTH, (-1.0, 0.0), -1.0),   # баня
    ((3.80, 5.85), DOOR_WIDTH, (1.0, 0.0), 1.0),     # мокро
    ((0.90, 4.45), DOOR_WIDTH, (1.0, 0.0), -1.0),    # спалня 1
    ((5.60, 4.45), DOOR_WIDTH, (-1.0, 0.0), 1.0),    # спалня 2
    ((11.30, 5.63), DOOR_WIDTH, (-1.0, 0.0), 1.0),   # антре → хол
]

# --- Прозорци: (x1, y1, x2, y2, вид) -------------------------------------
WINDOWS = [
    (1.175, 0.0, 2.675, WALL_EXT, "window"),          # спалня 1
    (4.475, 0.0, 5.975, WALL_EXT, "window"),          # спалня 2
    (7.900, 0.0, 10.700, WALL_EXT, "slider"),         # хол → тераса
    (1.625, 7.85, 2.225, HOUSE_DEPTH, "window"),      # баня
    (4.925, 7.85, 5.525, HOUSE_DEPTH, "window"),      # мокро
    (7.690, 7.85, 8.890, HOUSE_DEPTH, "window"),      # кухня
    (0.0, 2.00, WALL_EXT, 3.00, "window"),            # спалня 1, запад (опция)
    (11.65, 3.10, HOUSE_LENGTH, 4.70, "window"),      # трапезария
]


# =========================================================================
# 3. ПОМОЩНИ ФУНКЦИИ
# =========================================================================


def bg(value: float, digits: int = 2) -> str:
    """Форматира число с десетична запетая."""
    return f"{value:.{digits}f}".replace(".", ",")


def create_layers(doc: ezdxf.document.Drawing) -> None:
    specs = {
        LAYER_WALLS: (COLOR_LINE, 50),
        LAYER_DOORS: (COLOR_LINE, 25),
        LAYER_WINDOWS: (COLOR_LINE, 25),
        LAYER_ROOMS: (COLOR_ROOM, 13),
        LAYER_DIMENSIONS: (COLOR_LINE, 13),
    }
    for name, (color, lineweight) in specs.items():
        doc.layers.add(name, color=color, lineweight=lineweight)


def create_text_style(doc: ezdxf.document.Drawing) -> str:
    doc.styles.add(TEXT_STYLE, font=TEXT_FONT)
    return TEXT_STYLE


def create_dim_style(doc: ezdxf.document.Drawing) -> str:
    name = "ICF"
    style = doc.dimstyles.add(name)
    style.dxf.dimtxsty = TEXT_STYLE
    style.dxf.dimtxt = TEXT_DIM
    style.dxf.dimasz = 0.09
    style.dxf.dimexe = 0.08
    style.dxf.dimexo = 0.08
    style.dxf.dimgap = 0.05
    style.dxf.dimdec = 2
    style.dxf.dimzin = 0
    style.dxf.dimdsep = 44
    style.dxf.dimclrt = COLOR_LINE
    style.dxf.dimclre = COLOR_LINE
    style.dxf.dimtad = 1
    return name


def add_label(
    msp: ezdxf.layouts.Modelspace,
    x: float,
    y: float,
    text: str,
    height: float = TEXT_INFO,
    layer: str = LAYER_ROOMS,
    align: TextEntityAlignment = TextEntityAlignment.MIDDLE_CENTER,
) -> None:
    entity = msp.add_text(
        text, height=height, dxfattribs={"layer": layer, "style": TEXT_STYLE}
    )
    entity.set_placement((x, y), align=align)


def draw_filled_rect(
    msp: ezdxf.layouts.Modelspace,
    x1: float,
    y1: float,
    x2: float,
    y2: float,
    layer: str,
    fill_color: int = COLOR_WALL_FILL,
) -> None:
    points = [(x1, y1), (x2, y1), (x2, y2), (x1, y2)]
    msp.add_lwpolyline(points, close=True, dxfattribs={"layer": layer})
    hatch = msp.add_hatch(dxfattribs={"layer": layer})
    hatch.set_solid_fill(color=fill_color)
    hatch.paths.add_polyline_path(points, is_closed=True)


# =========================================================================
# 4. ЧЕРТАНЕ НА СТАЯ ПО КООРДИНАТИ
# =========================================================================


def draw_room(
    msp: ezdxf.layouts.Modelspace,
    x1: float,
    y1: float,
    x2: float,
    y2: float,
    name: str,
    *,
    layer: str = LAYER_ROOMS,
    show_size: bool = True,
    label: bool = True,
) -> float:
    """
    Чертае стая по координати.

    Параметри
    ---------
    x1, y1 : долен ляв ъгъл (m)
    x2, y2 : горен десен ъгъл (m)
    name   : име на помещението
    layer  : слой за контура и надписа
    show_size : дали да се изпишат размерите и площта
    label  : дали да се изпише името (при тясно помещение се изписва отделно)

    Връща
    -----
    Площта на помещението в m².

    Контурът е затворена полилиния, за да може площта да се измери директно
    в CAD с AREA / MASSPROP.
    """
    if x2 <= x1 or y2 <= y1:
        raise ValueError(f"Некоректни координати за стая „{name}“")

    width, height = x2 - x1, y2 - y1
    area = width * height
    cx, cy = (x1 + x2) / 2, (y1 + y2) / 2

    msp.add_lwpolyline(
        [(x1, y1), (x2, y1), (x2, y2), (x1, y2)],
        close=True,
        dxfattribs={"layer": layer},
    )

    # В ниските помещения надписът се измества, за да не пада върху вратата
    offset = 0.18 if height < 2.20 else 0.0
    if not label:
        return area
    if show_size:
        add_label(msp, cx, cy + TEXT_INFO + offset, name, TEXT_ROOM, layer)
        add_label(msp, cx, cy - TEXT_INFO + offset,
                  f"{bg(width)} × {bg(height)} · {bg(area)} m²", TEXT_INFO, layer)
    else:
        add_label(msp, cx, cy + offset, name, TEXT_ROOM, layer)
    return area


# =========================================================================
# 5. ЧЕРТАНЕ НА ЕЛЕМЕНТИТЕ
# =========================================================================


def _wall_segment(msp, wall: Wall, start: float, end: float, layer: str) -> None:
    if wall.is_horizontal:
        draw_filled_rect(msp, start, wall.y1, end, wall.y2, layer)
    else:
        draw_filled_rect(msp, wall.x1, start, wall.x2, end, layer)


def draw_wall(msp, wall: Wall, layer: str = LAYER_WALLS) -> None:
    """Стена, разделена на плътни участъци между отворите."""
    start, end = (wall.x1, wall.x2) if wall.is_horizontal else (wall.y1, wall.y2)
    cuts = sorted(
        (max(start, s), min(end, e)) for s, e in wall.openings if e > start and s < end
    )
    cursor = start
    for a, b in cuts:
        if a > cursor:
            _wall_segment(msp, wall, cursor, a, layer)
        cursor = max(cursor, b)
    if cursor < end:
        _wall_segment(msp, wall, cursor, end, layer)


def draw_window(msp, x1, y1, x2, y2, kind="window", layer=LAYER_WINDOWS) -> None:
    """Прозорец или плъзгаща врата."""
    horizontal = (x2 - x1) >= (y2 - y1)
    msp.add_lwpolyline(
        [(x1, y1), (x2, y1), (x2, y2), (x1, y2)],
        close=True,
        dxfattribs={"layer": layer},
    )
    if horizontal:
        mid = (y1 + y2) / 2
        if kind == "slider":
            half = (x1 + x2) / 2
            msp.add_line((x1, mid - 0.03), (half, mid - 0.03), dxfattribs={"layer": layer})
            msp.add_line((half, mid + 0.03), (x2, mid + 0.03), dxfattribs={"layer": layer})
        else:
            msp.add_line((x1, mid), (x2, mid), dxfattribs={"layer": layer})
    else:
        mid = (x1 + x2) / 2
        msp.add_line((mid, y1), (mid, y2), dxfattribs={"layer": layer})


def draw_door(msp, hinge, width, along, side, layer=LAYER_DOORS) -> None:
    """Крило под 90° и дъга на отваряне."""
    ax, ay = along
    px_, py_ = -ay * side, ax * side
    leaf = (hinge[0] + px_ * width, hinge[1] + py_ * width)
    closed = (hinge[0] + ax * width, hinge[1] + ay * width)

    msp.add_line(hinge, leaf, dxfattribs={"layer": layer})

    start = math.degrees(math.atan2(closed[1] - hinge[1], closed[0] - hinge[0]))
    end = math.degrees(math.atan2(leaf[1] - hinge[1], leaf[0] - hinge[0]))
    if round((end - start) % 360) != 90:
        start, end = end, start
    msp.add_arc(hinge, width, start, end, dxfattribs={"layer": layer})


def draw_dimensions(msp, dimstyle: str, layer: str = LAYER_DIMENSIONS) -> None:
    attrs = {"layer": layer}

    def linear(p1, p2, base, angle=0.0):
        dim = msp.add_linear_dim(
            base=base, p1=p1, p2=p2, angle=angle, dimstyle=dimstyle, dxfattribs=attrs
        )
        dim.render()

    # над сградата
    top = HOUSE_DEPTH
    chain_y = HOUSE_DEPTH + 1.05
    linear((0.35, top), (3.50, top), (0, chain_y))
    linear((3.65, top), (6.80, top), (0, chain_y))
    linear((6.95, top), (11.65, top), (0, chain_y))
    linear((0, top), (HOUSE_LENGTH, top), (0, HOUSE_DEPTH + 1.85))

    # вляво
    chain_x = -0.95
    linear((0, 5.85), (0, 7.85), (chain_x, 0), angle=90)
    linear((0, 4.60), (0, 5.70), (chain_x, 0), angle=90)
    linear((0, 0.35), (0, 4.45), (chain_x, 0), angle=90)
    linear((0, 0), (0, HOUSE_DEPTH), (chain_x - 0.75, 0), angle=90)


def draw_title_block(msp, layer=LAYER_DIMENSIONS) -> None:
    x1, y1, x2, y2 = 0.0, -2.95, HOUSE_LENGTH, -1.05
    msp.add_lwpolyline(
        [(x1, y1), (x2, y1), (x2, y2), (x1, y2)], close=True, dxfattribs={"layer": layer}
    )
    msp.add_line((0.0, -1.62), (HOUSE_LENGTH, -1.62), dxfattribs={"layer": layer})
    msp.add_line((9.60, -1.62), (9.60, -1.05), dxfattribs={"layer": layer})

    add_label(msp, 0.20, -1.26, "NIKOLAEVO HOUSE — едноетажна ICF къща",
              0.17, layer, TextEntityAlignment.MIDDLE_LEFT)
    add_label(msp, 0.20, -1.47, "КОНЦЕПТУАЛЕН ПЛАН — 12,00 × 8,20 m",
              0.12, layer, TextEntityAlignment.MIDDLE_LEFT)
    add_label(msp, 9.75, -1.26, "Лист A-01", 0.13, layer,
              TextEntityAlignment.MIDDLE_LEFT)
    add_label(msp, 9.75, -1.47, "Мащаб 1:100", 0.13, layer,
              TextEntityAlignment.MIDDLE_LEFT)

    net = sum(room.area for room in ROOMS)
    lines = [
        f"Застроена площ {bg(BUILT_AREA)} m² · чиста използваема {bg(net)} m² · "
        f"височина до стреха {bg(WALL_H)} m",
        f"Външни ICF стени {bg(WALL_EXT)} m · прегради {bg(WALL_INT)} / "
        f"{bg(WALL_THIN)} m · врати {bg(DOOR_WIDTH)} m · размери в m",
        "Концептуален чертеж за обсъждане. Не е строителен проект.",
    ]
    for i, text in enumerate(lines):
        add_label(msp, 0.20, -1.92 - i * 0.24, text, 0.115, layer,
                  TextEntityAlignment.MIDDLE_LEFT)


def draw_north_arrow(msp, layer=LAYER_DIMENSIONS) -> None:
    cx, cy, size = 13.15, 6.30, 0.45
    msp.add_lwpolyline(
        [(cx, cy + size), (cx + size * 0.55, cy - size), (cx, cy - size * 0.35),
         (cx - size * 0.55, cy - size)],
        close=True,
        dxfattribs={"layer": layer},
    )
    add_label(msp, cx, cy + size + 0.30, "С", 0.22, layer)


# =========================================================================
# 6. СГЛОБЯВАНЕ
# =========================================================================


def build_house() -> ezdxf.document.Drawing:
    doc = ezdxf.new(dxfversion="R2010", setup=True)
    doc.units = units.M
    doc.header["$LUNITS"] = 2
    doc.header["$LUPREC"] = 2

    create_layers(doc)
    create_text_style(doc)
    dimstyle = create_dim_style(doc)
    msp = doc.modelspace()

    for room in ROOMS:
        # антрето е тясно и вратата минава през средата — надписът се мести
        is_entry = room.name == "АНТРЕ"
        draw_room(msp, room.x1, room.y1, room.x2, room.y2, room.name,
                  show_size=not is_entry, label=not is_entry)

    # антрето е тясно (1,90 m) — размерът и площта се разбиват на два реда
    add_label(msp, 10.70, 6.85, "АНТРЕ", TEXT_ROOM)
    add_label(msp, 10.70, 6.60, "1,90 × 2,10", TEXT_INFO)
    add_label(msp, 10.70, 6.38, "3,99 m²", TEXT_INFO)

    for wall in WALLS:
        draw_wall(msp, wall)
    for x1, y1, x2, y2, kind in WINDOWS:
        draw_window(msp, x1, y1, x2, y2, kind)
    for hinge, width, along, side in DOORS:
        draw_door(msp, hinge, width, along, side)

    add_label(msp, 12.45, 6.98, "ВХОД", TEXT_INFO, LAYER_DOORS)

    draw_dimensions(msp, dimstyle)
    draw_title_block(msp)
    draw_north_arrow(msp)
    return doc


def report() -> None:
    """Контролна сметка — сравнява се с очакваните стойности от проекта."""
    print("Помещения (по вътрешни стени):")
    for room in ROOMS:
        print(f"  {room.name:<18} {bg(room.width)} × {bg(room.height)} "
              f"= {bg(room.area):>6} m²")

    net = sum(room.area for room in ROOMS)
    interior = (HOUSE_LENGTH - 2 * WALL_EXT) * (HOUSE_DEPTH - 2 * WALL_EXT)

    print()
    print(f"  Застроена площ:      {bg(BUILT_AREA)} m²")
    print(f"  Вътрешна (в светли): {bg(interior)} m²")
    print(f"  Чиста използваема:   {bg(net)} m²")

    ok = True
    for key, value in (("built", BUILT_AREA), ("interior", interior), ("net", net)):
        expected = EXPECTED[key]
        if abs(value - expected) > 0.05:
            print(f"  ГРЕШКА: {key} = {bg(value)}, очаквано {bg(expected)}")
            ok = False
    if ok:
        print("\n  ✓ Площите съвпадат с останалите чертежи в проекта.")


# =========================================================================
# 7. ЕКСПОРТ НА ИЗОБРАЖЕНИЕ
# =========================================================================


def export_images(doc, stem: Path) -> None:
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from ezdxf import bbox
        from ezdxf.addons.drawing import Frontend, RenderContext
        from ezdxf.addons.drawing.config import BackgroundPolicy, Configuration
        from ezdxf.addons.drawing.matplotlib import MatplotlibBackend
    except ImportError:
        print("matplotlib не е инсталиран — пропускам експорта на изображения.")
        return

    msp = doc.modelspace()
    extents = bbox.extents(msp)
    width = max(extents.size.x, 1.0)
    height = max(extents.size.y, 1.0)

    fig_width = 12.0
    fig = plt.figure(figsize=(fig_width, fig_width * height / width), facecolor="white")
    ax = fig.add_axes((0.0, 0.0, 1.0, 1.0))

    config = Configuration(background_policy=BackgroundPolicy.WHITE)
    Frontend(RenderContext(doc), MatplotlibBackend(ax), config=config).draw_layout(
        msp, finalize=True
    )

    margin = 0.02 * max(width, height)
    ax.set_aspect("equal", adjustable="box")
    ax.set_xlim(extents.extmin.x - margin, extents.extmax.x + margin)
    ax.set_ylim(extents.extmin.y - margin, extents.extmax.y + margin)
    ax.axis("off")

    png_path, svg_path = stem.with_suffix(".png"), stem.with_suffix(".svg")
    fig.savefig(png_path, dpi=200, facecolor="white")
    fig.savefig(svg_path, facecolor="white")
    plt.close(fig)
    print(f"PNG:  {png_path}")
    print(f"SVG:  {svg_path}")


# =========================================================================
# 8. MAIN
# =========================================================================


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Генерира концептуален план на ICF къща като DXF."
    )
    parser.add_argument("--outdir", type=Path,
                        default=Path(__file__).resolve().parent)
    parser.add_argument("--no-image", action="store_true")
    args = parser.parse_args(argv)

    args.outdir.mkdir(parents=True, exist_ok=True)
    report()

    doc = build_house()
    dxf_path = args.outdir / DXF_NAME
    doc.saveas(dxf_path)
    print(f"\nDXF:  {dxf_path}")

    if not args.no_image:
        export_images(doc, args.outdir / IMAGE_NAME)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

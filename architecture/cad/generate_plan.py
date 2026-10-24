#!/usr/bin/env python3
"""
Концептуален план на едноетажна ICF къща, ~90 m² (вариант „компактен“).

Скриптът чертае план на едно ниво в реални размери (метри) и го записва като DXF.
По желание експортира и изображения (PNG + SVG) чрез matplotlib.

Програма на помещенията
-----------------------
    спалня 1        юг
    спалня 2        юг
    хол + кухня     отворено пространство ≥ 30 m² (изток)
    баня            север
    мокро / килер   север
    коридор         връзка към спалните и мокрите помещения

Слоеве
------
    WALLS       стени (запълнени с плътна hatch)
    DOORS       врати (крило + дъга на отваряне)
    WINDOWS     прозорци и плъзгаща врата
    ROOMS       контури на помещенията + надписи с площ
    DIMENSIONS  размерни вериги, рамка, север

Използване
----------
    python generate_plan.py              # DXF + PNG + SVG
    python generate_plan.py --no-image   # само DXF

Зависимости
-----------
    ezdxf          (задължителна)
    matplotlib     (само за експорт на изображения)

Забележка: това е концептуален чертеж, а не строителен проект.
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

# Windows конзолата често е с кодова страница, различна от UTF-8, което чупи
# кирилицата в print(). Пренастройваме изхода, ако е възможно.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# =========================================================================
# 1. КОНСТАНТИ
# =========================================================================

# --- Външни габарити на сградата (m) -------------------------------------
HOUSE_LENGTH = 12.00            # изток–запад
HOUSE_DEPTH = 7.60              # север–юг

# --- Конструкция ---------------------------------------------------------
WALL_EXT = 0.25                 # дебелина на външната ICF стена
WALL_INT = 0.10                 # дебелина на вътрешна преграда
DOOR_WIDTH = 0.90               # стандартна врата

# --- Вътрешно зониране ---------------------------------------------------
DAY_ZONE_WIDTH = 4.50           # ширина на дневната зона (изток)
NORTH_BAND_DEPTH = 1.90         # баня / мокро помещение (север)
CORRIDOR_DEPTH = 1.05           # коридор

# --- Височини на текстовете (в чертожни единици = m) ---------------------
TEXT_ROOM = 0.19
TEXT_INFO = 0.13
TEXT_DIM = 0.14
TEXT_TITLE = 0.24

# --- Имена на слоеве и изходни файлове -----------------------------------
LAYER_WALLS = "WALLS"
LAYER_DOORS = "DOORS"
LAYER_WINDOWS = "WINDOWS"
LAYER_ROOMS = "ROOMS"
LAYER_DIMENSIONS = "DIMENSIONS"

DXF_NAME = "house.dxf"
IMAGE_NAME = "house"

# Шрифт: TrueType с пълна кирилица и символи (×, ·, ²). Стойността 'txt' (SHX)
# не покрива тези знаци и при експорт се получават празни квадратчета.
TEXT_STYLE = "ICF"
TEXT_FONT = "LiberationSans-Regular.ttf"

# Цветове по ACI (7 = черно/бяло, 8 = сиво, 9 = светло сиво)
COLOR_LINE = 7
COLOR_SOFT = 8
COLOR_WALL_FILL = 9

# =========================================================================
# 2. ИЗЧИСЛЕНА ГЕОМЕТРИЯ
# =========================================================================
# Координатна система: начало – външен югозападен ъгъл, x на изток, y на север.

IN_X0 = WALL_EXT                       # вътрешна повърхност, запад
IN_X1 = HOUSE_LENGTH - WALL_EXT        # вътрешна повърхност, изток
IN_Y0 = WALL_EXT                       # вътрешна повърхност, юг
IN_Y1 = HOUSE_DEPTH - WALL_EXT         # вътрешна повърхност, север

# Разделяне запад (спални/мокри) | изток (дневна зона)
SPLIT_X = IN_X1 - DAY_ZONE_WIDTH       # лява страна на преградата
DAY_X0 = SPLIT_X
DAY_X1 = IN_X1
WEST_X0 = IN_X0
WEST_X1 = SPLIT_X - WALL_INT

# Хоризонтални ленти по дълбочина
NORTH_Y0 = IN_Y1 - NORTH_BAND_DEPTH    # долен ръб на северната лента
CORRIDOR_Y1 = NORTH_Y0 - WALL_INT
CORRIDOR_Y0 = CORRIDOR_Y1 - CORRIDOR_DEPTH
SOUTH_Y1 = CORRIDOR_Y0 - WALL_INT
SOUTH_Y0 = IN_Y0                       # долен ръб на южната лента (спални)

# Вертикална преграда между баня/мокро и между двете спални (една ос)
MID_PART_X0 = WEST_X0 + (WEST_X1 - WEST_X0 - WALL_INT) / 2
MID_PART_X1 = MID_PART_X0 + WALL_INT

# Отвори по фасадите (позиции по дългата ос на стената, в m)
OPENINGS_SOUTH = [(1.20, 2.70), (4.60, 6.10), (8.20, 10.80)]   # 2 прозореца + плъзгаща
OPENINGS_NORTH = [(1.60, 2.20), (4.90, 5.50), (7.90, 9.10)]    # баня, мокро, кухня
OPENINGS_WEST = [(1.60, 2.60)]                                  # спалня 1 (опция)
OPENINGS_EAST = [(3.90, 4.80), (1.40, 2.60)]                    # вход + трапезария


# =========================================================================
# 3. МОДЕЛИ НА ДАННИТЕ
# =========================================================================


@dataclass(frozen=True)
class Room:
    """Правоъгълно помещение, зададено с два срещуположни ъгъла."""

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


# --- Стаи -----------------------------------------------------------------
ROOMS = [
    Room("СПАЛНЯ 1", WEST_X0, SOUTH_Y0, MID_PART_X0, SOUTH_Y1),
    Room("СПАЛНЯ 2", MID_PART_X1, SOUTH_Y0, WEST_X1, SOUTH_Y1),
    Room("КОРИДОР", WEST_X0, CORRIDOR_Y0, WEST_X1, CORRIDOR_Y1),
    Room("БАНЯ", WEST_X0, NORTH_Y0, MID_PART_X0, IN_Y1),
    Room("МОКРО / КИЛЕР", MID_PART_X1, NORTH_Y0, WEST_X1, IN_Y1),
    Room("ХОЛ + ТРАПЕЗАРИЯ", DAY_X0, IN_Y0, DAY_X1, IN_Y1),
]

# --- Стени ----------------------------------------------------------------
WALLS = [
    # външни
    Wall(0.0, 0.0, HOUSE_LENGTH, WALL_EXT, tuple(OPENINGS_SOUTH)),
    Wall(0.0, IN_Y1, HOUSE_LENGTH, HOUSE_DEPTH, tuple(OPENINGS_NORTH)),
    Wall(0.0, WALL_EXT, WALL_EXT, IN_Y1, tuple(OPENINGS_WEST)),
    Wall(IN_X1, WALL_EXT, HOUSE_LENGTH, IN_Y1, tuple(OPENINGS_EAST)),
    # вътрешни
    Wall(SPLIT_X - WALL_INT, WALL_EXT, SPLIT_X, IN_Y1,
         ((CORRIDOR_Y0, CORRIDOR_Y1),)),                     # проход към хола
    Wall(WEST_X0, CORRIDOR_Y1, WEST_X1, NORTH_Y0,
         ((2.40, 3.30), (4.30, 5.20))),                      # врати баня / мокро
    Wall(WEST_X0, SOUTH_Y1, WEST_X1, CORRIDOR_Y0,
         ((0.90, 1.80), (5.30, 6.20))),                      # врати спални
    Wall(MID_PART_X0, SOUTH_Y0, MID_PART_X1, SOUTH_Y1),      # между спалните
    Wall(MID_PART_X0, NORTH_Y0, MID_PART_X1, IN_Y1),         # баня / мокро
]

# --- Врати: (панта, ширина, посока по стената, посока на отваряне) ---------
DOORS = [
    ((IN_X1, 3.90), DOOR_WIDTH, (0.0, 1.0), +1.0),     # входна, отваря се в хола
    ((2.40, NORTH_Y0), DOOR_WIDTH, (1.0, 0.0), +1.0),  # баня
    ((5.20, NORTH_Y0), DOOR_WIDTH, (-1.0, 0.0), -1.0), # мокро помещение
    ((0.90, SOUTH_Y1), DOOR_WIDTH, (1.0, 0.0), -1.0),  # спалня 1
    ((6.20, SOUTH_Y1), DOOR_WIDTH, (-1.0, 0.0), +1.0), # спалня 2
]

# --- Прозорци: (x1, y1, x2, y2, вид) -------------------------------------
WINDOWS = [
    # юг – спални
    (1.20, 0.0, 2.70, WALL_EXT, "window"),
    (4.60, 0.0, 6.10, WALL_EXT, "window"),
    # юг – хол (плъзгаща врата)
    (8.20, 0.0, 10.80, WALL_EXT, "slider"),
    # север – баня, мокро, кухня
    (1.60, IN_Y1, 2.20, HOUSE_DEPTH, "window"),
    (4.90, IN_Y1, 5.50, HOUSE_DEPTH, "window"),
    (7.90, IN_Y1, 9.10, HOUSE_DEPTH, "window"),
    # запад – спалня 1
    (0.0, 1.60, WALL_EXT, 2.60, "window"),
    # изток – трапезария
    (IN_X1, 1.40, HOUSE_LENGTH, 2.60, "window"),
]


# =========================================================================
# 4. ПОМОЩНИ ФУНКЦИИ
# =========================================================================


def bg(value: float, digits: int = 2) -> str:
    """Форматира число с десетична запетая (българска конвенция)."""
    return f"{value:.{digits}f}".replace(".", ",")


def create_layers(doc: ezdxf.document.Drawing) -> None:
    """Създава петте слоя на чертежа с цвят и дебелина на линията."""
    specs = {
        LAYER_WALLS: (COLOR_LINE, 50),
        LAYER_DOORS: (COLOR_LINE, 25),
        LAYER_WINDOWS: (COLOR_LINE, 25),
        LAYER_ROOMS: (COLOR_LINE, 13),
        LAYER_DIMENSIONS: (COLOR_LINE, 13),
    }
    for name, (color, lineweight) in specs.items():
        doc.layers.add(name, color=color, lineweight=lineweight)


def create_text_style(doc: ezdxf.document.Drawing) -> str:
    """Създава текстов стил с TrueType шрифт (кирилица + символи)."""
    doc.styles.add(TEXT_STYLE, font=TEXT_FONT)
    return TEXT_STYLE


def create_dim_style(doc: ezdxf.document.Drawing) -> str:
    """Създава размерен стил в метри (2 знака, запетая за десетичен знак)."""
    name = "ICF"
    style = doc.dimstyles.add(name)
    style.dxf.dimtxsty = TEXT_STYLE  # текстов стил на размера
    style.dxf.dimtxt = TEXT_DIM     # височина на текста
    style.dxf.dimasz = 0.09         # размер на стрелката
    style.dxf.dimexe = 0.08         # продължение на размерната линия
    style.dxf.dimexo = 0.08         # отстъп от обекта
    style.dxf.dimgap = 0.05         # отстъп текст–линия
    style.dxf.dimdec = 2            # два знака след десетичната
    style.dxf.dimzin = 0            # без скриване на нулите (12,00 вместо 12)
    style.dxf.dimdsep = 44          # ASCII 44 = ',' (десетична запетая)
    style.dxf.dimclrt = COLOR_LINE  # цвят на текста
    style.dxf.dimclre = COLOR_LINE  # цвят на размерните линии
    style.dxf.dimtad = 1            # текст над размерната линия
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
    """Поставя единичен надпис с зададено подравняване."""
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
    """Правоъгълник с плътно запълване (използва се за стени)."""
    points = [(x1, y1), (x2, y1), (x2, y2), (x1, y2)]
    msp.add_lwpolyline(points, close=True, dxfattribs={"layer": layer})
    hatch = msp.add_hatch(dxfattribs={"layer": layer})
    hatch.set_solid_fill(color=fill_color)
    hatch.paths.add_polyline_path(points, is_closed=True)


# =========================================================================
# 5. ЧЕРТАНЕ НА ЕЛЕМЕНТИТЕ
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

    Връща
    -----
    Площта на помещението в m².

    Бележка: контурът е затворена полилиния, за да може площта да се измери
    директно в CAD (AREA / MASSPROP).
    """
    if x2 <= x1 or y2 <= y1:
        raise ValueError(f"Некоректни координати за стая „{name}“")

    width, height = x2 - x1, y2 - y1
    area = width * height
    center_x, center_y = (x1 + x2) / 2, (y1 + y2) / 2

    # 1. Затворен контур на помещението
    msp.add_lwpolyline(
        [(x1, y1), (x2, y1), (x2, y2), (x1, y2)],
        close=True,
        dxfattribs={"layer": layer},
    )

    # 2. Надпис: име + (размери · площ). В ниските помещения надписът се
    #    измества нагоре, за да не попада върху дъгата на вратата.
    offset = 0.18 if height < 2.20 else 0.0
    if show_size:
        add_label(msp, center_x, center_y + TEXT_INFO + offset, name, TEXT_ROOM, layer)
        info = f"{bg(width)} × {bg(height)} · {bg(area)} m²"
        add_label(msp, center_x, center_y - TEXT_INFO + offset, info, TEXT_INFO, layer)
    else:
        add_label(msp, center_x, center_y + offset, name, TEXT_ROOM, layer)

    return area


def draw_wall(
    msp: ezdxf.layouts.Modelspace,
    wall: Wall,
    layer: str = LAYER_WALLS,
) -> None:
    """Чертае стена, разделена на плътни сегменти между отворите."""
    if wall.is_horizontal:
        start, end = wall.x1, wall.x2
    else:
        start, end = wall.y1, wall.y2

    # Нормализираме отворите в границите на стената и ги сортираме
    cuts = sorted(
        (max(start, s), min(end, e)) for s, e in wall.openings if e > start and s < end
    )

    cursor = start
    for cut_start, cut_end in cuts:
        if cut_start > cursor:
            _draw_wall_segment(msp, wall, cursor, cut_start, layer)
        cursor = max(cursor, cut_end)
    if cursor < end:
        _draw_wall_segment(msp, wall, cursor, end, layer)


def _draw_wall_segment(
    msp: ezdxf.layouts.Modelspace,
    wall: Wall,
    start: float,
    end: float,
    layer: str,
) -> None:
    """Един непрекъснат участък от стена (без отвори)."""
    if wall.is_horizontal:
        draw_filled_rect(msp, start, wall.y1, end, wall.y2, layer)
    else:
        draw_filled_rect(msp, wall.x1, start, wall.x2, end, layer)


def draw_window(
    msp: ezdxf.layouts.Modelspace,
    x1: float,
    y1: float,
    x2: float,
    y2: float,
    kind: str = "window",
    layer: str = LAYER_WINDOWS,
) -> None:
    """Прозорец или плъзгаща врата в стената (правоъгълник + линии на стъклото)."""
    horizontal = (x2 - x1) >= (y2 - y1)
    msp.add_lwpolyline(
        [(x1, y1), (x2, y1), (x2, y2), (x1, y2)],
        close=True,
        dxfattribs={"layer": layer},
    )

    if horizontal:
        mid = (y1 + y2) / 2
        if kind == "slider":                     # две крила, разминати едно спрямо друго
            half = (x1 + x2) / 2
            msp.add_line((x1, mid - 0.03), (half, mid - 0.03), dxfattribs={"layer": layer})
            msp.add_line((half, mid + 0.03), (x2, mid + 0.03), dxfattribs={"layer": layer})
        else:
            msp.add_line((x1, mid), (x2, mid), dxfattribs={"layer": layer})
    else:
        mid = (x1 + x2) / 2
        msp.add_line((mid, y1), (mid, y2), dxfattribs={"layer": layer})


def draw_door(
    msp: ezdxf.layouts.Modelspace,
    hinge: tuple[float, float],
    width: float,
    along: tuple[float, float],
    side: float,
    layer: str = LAYER_DOORS,
) -> None:
    """
    Чертае врата: крило под 90° и дъга на отваряне.

    hinge : координати на пантата
    width : ширина на вратата
    along : единичен вектор по стената (посока на затвореното крило)
    side  : +1 / -1 – от коя страна на стената се отваря
    """
    ax, ay = along
    # Перпендикуляр на посоката на стената, обърнат според страната
    px, py = -ay * side, ax * side

    leaf_end = (hinge[0] + px * width, hinge[1] + py * width)
    closed_end = (hinge[0] + ax * width, hinge[1] + ay * width)

    msp.add_line(hinge, leaf_end, dxfattribs={"layer": layer})

    start = math.degrees(math.atan2(closed_end[1] - hinge[1], closed_end[0] - hinge[0]))
    end = math.degrees(math.atan2(leaf_end[1] - hinge[1], leaf_end[0] - hinge[0]))
    if round((end - start) % 360) != 90:          # дъгата се чертае обратно на часовника
        start, end = end, start
    msp.add_arc(hinge, width, start, end, dxfattribs={"layer": layer})


def draw_dimensions(
    msp: ezdxf.layouts.Modelspace,
    dimstyle: str,
    layer: str = LAYER_DIMENSIONS,
) -> None:
    """Размерни вериги по стаите + габаритни размери."""
    attributes = {"layer": layer}

    def linear(p1, p2, base, angle=0.0):
        dim = msp.add_linear_dim(
            base=base, p1=p1, p2=p2, angle=angle, dimstyle=dimstyle, dxfattribs=attributes
        )
        dim.render()

    # Хоризонтална верига (над сградата): ширини на стаите.
    # Измервателните точки са на северната фасада, за да не минават
    # удължителните линии през целия план.
    top = HOUSE_DEPTH
    chain_y = HOUSE_DEPTH + 1.05
    linear((WEST_X0, top), (MID_PART_X0, top), (0, chain_y))
    linear((MID_PART_X1, top), (WEST_X1, top), (0, chain_y))
    linear((DAY_X0, top), (DAY_X1, top), (0, chain_y))
    # Габарит по дължина
    linear((0, top), (HOUSE_LENGTH, top), (0, HOUSE_DEPTH + 1.85))

    # Вертикална верига (вляво): дълбочини на лентите
    chain_x = -0.95
    linear((0, SOUTH_Y0), (0, SOUTH_Y1), (chain_x, 0), angle=90)
    linear((0, CORRIDOR_Y0), (0, CORRIDOR_Y1), (chain_x, 0), angle=90)
    linear((0, NORTH_Y0), (0, IN_Y1), (chain_x, 0), angle=90)
    # Габарит по дълбочина
    linear((0, 0), (0, HOUSE_DEPTH), (chain_x - 0.75, 0), angle=90)


def draw_title_block(msp: ezdxf.layouts.Modelspace, layer: str = LAYER_DIMENSIONS) -> None:
    """Рамка с описание на чертежа под плана."""
    x1, y1, x2, y2 = 0.0, -2.85, HOUSE_LENGTH, -1.05
    msp.add_lwpolyline(
        [(x1, y1), (x2, y1), (x2, y2), (x1, y2)], close=True, dxfattribs={"layer": layer}
    )
    msp.add_line((0.0, -1.62), (HOUSE_LENGTH, -1.62), dxfattribs={"layer": layer})

    add_label(
        msp, 0.20, -1.26, "NIKOLAEVO HOUSE — едноетажна ICF къща",
        0.17, layer, TextEntityAlignment.MIDDLE_LEFT,
    )
    add_label(
        msp, 0.20, -1.47, "КОНЦЕПТУАЛЕН ПЛАН — ВАРИАНТ ~90 m²",
        0.12, layer, TextEntityAlignment.MIDDLE_LEFT,
    )
    msp.add_line((9.60, -1.62), (9.60, -1.05), dxfattribs={"layer": layer})
    add_label(
        msp, 9.75, -1.26, "Лист A-02", 0.13, layer, TextEntityAlignment.MIDDLE_LEFT
    )
    add_label(
        msp, 9.75, -1.47, "Мащаб 1:100", 0.13, layer, TextEntityAlignment.MIDDLE_LEFT
    )

    total_net = sum(room.area for room in ROOMS)
    lines = [
        f"Застроена площ {bg(HOUSE_LENGTH * HOUSE_DEPTH)} m² · "
        f"чиста използваема {bg(total_net)} m²",
        f"Външни ICF стени {bg(WALL_EXT)} m · прегради {bg(WALL_INT)} m · "
        f"врати {bg(DOOR_WIDTH)} m · размери в m",
        "Концептуален чертеж за обсъждане. Не е строителен проект.",
    ]
    for index, text in enumerate(lines):
        add_label(
            msp, 0.20, -1.86 - index * 0.22, text, 0.13, layer,
            TextEntityAlignment.MIDDLE_LEFT,
        )


def draw_north_arrow(msp: ezdxf.layouts.Modelspace, layer: str = LAYER_DIMENSIONS) -> None:
    """Стрелка за север (горе = север)."""
    cx, cy, size = 13.15, 6.30, 0.45
    msp.add_lwpolyline(
        [(cx, cy + size), (cx + size * 0.55, cy - size), (cx, cy - size * 0.35),
         (cx - size * 0.55, cy - size)],
        close=True,
        dxfattribs={"layer": layer},
    )
    add_label(msp, cx, cy + size + 0.30, "С", 0.22, layer)


# =========================================================================
# 6. СГЛОБЯВАНЕ НА ЧЕРТЕЖА
# =========================================================================


def build_house() -> ezdxf.document.Drawing:
    """Създава нов DXF документ с целия план."""
    doc = ezdxf.new(dxfversion="R2010", setup=True)
    doc.units = units.M                      # чертожни единици = метри
    doc.header["$LUNITS"] = 2
    doc.header["$LUPREC"] = 2

    create_layers(doc)
    create_text_style(doc)
    dimstyle = create_dim_style(doc)
    msp = doc.modelspace()

    # Редът на чертане определя кой елемент е отгоре
    for room in ROOMS:
        draw_room(msp, room.x1, room.y1, room.x2, room.y2, room.name)

    # Допълнителен надпис за кухненската зона в отвореното пространство
    add_label(
        msp, (DAY_X0 + DAY_X1) / 2, IN_Y1 - 0.85, "КУХНЯ (отворена)",
        TEXT_INFO, LAYER_ROOMS,
    )

    for wall in WALLS:
        draw_wall(msp, wall)

    for x1, y1, x2, y2, kind in WINDOWS:
        draw_window(msp, x1, y1, x2, y2, kind)

    for hinge, width, along, side in DOORS:
        draw_door(msp, hinge, width, along, side)

    add_label(msp, 11.05, 5.35, "ВХОД", TEXT_INFO, LAYER_DOORS)

    draw_dimensions(msp, dimstyle)
    draw_title_block(msp)
    draw_north_arrow(msp)
    return doc


def report() -> None:
    """Отпечатва контролна сметка на площите."""
    print("Помещения:")
    for room in ROOMS:
        print(
            f"  {room.name:<18} {bg(room.width)} × {bg(room.height)} "
            f"= {bg(room.area):>6} m²"
        )
    net = sum(r.area for r in ROOMS)
    day = next(r.area for r in ROOMS if r.name.startswith("ХОЛ"))
    print(f"\n  Чиста площ:      {bg(net)} m²")
    print(f"  Застроена площ:  {bg(HOUSE_LENGTH * HOUSE_DEPTH)} m²")
    print(f"  Хол + кухня:     {bg(day)} m² (изискване ≥ 30,00 m²)")

    if day < 30.0:
        raise SystemExit("ГРЕШКА: хол + кухня е под 30 m²")
    if not 75.0 <= HOUSE_LENGTH * HOUSE_DEPTH <= 99.0:
        raise SystemExit("ГРЕШКА: застроената площ е извън 75–99 m²")


# =========================================================================
# 7. ЕКСПОРТ НА ИЗОБРАЖЕНИЕ
# =========================================================================


def export_images(doc: ezdxf.document.Drawing, stem: Path) -> None:
    """Експортира моделното пространство като PNG и SVG чрез matplotlib."""
    try:
        import matplotlib

        matplotlib.use("Agg")                    # без графичен прозорец
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

    # Бял фон: иначе ACI 7 (черно/бяло) се рендира в бяло и изчезва на белия лист
    config = Configuration(background_policy=BackgroundPolicy.WHITE)
    context = RenderContext(doc)
    backend = MatplotlibBackend(ax)
    Frontend(context, backend, config=config).draw_layout(msp, finalize=True)

    margin = 0.02 * max(width, height)
    ax.set_aspect("equal", adjustable="box")
    ax.set_xlim(extents.extmin.x - margin, extents.extmax.x + margin)
    ax.set_ylim(extents.extmin.y - margin, extents.extmax.y + margin)
    ax.axis("off")

    png_path = stem.with_suffix(".png")
    svg_path = stem.with_suffix(".svg")
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
        description="Генерира концептуален план на ICF къща (~90 m²) като DXF."
    )
    parser.add_argument(
        "--outdir",
        type=Path,
        default=Path(__file__).resolve().parent,
        help="папка за изходните файлове (по подразбиране: папката на скрипта)",
    )
    parser.add_argument(
        "--no-image",
        action="store_true",
        help="без експорт на PNG/SVG (само DXF)",
    )
    args = parser.parse_args(argv)

    outdir: Path = args.outdir
    outdir.mkdir(parents=True, exist_ok=True)

    report()

    doc = build_house()
    dxf_path = outdir / DXF_NAME
    doc.saveas(dxf_path)
    print(f"\nDXF:  {dxf_path}")

    if not args.no_image:
        export_images(doc, outdir / IMAGE_NAME)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

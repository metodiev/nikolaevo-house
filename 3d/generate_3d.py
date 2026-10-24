#!/usr/bin/env python3
"""
Николаево — 3D модел на едноетажната ICF къща.

Геометрията се строи от същите размери, използвани в 2D чертежите:
12,00 × 8,20 m, външни стени 0,35 m, прегради 0,15 / 0,12 m,
височина до стреха 3,00 m, двускатен покрив ~25°.

Координатна система (както в документацията):
    x — на изток  (0 … 12,00)
    y — на юг     (0 …  8,20)
    z — нагоре    (0 = готов под)

Изход:
    house-shell.obj / .mtl   — модел без обзавеждане
    house-full.obj  / .mtl   — модел с обзавеждане
    model-data.json          — геометрия за интерактивния model.html
    images/*.png             — рендери (вън / вътре, с и без обзавеждане)

Стартиране:  python generate_3d.py
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
IMG_DIR = HERE / "images"

# =========================================================================
# 1. РАЗМЕРИ (m)
# =========================================================================

L = 12.00           # дължина изток–запад
D = 8.20            # дълбочина север–юг
T_EXT = 0.35        # външна ICF стена
H_WALL = 3.00       # височина до стреха
PLINTH = 0.35       # кота на терена под готовия под

PITCH_DEG = 25.0    # наклон на покрива (документацията дава 20–30°)
OVERHANG_EAVE = 0.60
OVERHANG_GABLE = 0.50
T_ROOF = 0.20


# =========================================================================
# 2. ЦВЕТОВЕ
# =========================================================================

C_EXT = (0.87, 0.85, 0.81)      # външна мазилка
C_INT = (0.94, 0.93, 0.90)      # вътрешна мазилка
C_SLAB = (0.62, 0.62, 0.60)     # бетон
C_GROUND = (0.72, 0.76, 0.66)   # терен
C_ROOF = (0.56, 0.31, 0.25)     # керемиди
C_CEIL = (0.97, 0.97, 0.96)     # таван
C_GLASS = (0.66, 0.82, 0.88)    # стъкло
C_FRAME = (0.32, 0.34, 0.37)    # профил
C_DOOR = (0.66, 0.50, 0.34)     # дървена врата
C_DOOR_EXT = (0.36, 0.26, 0.20)  # входна врата
C_WOOD_FLOOR = (0.79, 0.66, 0.50)
C_TILE = (0.84, 0.86, 0.87)
C_FURN_WOOD = (0.64, 0.47, 0.32)
C_FURN_LIGHT = (0.86, 0.80, 0.70)
C_FABRIC = (0.52, 0.58, 0.66)
C_BED = (0.93, 0.93, 0.95)
C_WHITE = (0.96, 0.96, 0.96)
C_DARK = (0.18, 0.19, 0.21)
C_METAL = (0.70, 0.72, 0.74)
C_RUG = (0.72, 0.66, 0.60)
C_PLANT = (0.36, 0.52, 0.30)
C_VWOOD = (0.58, 0.40, 0.26)     # дървена конструкция на верандата
C_VROOF = (0.30, 0.33, 0.32)     # покрив на верандата
C_VDECK = (0.70, 0.55, 0.40)     # под на верандата

MATERIALS = {
    "vanshna-mazilka": C_EXT,
    "vatreshna-mazilka": C_INT,
    "beton": C_SLAB,
    "teren": C_GROUND,
    "keremidi": C_ROOF,
    "tavan": C_CEIL,
    "stuklo": C_GLASS,
    "profil": C_FRAME,
    "vrata": C_DOOR,
    "vhodna-vrata": C_DOOR_EXT,
    "pod-darvo": C_WOOD_FLOOR,
    "pod-plochki": C_TILE,
    "mebel-darvo": C_FURN_WOOD,
    "mebel-svetal": C_FURN_LIGHT,
    "tapiceria": C_FABRIC,
    "leglo": C_BED,
    "byalo": C_WHITE,
    "tyomno": C_DARK,
    "metal": C_METAL,
    "kilim": C_RUG,
    "rasteanie": C_PLANT,
    "veranda-darvo": C_VWOOD,
    "veranda-pokriv": C_VROOF,
    "veranda-pod": C_VDECK,
}
MAT_BY_RGB = {v: k for k, v in MATERIALS.items()}


# =========================================================================
# 3. МОДЕЛ
# =========================================================================


@dataclass
class Model:
    """Списък от четириъгълници с цвят и група."""

    faces: list = field(default_factory=list)
    clip_z: float = 10.0

    def quad(self, a, b, c, d, colour, group="steni"):
        self.faces.append(([a, b, c, d], colour, group))

    def tri(self, a, b, c, colour, group="steni"):
        self.faces.append(([a, b, c], colour, group))

    def box(self, x1, y1, z1, x2, y2, z2, colour, group="steni"):
        """Правоъгълен паралелепипед с външно ориентирани нормали."""
        x1, x2 = min(x1, x2), max(x1, x2)
        y1, y2 = min(y1, y2), max(y1, y2)
        z1, z2 = min(z1, z2), max(z1, z2)
        z2 = min(z2, self.clip_z)
        if z2 - z1 < 1e-4 or x2 - x1 < 1e-4 or y2 - y1 < 1e-4:
            return
        p = lambda x, y, z: (x, y, z)
        self.quad(p(x1, y1, z1), p(x1, y2, z1), p(x2, y2, z1), p(x2, y1, z1), colour, group)
        self.quad(p(x1, y1, z2), p(x2, y1, z2), p(x2, y2, z2), p(x1, y2, z2), colour, group)
        self.quad(p(x1, y1, z1), p(x1, y1, z2), p(x1, y2, z2), p(x1, y2, z1), colour, group)
        self.quad(p(x2, y1, z1), p(x2, y2, z1), p(x2, y2, z2), p(x2, y1, z2), colour, group)
        self.quad(p(x1, y1, z1), p(x2, y1, z1), p(x2, y1, z2), p(x1, y1, z2), colour, group)
        self.quad(p(x2, y2, z1), p(x1, y2, z1), p(x1, y2, z2), p(x2, y2, z2), colour, group)

    def prism_x(self, poly, x1, x2, colour, group="pokriv"):
        """Призма по полигон в равнината (y, z), изтеглена по x."""
        x1, x2 = min(x1, x2), max(x1, x2)
        area = 0.0
        n = len(poly)
        for i in range(n):
            y1, z1 = poly[i]
            y2, z2 = poly[(i + 1) % n]
            area += y1 * z2 - y2 * z1
        pts = list(poly) if area > 0 else list(reversed(poly))
        for i in range(len(pts)):
            y1, z1 = pts[i]
            y2, z2 = pts[(i + 1) % len(pts)]
            self.quad((x2, y1, z1), (x1, y1, z1), (x1, y2, z2), (x2, y2, z2), colour, group)
        for xcap, flip in ((x1, True), (x2, False)):
            cap = [(xcap, y, z) for y, z in pts]
            if flip:
                cap = list(reversed(cap))
            for i in range(1, len(cap) - 1):
                self.tri(cap[0], cap[i], cap[i + 1], colour, group)

    def prism_y(self, poly, y1, y2, colour, group="pokriv"):
        """Призма по полигон в равнината (x, z), изтеглена по y."""
        y1, y2 = min(y1, y2), max(y1, y2)
        area = 0.0
        n = len(poly)
        for i in range(n):
            x1, z1 = poly[i]
            x2, z2 = poly[(i + 1) % n]
            area += x1 * z2 - x2 * z1
        pts = list(poly) if area > 0 else list(reversed(poly))
        for i in range(len(pts)):
            x1, z1 = pts[i]
            x2, z2 = pts[(i + 1) % len(pts)]
            self.quad((x1, y2, z1), (x1, y1, z1), (x2, y1, z2), (x2, y2, z2), colour, group)
        for ycap, flip in ((y1, False), (y2, True)):
            cap = [(x, ycap, z) for x, z in pts]
            if flip:
                cap = list(reversed(cap))
            for i in range(1, len(cap) - 1):
                self.tri(cap[0], cap[i], cap[i + 1], colour, group)

    def plate(self, x1, y1, x2, y2, z, colour, group="pod", t=0.012):
        self.box(x1, y1, z, x2, y2, z + t, colour, group)

    def wall_x(self, x1, x2, y1, y2, openings, colour, group="steni", z_top=H_WALL):
        """Стена по оста x с правоъгълни отвори (x1, x2, z1, z2)."""
        cursor = x1
        for ox1, ox2, oz1, oz2 in sorted(openings):
            if ox1 - cursor > 1e-4:
                self.box(cursor, y1, 0, ox1, y2, z_top, colour, group)
            if oz1 > 1e-4:
                self.box(ox1, y1, 0, ox2, y2, oz1, colour, group)
            if oz2 < z_top - 1e-4:
                self.box(ox1, y1, oz2, ox2, y2, z_top, colour, group)
            cursor = ox2
        if x2 - cursor > 1e-4:
            self.box(cursor, y1, 0, x2, y2, z_top, colour, group)

    def wall_y(self, y1, y2, x1, x2, openings, colour, group="steni", z_top=H_WALL):
        """Стена по оста y с правоъгълни отвори (y1, y2, z1, z2)."""
        cursor = y1
        for oy1, oy2, oz1, oz2 in sorted(openings):
            if oy1 - cursor > 1e-4:
                self.box(x1, cursor, 0, x2, oy1, z_top, colour, group)
            if oz1 > 1e-4:
                self.box(x1, oy1, 0, x2, oy2, oz1, colour, group)
            if oz2 < z_top - 1e-4:
                self.box(x1, oy1, oz2, x2, oy2, z_top, colour, group)
            cursor = oy2
        if y2 - cursor > 1e-4:
            self.box(x1, cursor, 0, x2, y2, z_top, colour, group)


# =========================================================================
# 4. ОТВОРИ (от architecture/03-openings.md)
# =========================================================================

# Прозорци: (код, стена, u1, u2, подпрозорец, горен ръб)
WINDOWS = [
    ("П1", "юг", 1.175, 2.675, 0.80, 2.20),
    ("П2", "юг", 4.475, 5.975, 0.80, 2.20),
    ("П3", "юг", 7.900, 10.700, 0.00, 2.25),      # плъзгаща врата
    ("П4", "север", 7.690, 8.890, 1.00, 2.40),
    ("П5", "север", 1.625, 2.225, 1.60, 2.20),
    ("П6", "север", 4.925, 5.525, 1.50, 2.10),
    ("П7", "изток", 3.500, 5.100, 0.80, 2.20),
    ("П8", "запад", 5.200, 6.200, 0.80, 2.20),
    ("П9", "изток", 5.900, 7.300, 0.80, 2.20),        # хол, югоизток
]

# Врати: (код, стена, u1, u2, горен ръб)
DOORS = [
    ("В1", "изток", 0.700, 1.750, 2.10),
    ("В2", "антре", 10.400, 11.300, 2.10),
    ("В3", "коридор", 0.900, 1.800, 2.00),
    ("В4", "коридор", 4.700, 5.600, 2.00),
    ("В5", "коридор", 2.200, 3.100, 2.00),
    ("В6", "коридор", 3.800, 4.700, 2.00),
]


def add_openings(m: Model) -> None:
    """Стъкло и профил за прозорците, крило за вратите."""
    gap = 0.055
    for _code, wall, u1, u2, sill, head in WINDOWS:
        if wall in ("юг", "север"):
            yc = (D - T_EXT / 2) if wall == "юг" else T_EXT / 2
            if sill <= 0.001:                       # плъзгаща врата — цяло стъкло
                m.box(u1, yc - gap, 0.0, u2, yc + gap, 0.06, C_FRAME, "dograma")
                m.box(u1, yc - gap, head - 0.06, u2, yc + gap, head, C_FRAME, "dograma")
                m.box(u1, yc - gap, 0.0, u1 + 0.06, yc + gap, head, C_FRAME, "dograma")
                m.box(u2 - 0.06, yc - gap, 0.0, u2, yc + gap, head, C_FRAME, "dograma")
                m.box(u1 + 0.06, yc - 0.015, 0.06, u2 - 0.06, yc + 0.015,
                      head - 0.06, C_GLASS, "dograma")
            else:
                m.box(u1, yc - gap, sill, u2, yc + gap, sill + 0.06, C_FRAME, "dograma")
                m.box(u1, yc - gap, head - 0.06, u2, yc + gap, head, C_FRAME, "dograma")
                m.box(u1, yc - gap, sill, u1 + 0.06, yc + gap, head, C_FRAME, "dograma")
                m.box(u2 - 0.06, yc - gap, sill, u2, yc + gap, head, C_FRAME, "dograma")
                m.box(u1 + 0.06, yc - 0.015, sill + 0.06,
                      u2 - 0.06, yc + 0.015, head - 0.06, C_GLASS, "dograma")
        else:
            xc = (L - T_EXT / 2) if wall == "изток" else T_EXT / 2
            m.box(xc - gap, u1, sill, xc + gap, u2, sill + 0.06, C_FRAME, "dograma")
            m.box(xc - gap, u1, head - 0.06, xc + gap, u2, head, C_FRAME, "dograma")
            m.box(xc - gap, u1, sill, xc + gap, u1 + 0.06, head, C_FRAME, "dograma")
            m.box(xc - gap, u2 - 0.06, sill, xc + gap, u2, head, C_FRAME, "dograma")
            m.box(xc - 0.015, u1 + 0.06, sill + 0.06,
                  xc + 0.015, u2 - 0.06, head - 0.06, C_GLASS, "dograma")

    for code, wall, u1, u2, head in DOORS:
        colour = C_DOOR_EXT if code == "В1" else C_DOOR
        if wall == "изток":
            xc = L - T_EXT / 2
            m.box(xc - 0.03, u1, 0, xc + 0.03, u2, head, colour, "dograma")
        elif wall == "антре":
            m.box(u1, 2.48, 0, u2, 2.54, head, colour, "dograma")
        else:
            m.box(u1, 3.645, 0, u2, 3.705, head, colour, "dograma")


# =========================================================================
# 5. ОБЗАВЕЖДАНЕ
# =========================================================================


def chair(m: Model, x, y, side):
    """Стол 450 × 450 с облегалка от страната `side`."""
    s = 0.45
    m.box(x, y, 0.42, x + s, y + s, 0.46, C_FURN_WOOD, "mebel")
    if side == "N":
        m.box(x, y, 0.46, x + s, y + 0.06, 0.92, C_FURN_WOOD, "mebel")
    elif side == "S":
        m.box(x, y + s - 0.06, 0.46, x + s, y + s, 0.92, C_FURN_WOOD, "mebel")
    elif side == "W":
        m.box(x, y, 0.46, x + 0.06, y + s, 0.92, C_FURN_WOOD, "mebel")
    else:
        m.box(x + s - 0.06, y, 0.46, x + s, y + s, 0.92, C_FURN_WOOD, "mebel")
    for dx, dy in ((0.03, 0.03), (s - 0.08, 0.03), (0.03, s - 0.08), (s - 0.08, s - 0.08)):
        m.box(x + dx, y + dy, 0, x + dx + 0.05, y + dy + 0.05, 0.42, C_FURN_WOOD, "mebel")


def table(m: Model, x, y, w, d, h=0.75):
    m.box(x, y, h - 0.04, x + w, y + d, h, C_FURN_WOOD, "mebel")
    for dx, dy in ((0.06, 0.06), (w - 0.11, 0.06), (0.06, d - 0.11), (w - 0.11, d - 0.11)):
        m.box(x + dx, y + dy, 0, x + dx + 0.05, y + dy + 0.05, h - 0.04, C_FURN_WOOD, "mebel")


def fill_day(m: Model) -> None:
    """Кухня, трапезария и хол."""
    m.box(6.95, 0.35, 0, 8.90, 0.95, 0.88, C_FURN_LIGHT, "mebel")
    m.box(6.95, 0.95, 0, 7.55, 2.45, 0.88, C_FURN_LIGHT, "mebel")
    m.box(6.94, 0.34, 0.88, 8.91, 0.96, 0.92, C_METAL, "mebel")
    m.box(6.94, 0.94, 0.88, 7.56, 2.46, 0.92, C_METAL, "mebel")
    m.box(7.70, 0.42, 0.92, 8.40, 0.90, 0.94, C_DARK, "mebel")
    m.box(7.02, 1.62, 0.92, 7.52, 2.12, 0.94, C_DARK, "mebel")
    m.box(8.95, 0.35, 0, 9.60, 1.05, 1.90, C_WHITE, "mebel")
    m.box(6.95, 0.35, 1.45, 8.90, 0.66, 2.20, C_FURN_LIGHT, "mebel")
    m.box(6.95, 0.95, 1.45, 7.25, 2.45, 2.20, C_FURN_LIGHT, "mebel")

    table(m, 7.50, 4.08, 1.40, 0.90)
    for cx in (7.78, 8.17):
        chair(m, cx, 3.56, "N")
        chair(m, cx, 5.05, "S")
    chair(m, 6.98, 4.31, "W")
    chair(m, 8.97, 4.31, "E")

    m.box(6.95, 5.00, 0, 7.35, 6.65, 0.45, C_FURN_WOOD, "mebel")
    m.box(6.97, 5.10, 1.00, 7.03, 6.50, 1.80, C_DARK, "mebel")
    m.box(9.48, 4.70, 0, 10.38, 6.90, 0.42, C_FABRIC, "mebel")
    m.box(10.14, 4.70, 0.42, 10.38, 6.90, 0.86, C_FABRIC, "mebel")
    m.box(9.48, 4.70, 0.42, 10.16, 4.90, 0.62, C_FABRIC, "mebel")
    m.box(9.48, 6.70, 0.42, 10.16, 6.90, 0.62, C_FABRIC, "mebel")
    m.box(9.52, 4.92, 0.42, 10.14, 5.78, 0.50, C_FABRIC, "mebel")
    m.box(9.52, 5.82, 0.42, 10.14, 6.68, 0.50, C_FABRIC, "mebel")
    m.box(10.48, 5.15, 0, 11.33, 6.00, 0.42, C_FABRIC, "mebel")
    m.box(11.13, 5.15, 0.42, 11.33, 6.00, 0.84, C_FABRIC, "mebel")
    m.box(8.20, 5.60, 0.36, 9.30, 6.20, 0.40, C_FURN_WOOD, "mebel")
    for dx, dy in ((0.05, 0.05), (1.05, 0.05), (0.05, 0.55), (1.05, 0.55)):
        m.box(8.20 + dx, 5.60 + dy, 0, 8.25 + dx, 5.65 + dy, 0.36, C_FURN_WOOD, "mebel")
    m.plate(7.80, 5.50, 9.90, 7.00, 0.014, C_RUG, "mebel", t=0.008)
    m.box(11.25, 7.50, 0, 11.63, 7.83, 0.40, C_FURN_WOOD, "mebel")
    m.box(11.30, 7.55, 0.40, 11.58, 7.78, 1.30, C_PLANT, "mebel")


def fill_bed1(m: Model) -> None:
    m.box(1.90, 3.75, 0, 3.50, 4.30, 2.35, C_FURN_LIGHT, "mebel")
    m.box(1.50, 4.75, 0.10, 3.50, 6.35, 0.35, C_FURN_WOOD, "mebel")
    m.box(1.52, 4.77, 0.35, 3.42, 6.33, 0.58, C_BED, "mebel")
    m.box(3.41, 4.75, 0.10, 3.50, 6.35, 1.10, C_FURN_WOOD, "mebel")
    m.box(3.00, 4.85, 0.58, 3.40, 5.43, 0.72, C_WHITE, "mebel")
    m.box(3.00, 5.67, 0.58, 3.40, 6.25, 0.72, C_WHITE, "mebel")
    m.box(1.52, 4.77, 0.58, 2.60, 6.33, 0.64, C_FABRIC, "mebel")
    m.box(3.05, 4.35, 0, 3.50, 4.75, 0.50, C_FURN_WOOD, "mebel")
    m.box(3.05, 6.35, 0, 3.50, 6.75, 0.50, C_FURN_WOOD, "mebel")
    m.plate(0.55, 4.95, 1.25, 6.15, 0.014, C_RUG, "mebel", t=0.008)


def fill_bed2(m: Model) -> None:
    m.box(5.60, 3.75, 0, 6.80, 4.30, 2.35, C_FURN_LIGHT, "mebel")
    m.box(3.65, 4.90, 0.10, 5.65, 6.50, 0.35, C_FURN_WOOD, "mebel")
    m.box(3.73, 4.92, 0.35, 5.63, 6.48, 0.58, C_BED, "mebel")
    m.box(3.65, 4.90, 0.10, 3.74, 6.50, 1.10, C_FURN_WOOD, "mebel")
    m.box(3.75, 5.00, 0.58, 4.15, 5.58, 0.72, C_WHITE, "mebel")
    m.box(3.75, 5.82, 0.58, 4.15, 6.40, 0.72, C_WHITE, "mebel")
    m.box(4.25, 4.92, 0.58, 5.63, 6.48, 0.64, C_FABRIC, "mebel")
    m.box(3.65, 4.45, 0, 4.05, 4.90, 0.50, C_FURN_WOOD, "mebel")
    m.box(3.65, 6.50, 0, 4.05, 6.95, 0.50, C_FURN_WOOD, "mebel")


def fill_bath(m: Model) -> None:
    m.box(0.40, 0.40, 0, 1.55, 1.25, 0.10, C_WHITE, "mebel")
    m.box(1.52, 0.40, 0.10, 1.56, 1.25, 2.00, C_GLASS, "mebel")
    m.box(0.40, 1.30, 0, 1.20, 1.75, 0.42, C_WHITE, "mebel")
    m.box(0.40, 1.02, 0.42, 1.20, 1.32, 0.85, C_WHITE, "mebel")
    m.box(1.00, 1.82, 0, 2.00, 2.32, 0.82, C_FURN_LIGHT, "mebel")
    m.box(1.00, 1.82, 0.82, 2.00, 2.32, 0.88, C_WHITE, "mebel")
    m.box(1.55, 0.50, 0.10, 1.60, 1.20, 0.70, C_METAL, "mebel")


def fill_wet(m: Model) -> None:
    m.box(3.65, 0.35, 0, 4.25, 0.95, 0.85, C_WHITE, "mebel")
    m.box(4.30, 0.35, 0, 4.90, 0.95, 0.85, C_WHITE, "mebel")
    m.box(5.50, 0.35, 0, 6.80, 0.95, 0.88, C_FURN_LIGHT, "mebel")
    m.box(5.70, 0.42, 0.88, 6.20, 0.90, 0.93, C_METAL, "mebel")
    m.box(3.65, 1.00, 0, 4.05, 1.40, 1.80, C_FURN_LIGHT, "mebel")
    m.box(6.15, 1.50, 1.20, 6.75, 2.10, 1.95, C_WHITE, "mebel")


def fill_entry(m: Model) -> None:
    m.box(9.75, 0.50, 0, 10.15, 1.40, 2.20, C_FURN_LIGHT, "mebel")
    m.box(9.75, 1.60, 0, 10.20, 2.10, 0.45, C_FURN_WOOD, "mebel")
    m.box(9.85, 2.43, 1.40, 10.35, 2.47, 1.80, C_DARK, "mebel")


# =========================================================================
# 6. СГЛОБЯВАНЕ НА КЪЩАТА
# =========================================================================

ROOMS_FLOOR = [
    (0.35, 0.35, 3.50, 2.35, C_TILE),
    (3.65, 0.35, 6.80, 2.35, C_TILE),
    (0.35, 2.50, 6.80, 3.60, C_WOOD_FLOOR),
    (0.35, 3.75, 3.50, 7.85, C_WOOD_FLOOR),
    (3.65, 3.75, 6.80, 7.85, C_WOOD_FLOOR),
    (6.95, 0.35, 9.63, 2.57, C_TILE),
    (9.75, 0.35, 11.65, 2.45, C_TILE),
    (6.95, 2.57, 11.65, 7.85, C_WOOD_FLOOR),
]

PARTITIONS = [
    ("x", 0.35, 2.20, 2.35, 2.50),
    ("x", 3.10, 3.80, 2.35, 2.50),
    ("x", 4.70, 6.80, 2.35, 2.50),
    ("x", 0.35, 0.90, 3.60, 3.75),
    ("x", 1.80, 4.70, 3.60, 3.75),
    ("x", 5.60, 6.80, 3.60, 3.75),
    ("y", 0.35, 2.35, 3.50, 3.65),
    ("y", 3.75, 7.85, 3.50, 3.65),
    ("y", 0.35, 2.50, 6.80, 6.95),
    ("y", 3.60, 7.85, 6.80, 6.95),
    ("y", 0.35, 2.45, 9.63, 9.75),
    ("x", 9.63, 10.40, 2.45, 2.57),
    ("x", 11.30, 11.65, 2.45, 2.57),
]

HEADERS = [
    (2.20, 3.10, 2.35, 2.50, 2.00),
    (3.80, 4.70, 2.35, 2.50, 2.00),
    (0.90, 1.80, 3.60, 3.75, 2.00),
    (4.70, 5.60, 3.60, 3.75, 2.00),
    (10.40, 11.30, 2.45, 2.57, 2.10),
    (6.80, 6.95, 2.50, 3.60, 2.10),
]


def build_model(furniture: bool = True, clip_z: float = 10.0,
                veranda: bool = True) -> Model:
    m = Model(clip_z=clip_z)

    m.box(-30.0, -30.0, -PLINTH - 0.08, L + 30.0, D + 30.0, -PLINTH, C_GROUND, "osnova")
    m.box(0, 0, -PLINTH, L, D, 0.0, C_SLAB, "osnova")

    for x1, y1, x2, y2, col in ROOMS_FLOOR:
        m.plate(x1, y1, x2, y2, 0.0, col, "pod", t=0.010)

    south = [(u1, u2, s, h) for _c, w, u1, u2, s, h in WINDOWS if w == "юг"]
    north = [(u1, u2, s, h) for _c, w, u1, u2, s, h in WINDOWS if w == "север"]
    west = [(u1, u2, s, h) for _c, w, u1, u2, s, h in WINDOWS if w == "запад"]
    east_w = [(u1, u2, s, h) for _c, w, u1, u2, s, h in WINDOWS if w == "изток"]
    east_d = [(u1, u2, 0.0, h) for _c, w, u1, u2, h in DOORS if w == "изток"]

    m.wall_x(0.0, L, D - T_EXT, D, south, C_EXT)
    m.wall_x(0.0, L, 0.0, T_EXT, north, C_EXT)
    m.wall_y(0.0, D, 0.0, T_EXT, west, C_EXT)
    m.wall_y(0.0, D, L - T_EXT, L, east_w + east_d, C_EXT)

    for axis, a1, a2, b1, b2 in PARTITIONS:
        if axis == "x":
            m.box(a1, b1, 0, a2, b2, H_WALL, C_INT, "steni")
        else:
            m.box(b1, a1, 0, b2, a2, H_WALL, C_INT, "steni")
    for x1, x2, y1, y2, z1 in HEADERS:
        m.box(x1, y1, z1, x2, y2, H_WALL, C_INT, "steni")

    add_openings(m)

    if clip_z > H_WALL + 0.01:
        tan = math.tan(math.radians(PITCH_DEG))
        rise = (D / 2) * tan
        z_ridge = H_WALL + rise
        y_ridge = D / 2
        y_eave_s = D + OVERHANG_EAVE
        y_eave_n = -OVERHANG_EAVE
        z_eave = H_WALL - OVERHANG_EAVE * tan
        x1, x2 = -OVERHANG_GABLE, L + OVERHANG_GABLE

        south_slope = [(y_eave_s, z_eave), (y_ridge, z_ridge),
                       (y_ridge, z_ridge + T_ROOF), (y_eave_s, z_eave + T_ROOF)]
        north_slope = [(y_ridge, z_ridge), (y_eave_n, z_eave),
                       (y_eave_n, z_eave + T_ROOF), (y_ridge, z_ridge + T_ROOF)]
        m.prism_x(south_slope, x1, x2, C_ROOF, "pokriv")
        m.prism_x(north_slope, x1, x2, C_ROOF, "pokriv")

        # фронтони — леко над равнината на покрива, за да влязат в плочата
        # (припокриване вместо съвпадащи повърхности → без z-fighting)
        gable = [(0.0, H_WALL), (D, H_WALL), (y_ridge, z_ridge + 0.05)]
        m.prism_x(gable, 0.0, T_EXT, C_EXT, "pokriv")
        m.prism_x(gable, L - T_EXT, L, C_EXT, "pokriv")

        m.box(0.0, 0.0, H_WALL, L, D, H_WALL + 0.05, C_CEIL, "tavan")

    if veranda:
        build_veranda(m)

    if furniture:
        fill_day(m)
        fill_bed1(m)
        fill_bed2(m)
        fill_bath(m)
        fill_wet(m)
        fill_entry(m)
        if veranda:
            fill_veranda(m)

    return m


# =========================================================================
# 6. ВЕРАНДА (изток) — отворена, по цялата дължина на къщата
# =========================================================================

V_Y0 = 0.00            # от северния ъгъл…
V_Y1 = D               # …до южния (8,20)
V_LEN = V_Y1 - V_Y0
V_X0 = L               # 12,00 — плътно до къщата
V_DEPTH = 1.80
V_X1 = V_X0 + V_DEPTH  # 13,80
V_Z_HOUSE = 2.90       # долна страна на покрива при къщата
V_Z_EDGE = 2.45        # долна страна на покрива при x = 14,10
V_ROOF_X = 14.10
V_ROOF_T = 0.12
V_POST = 0.10
V_RAIL = 1.00          # височина на парапета
V_RAIL_FROM = 2.30     # парапетът започва след входа


def v_top(x: float) -> float:
    """Височина на подпорите при дадено x (под покрива)."""
    return V_Z_HOUSE + (x - V_X0) * (V_Z_EDGE - V_Z_HOUSE) / (V_ROOF_X - V_X0)


def build_veranda(m: Model) -> None:
    """Отворена дървена веранда 1,80 × 8,20 m по източната фасада."""
    # под — дървена скара, малко под котата на къщата
    m.box(V_X0, V_Y0, -0.08, V_X1, V_Y1, 0.02, C_VDECK, "veranda")

    # стъпало при входа (северния край)
    m.box(V_X1, 0.20, -0.34, V_X1 + 0.55, 1.90, -0.08, C_VWOOD, "veranda")

    # подпори
    posts_y = (0.06, 2.10, 4.10, 6.10, D - 0.16)
    for y in posts_y:
        m.box(V_X1 - V_POST - 0.04, y, 0.02, V_X1 - 0.04, y + V_POST,
              v_top(V_X1 - V_POST / 2 - 0.04), C_VWOOD, "veranda")

    # парапет по външния ръб (след входа на север)
    xr = V_X1 - V_POST / 2 - 0.04
    m.box(xr - 0.04, V_RAIL_FROM, V_RAIL - 0.06, xr + 0.04, V_Y1 - 0.06,
          V_RAIL, C_VWOOD, "veranda")
    m.box(xr - 0.04, V_RAIL_FROM, 0.10, xr + 0.04, V_Y1 - 0.06,
          0.18, C_VWOOD, "veranda")
    n = max(1, int((V_Y1 - 0.06 - V_RAIL_FROM) / 0.95))
    for i in range(1, n):
        y = V_RAIL_FROM + i * (V_Y1 - 0.06 - V_RAIL_FROM) / n
        m.box(xr - 0.025, y - 0.025, 0.18, xr + 0.025, y + 0.025,
              V_RAIL - 0.06, C_VWOOD, "veranda")

    if m.clip_z < 1.5:
        return

    # покрив — собствена едноскатна плоскост, под стрехата на къщата
    poly = [(V_X0 - 0.10, v_top(V_X0 - 0.10)), (V_ROOF_X, v_top(V_ROOF_X)),
            (V_ROOF_X, v_top(V_ROOF_X) + V_ROOF_T),
            (V_X0 - 0.10, v_top(V_X0 - 0.10) + V_ROOF_T)]
    m.prism_y(poly, V_Y0 - 0.28, V_Y1 + 0.28, C_VROOF, "vroof")


def fill_veranda(m: Model) -> None:
    """Пейка до стената на къщата."""
    m.box(V_X0 + 0.04, 5.90, 0.02, V_X0 + 0.48, 7.40, 0.42, C_VWOOD, "mebel")
    m.box(V_X0 + 0.02, 5.90, 0.42, V_X0 + 0.52, 7.40, 0.48, C_VDECK, "mebel")


# =========================================================================
# 7. РЕНДЕР (софтуерен z-buffer)
# =========================================================================

LIGHT_KEY = np.array([-0.30, 0.55, 0.78])
LIGHT_KEY /= np.linalg.norm(LIGHT_KEY)
LIGHT_FILL = np.array([0.62, -0.35, 0.70])
LIGHT_FILL /= np.linalg.norm(LIGHT_FILL)

AMBIENT = 0.34
K_KEY = 0.46
K_FILL = 0.26


def render(model: Model, eye, target, up=(0, 0, 1), size=(1500, 950),
           fov=42.0, bg=(0.963, 0.965, 0.972), hide=(), super_sample=2,
           ambient=AMBIENT, k_key=K_KEY, k_fill=K_FILL):
    """Плоско осветен рендер със z-buffer; връща PIL.Image."""
    W, H = size
    SW, SH = W * super_sample, H * super_sample
    eye_v = np.asarray(eye, float)
    target_v = np.asarray(target, float)
    f = target_v - eye_v
    f /= np.linalg.norm(f)
    r = np.cross(np.asarray(up, float), f)
    r /= np.linalg.norm(r)
    u = np.cross(f, r)
    fpx = (SH / 2.0) / math.tan(math.radians(fov) / 2.0)

    img = np.empty((SH, SW, 3), dtype=np.float32)
    img[:, :] = np.array(bg, dtype=np.float32)
    zbuf = np.full((SH, SW), np.inf, dtype=np.float64)

    for pts, colour, group in model.faces:
        if group in hide:
            continue
        world = [np.array(p, float) for p in pts]
        cam = []
        for p in world:
            d = p - eye_v
            cam.append((float(d @ r), float(d @ u), float(d @ f)))
        if all(c[2] < 0.05 for c in cam):
            continue

        n = np.cross(world[1] - world[0], world[2] - world[0])
        ln = np.linalg.norm(n)
        if ln < 1e-12:
            continue
        n /= ln
        centroid = sum(world) / len(world)
        if float(n @ (eye_v - centroid)) < 0:
            n = -n
        shade = (ambient
                 + k_key * max(0.0, float(n @ LIGHT_KEY))
                 + k_fill * max(0.0, float(n @ LIGHT_FILL)))
        if group == "tavan":
            shade = max(shade, 0.93)
        shade = min(shade, 0.95)
        col = np.clip(np.array(colour, float) * shade, 0.0, 1.0)

        poly = _clip_near(cam)
        if len(poly) < 3:
            continue
        screen = []
        for x, y, z in poly:
            screen.append((SW / 2.0 + fpx * x / z, SH / 2.0 - fpx * y / z, z))

        for i in range(1, len(screen) - 1):
            _raster(img, zbuf, screen[0], screen[i], screen[i + 1], col)

    im = Image.fromarray((np.clip(img, 0, 1) * 255).astype(np.uint8), "RGB")
    if super_sample > 1:
        im = im.resize((W, H), Image.LANCZOS)
    return im


def _clip_near(pts, near=0.05):
    out = []
    n = len(pts)
    for i in range(n):
        a = pts[i]
        b = pts[(i + 1) % n]
        ina = a[2] >= near
        if ina:
            out.append(a)
        if ina != (b[2] >= near):
            t = (near - a[2]) / (b[2] - a[2])
            out.append((a[0] + t * (b[0] - a[0]),
                        a[1] + t * (b[1] - a[1]),
                        near))
    return out


def _raster(img, zbuf, p0, p1, p2, col, band=192):
    SH, SW = zbuf.shape
    x0, y0, z0 = p0
    x1, y1, z1 = p1
    x2, y2, z2 = p2
    if z0 < 1e-6 or z1 < 1e-6 or z2 < 1e-6:
        return
    minx = max(int(math.floor(min(x0, x1, x2))), 0)
    maxx = min(int(math.ceil(max(x0, x1, x2))), SW - 1)
    miny = max(int(math.floor(min(y0, y1, y2))), 0)
    maxy = min(int(math.ceil(max(y0, y1, y2))), SH - 1)
    if maxx < minx or maxy < miny:
        return
    den = (y1 - y2) * (x0 - x2) + (x2 - x1) * (y0 - y2)
    if abs(den) < 1e-9:
        return
    xs = np.arange(minx, maxx + 1, dtype=np.float64)[None, :]
    # големите триъгълници се обработват на ивици, за да не се вдига паметта
    for ys0 in range(miny, maxy + 1, band):
        ys1 = min(ys0 + band - 1, maxy)
        ys = np.arange(ys0, ys1 + 1, dtype=np.float64)[:, None]
        w0 = ((y1 - y2) * (xs - x2) + (x2 - x1) * (ys - y2)) / den
        w1 = ((y2 - y0) * (xs - x2) + (x0 - x2) * (ys - y2)) / den
        w2 = 1.0 - w0 - w1
        mask = (w0 >= -1e-9) & (w1 >= -1e-9) & (w2 >= -1e-9)
        if not mask.any():
            continue
        iz = w0 / z0 + w1 / z1 + w2 / z2
        with np.errstate(divide="ignore", invalid="ignore"):
            depth = 1.0 / iz
        sub_z = zbuf[ys0:ys1 + 1, minx:maxx + 1]
        upd = mask & (depth < sub_z)
        if not upd.any():
            continue
        sub_z[upd] = depth[upd]
        img[ys0:ys1 + 1, minx:maxx + 1][upd] = col


# =========================================================================
# 8. ЕКСПОРТ
# =========================================================================


def export_obj(model: Model, obj_path: Path, mtl_path: Path, name="nikolaevo") -> int:
    verts, faces = [], []
    index = {}
    for pts, colour, _group in model.faces:
        mat = MAT_BY_RGB.get(tuple(round(c, 3) for c in colour), "byalo")
        idx = []
        for p in pts:
            rp = (round(p[0], 4), round(p[1], 4), round(p[2], 4))
            if rp not in index:
                index[rp] = len(verts) + 1
                verts.append(rp)
            idx.append(index[rp])
        faces.append((mat, idx))

    lines = [f"# {name} — генерирано от generate_3d.py",
             f"# {len(verts)} върха, {len(faces)} стени",
             f"mtllib {mtl_path.name}", f"o {name}"]
    lines += [f"v {x:.4f} {y:.4f} {z:.4f}" for x, y, z in verts]
    last = None
    for mat, idx in faces:
        if mat != last:
            lines.append(f"usemtl {mat}")
            last = mat
        lines.append("f " + " ".join(str(i) for i in idx))
    obj_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    ml = ["# Материали за 3D модела"]
    for mname, rgb in MATERIALS.items():
        ml += [f"newmtl {mname}",
               f"Kd {rgb[0]:.3f} {rgb[1]:.3f} {rgb[2]:.3f}",
               "Ka 0.200 0.200 0.200",
               "Ks 0.000 0.000 0.000",
               "illum 1", ""]
    mtl_path.write_text("\n".join(ml), encoding="utf-8")
    return len(faces)


def export_json(model: Model, path: Path) -> None:
    faces = []
    for pts, colour, group in model.faces:
        faces.append({"g": group,
                      "c": [round(c, 3) for c in colour],
                      "p": [[round(v, 4) for v in p] for p in pts]})
    payload = json.dumps({"units": "m", "faces": faces}, separators=(",", ":"))
    path.write_text(payload, encoding="utf-8")
    # същите данни и като JS — за да работи model.html и през file://
    (path.with_suffix(".js")).write_text(
        "window.HOUSE_DATA = " + payload + ";\n", encoding="utf-8")


# =========================================================================
# 9. СЦЕНИ
# =========================================================================

SCENES = [
    # (файл, модел, око, цел, fov, скрити групи, околна светлина)
    ("01-aksonometriya-s-mebel", "cut", (23.5, 21.0, 16.5), (7.3, 4.0, 0.0), 34, (), None),
    ("02-aksonometriya-bez-mebel", "cut0", (23.5, 21.0, 16.5), (7.3, 4.0, 0.0), 34, (), None),
    ("03-aksonometriya-severoiztok", "cut", (-8.5, -9.0, 15.0), (6.6, 4.2, 0.0), 34, (), None),
    ("04-fasada-yug", "full", (8.0, 46.0, 2.8), (8.0, 4.1, 2.0), 18, (), None),
    ("05-fasada-iztok", "full", (50.0, 4.1, 2.4), (14.0, 4.1, 1.9), 18, (), None),
    ("06-perspektiva-yugoiztok", "full", (28.0, 21.0, 9.0), (7.3, 3.8, 1.7), 34, (), None),
    ("07-perspektiva-severoiztok", "full", (-11.0, -10.0, 8.4), (6.4, 4.4, 1.7), 34, (), None),
    ("08-vatreshna-dnevna-s-mebel", "full", (10.70, 3.50, 1.60), (6.95, 3.28, 1.30), 63, ("pokriv",), 0.60),
    ("09-vatreshna-dnevna-bez-mebel", "full0", (10.70, 3.50, 1.60), (6.95, 3.28, 1.30), 63, ("pokriv",), 0.60),
    ("10-vatreshna-kuhnya-s-mebel", "full", (8.60, 7.60, 1.55), (8.20, 2.60, 1.10), 62, ("pokriv",), 0.60),
    ("11-vatreshna-kuhnya-bez-mebel", "full0", (8.60, 7.60, 1.55), (8.20, 2.60, 1.10), 62, ("pokriv",), 0.60),
    ("12-vatreshna-spalnya-s-mebel", "full", (0.75, 4.35, 1.50), (3.30, 7.40, 0.85), 66, ("pokriv",), 0.60),
    ("13-vatreshna-spalnya-bez-mebel", "full0", (0.75, 4.35, 1.50), (3.30, 7.40, 0.85), 66, ("pokriv",), 0.60),
    ("14-veranda-s-mebel", "vfull", (17.2, 13.6, 4.2), (12.9, 4.2, 1.0), 52, (), 0.55),
    ("15-veranda-otvorena", "vfull", (15.6, 6.0, 7.2), (12.9, 4.2, 0.2), 56, ("vroof",), 0.55),
]


def main() -> int:
    IMG_DIR.mkdir(parents=True, exist_ok=True)

    models = {
        "full": build_model(furniture=True),
        "full0": build_model(furniture=False),
        "cut": build_model(furniture=True, clip_z=1.35),
        "cut0": build_model(furniture=False, clip_z=1.35),
        "vfull": build_model(furniture=True),
        "vfull0": build_model(furniture=False),
    }

    n_full = export_obj(models["full"], HERE / "house-full.obj",
                        HERE / "house-full.mtl", "nikolaevo-full")
    n_shell = export_obj(models["full0"], HERE / "house-shell.obj",
                         HERE / "house-shell.mtl", "nikolaevo-shell")
    export_json(models["full"], HERE / "model-data.json")
    print(f"OBJ: house-full.obj ({n_full} стени), house-shell.obj ({n_shell} стени)")

    for name, key, eye, target, fov, hide, ambient in SCENES:
        kw = {"fov": fov, "hide": hide}
        if ambient is not None:
            kw["ambient"] = ambient
        im = render(models[key], eye, target, **kw)
        path = IMG_DIR / f"{name}.png"
        im.save(path, optimize=True)
        print(f"  {path.name:<42} {im.size[0]}×{im.size[1]}")

    print(f"\nГотово: {len(SCENES)} рендера в {IMG_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""
Дограма и врати — схема за поръчка.

Генерира (в architecture/plans/):
    A-03-dograma.svg   фасади на всеки прозорец и врата с посока на отваряне,
                       размери и списък на вътрешните врати

Схемата е за дограмаджията: показва как се отваря всяко крило, накъде, и какви
са размерите. Не е работен чертеж на профилите.

Чертае се в милиметри хартия (мащаб 1:1), защото отворите се мащабират
индивидуално, за да се поберат в клетките.

Употреба:
    python generate_openings_schedule.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from svgkit import Canvas  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

OUT = Path(__file__).resolve().parent / "plans"

PAGE_W, PAGE_H = 210, 300
MARGIN = 12

# (код, помещение, фасада, ширина, височина, подпрозорец, вид, отваряне)
OPENINGS = [
    ("П1", "Спалня 1", "ЮГ", 1500, 1400, 800, "window", "TL"),
    ("П2", "Спалня 2", "ЮГ", 1500, 1400, 800, "window", "TR"),
    ("П3", "Хол", "ЮГ", 2800, 2250, 0, "slider", "slide"),
    ("П4", "Кухня", "СЕВЕР", 1200, 1400, 1000, "window", "L"),
    ("П5", "Баня", "СЕВЕР", 600, 600, 1600, "window", "L"),
    ("П6", "Мокро", "СЕВЕР", 600, 600, 1500, "window", "R"),
    ("П7", "Трапезария", "ИЗТОК", 1600, 1400, 800, "window", "TL"),
    ("П8", "Спалня 1 (опция)", "ЗАПАД", 1000, 1400, 800, "window", "R"),
    ("В1", "Вход", "ИЗТОК", 1050, 2100, 0, "door", "L"),
]

INTERIOR_DOORS = [
    ("В2", "Антре → хол", 900, 2100, "в хола"),
    ("В3", "Коридор → спалня 1", 900, 2000, "в спалнята"),
    ("В4", "Коридор → спалня 2", 900, 2000, "в спалнята"),
    ("В5", "Коридор → баня", 900, 2000, "в банята"),
    ("В6", "Коридор → мокро", 900, 2000, "в помещението"),
]

MODE_TEXT = {
    "L": "ляво крило",
    "R": "дясно крило",
    "TL": "крилно-наклонено, ляво",
    "TR": "крилно-наклонено, дясно",
    "slide": "плъзгащо, 2 крила",
    "fix": "фиксирано",
}


def sash_marks(c: Canvas, x, y, w, h, mode: str) -> None:
    """Посока на отваряне: триъгълник с връх при пантата."""
    if mode == "slide":
        c.line(x + w * 0.10, y + h * 0.5, x + w * 0.86, y + h * 0.5, "soft")
        c.poly([(x + w * 0.90, y + h * 0.5), (x + w * 0.80, y + h * 0.42),
                (x + w * 0.80, y + h * 0.58)], "el-f")
        return
    if mode == "fix":
        return

    left = mode in ("L", "TL")
    apex_x = x + (w * 0.07 if left else w * 0.93)
    far_x = x + (w * 0.60 if left else w * 0.40)
    c.poly([(apex_x, y + h * 0.5), (far_x, y + h * 0.10), (far_x, y + h * 0.90)],
           "el-d")

    if mode in ("TL", "TR"):
        c.line(far_x, y + h * 0.10, far_x, y + h * 0.32, "soft")


def draw_opening(c: Canvas, x, y, w, h, mode: str, kind: str) -> None:
    """Фасада на отвор: рамка, крила и посока на отваряне."""
    c.rect(x, y, w, h, "el")
    c.rect(x + 1.2, y + 1.2, w - 2.4, h - 2.4, "el")

    if kind == "slider":
        c.line(x + w / 2, y + 1.2, x + w / 2, y + h - 1.2, "el-d")
        sash_marks(c, x, y, w, h, mode)
        return

    if kind == "window" and w >= 11.0:
        # двойно крило — маркира се само отварящото се
        c.line(x + w * 0.52, y + 1.2, x + w * 0.52, y + h - 1.2, "el-d")
        if mode in ("L", "TL"):
            sash_marks(c, x, y, w * 0.52, h, mode)
        else:
            sash_marks(c, x + w * 0.52, y, w * 0.48, h, mode)
    else:
        sash_marks(c, x, y, w, h, mode)


def build() -> Canvas:
    c = Canvas(1, "A-03 Дограма и врати — схема за поръчка")

    # ---------- заглавие ----------
    c.text(MARGIN, 14, "ДОГРАМА — ФАСАДИ И ПОСОКИ НА ОТВАРЯНЕ", "sub", "start")
    c.text(PAGE_W - MARGIN, 14, "Триъгълникът сочи към пантата", "lbl-s", "end")

    # ---------- решетка 3 × 3 ----------
    cell_w, cell_h = (PAGE_W - 2 * MARGIN) / 3, 58.0
    grid_y = 19.0

    for i, (code, room, facade, w, h, sill, kind, mode) in enumerate(OPENINGS):
        col, row = i % 3, i // 3
        cx = MARGIN + col * cell_w
        cy = grid_y + row * cell_h

        c.text(cx + cell_w / 2, cy + 5, f"{facade} ФАСАДА", "lbl-s")

        max_w, max_h = cell_w - 22, cell_h - 26
        k = min(max_w / w, max_h / h)
        dw, dh = w * k, h * k
        ox = cx + (cell_w - dw) / 2
        oy = cy + 9 + (max_h - dh) / 2

        draw_opening(c, ox, oy, dw, dh, mode, kind)

        c.text(ox + dw / 2, oy - 1.8, f"{code} · {room}", "code")
        size = f"{w} × {h}" + (f"  ·  подпрозорец {sill}" if sill else "")
        c.text(ox + dw / 2, oy + dh + 4.2, size, "lbl-s")

    # ---------- вътрешни врати ----------
    dy = grid_y + 3 * cell_h + 6
    c.text(MARGIN, dy, "ВЪТРЕШНИ ВРАТИ", "sub", "start")
    c.text(PAGE_W - MARGIN, dy, "0,9 m широки · отваряне в помещението", "lbl-s", "end")

    heads = [(MARGIN, "код"), (MARGIN + 10, "връзка"),
             (MARGIN + 92, "Ш × В"), (MARGIN + 116, "отваряне")]
    for x, head in heads:
        c.text(x, dy + 5, head, "lbl-s", "start")
    c.line(MARGIN, dy + 6.5, PAGE_W - MARGIN, dy + 6.5, "dim")

    for i, (code, where, w, h, direction) in enumerate(INTERIOR_DOORS):
        y = dy + 6.5 + i * 5.4
        c.text(MARGIN, y + 3.8, code, "note", "start")
        c.text(MARGIN + 10, y + 3.8, where, "note", "start")
        c.text(MARGIN + 92, y + 3.8, f"{w} × {h}", "note", "start")
        c.text(MARGIN + 116, y + 3.8, direction, "note", "start")
    c.line(MARGIN, dy + 6.5 + len(INTERIOR_DOORS) * 5.4,
           PAGE_W - MARGIN, dy + 6.5 + len(INTERIOR_DOORS) * 5.4, "dim")

    # ---------- бележки ----------
    ny = dy + 6.5 + len(INTERIOR_DOORS) * 5.4 + 9
    c.text(MARGIN, ny, "БЕЛЕЖКИ", "sub", "start")
    notes = [
        "1. Триъгълникът показва страната на пантата и посоката на отваряне.",
        "2. Външната дограма е с троен стъклопакет; на юг с нисък коефициент на слънчева пропускливост.",
        "3. Южните отвори изискват външно засенчване — надвес, ролетки или пергола.",
        "4. Размерите са номинални (отвор в светъл размер); реалните се снемат на място.",
        "5. П8 е опция — да се оферира отделно.  П3 е плъзгаща, с две крила.",
    ]
    for i, text in enumerate(notes):
        c.text(MARGIN, ny + 6 + i * 5.0, text, "note", "start")

    # ---------- рамка ----------
    c.title_block(
        MARGIN, ny + 33, PAGE_W - 2 * MARGIN,
        [
            "NIKOLAEVO HOUSE — ДОГРАМА",
            "Схема на отворите и посоките на отваряне · лист A-03",
            "За поръчка на дограма. Не е работен чертеж на профилите. Размери в mm.",
        ],
        "A-03",
        "Схема — без мащаб",
    )
    return c


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    path = build().render((-6, -6, PAGE_W + 12, PAGE_H + 12), OUT / "A-03-dograma.svg")
    print(f"Дограма — записан файл:\n  {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

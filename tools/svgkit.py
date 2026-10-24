#!/usr/bin/env python3
"""
Малка библиотека за генериране на SVG чертежи в реален мащаб.

Използва се от:
    furniture/generate_furniture.py
    electrical/generate_electrical.py
    architecture/generate_openings_schedule.py

Две мерни единици, които не бива да се бъркат:
    px(m)   — реален размер в метри → чертожни единици (1 единица = 1 mm)
    u(mm)   — милиметри върху хартията → чертожни единици по мащаба

Геометрията на сградата минава през px(); отстъпите на текст, легенди и рамки —
през u().
"""

from __future__ import annotations

from pathlib import Path


def esc(text: str) -> str:
    """Екранира специални символи за XML."""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def fmt(value: float, digits: int = 0) -> str:
    """Число с десетична запетая."""
    if digits == 0:
        return f"{value:.0f}"
    return f"{value:.{digits}f}".replace(".", ",")


def px(meters: float) -> float:
    """Метри → чертожни единици (1 единица = 1 mm от сградата)."""
    return meters * 1000.0


class Canvas:
    """Минималистичен SVG конструктор с размери в реални милиметри."""

    def __init__(self, scale: int, title: str, desc: str = ""):
        self.scale = scale
        self.title = title
        self.desc = desc
        self.els: list[str] = []

    # --- мащаб ------------------------------------------------------------
    def u(self, paper_mm: float) -> float:
        return paper_mm * self.scale

    # --- примитиви --------------------------------------------------------
    def line(self, x1, y1, x2, y2, cls="ln") -> None:
        self.els.append(
            f'<line class="{cls}" x1="{x1:.1f}" y1="{y1:.1f}" '
            f'x2="{x2:.1f}" y2="{y2:.1f}"/>'
        )

    def rect(self, x, y, w, h, cls="sym") -> None:
        self.els.append(
            f'<rect class="{cls}" x="{x:.1f}" y="{y:.1f}" '
            f'width="{max(w, 0.1):.1f}" height="{max(h, 0.1):.1f}"/>'
        )

    def circle(self, cx, cy, r, cls="sym") -> None:
        self.els.append(
            f'<circle class="{cls}" cx="{cx:.1f}" cy="{cy:.1f}" r="{r:.1f}"/>'
        )

    def ellipse(self, cx, cy, rx, ry, cls="sym") -> None:
        self.els.append(
            f'<ellipse class="{cls}" cx="{cx:.1f}" cy="{cy:.1f}" '
            f'rx="{rx:.1f}" ry="{ry:.1f}"/>'
        )

    def poly(self, pts, cls="sym", closed=True) -> None:
        points = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
        tag = "polygon" if closed else "polyline"
        self.els.append(f'<{tag} class="{cls}" points="{points}"/>')

    def text(self, x, y, s, cls="lbl", anchor="middle", rot=0.0, size=None) -> None:
        tr = f' transform="rotate({rot:.1f} {x:.1f} {y:.1f})"' if rot else ""
        st = f' style="font-size:{size:.1f}px"' if size is not None else ""
        self.els.append(
            f'<text class="{cls}" x="{x:.1f}" y="{y:.1f}" '
            f'text-anchor="{anchor}"{tr}{st}>{esc(s)}</text>'
        )

    # --- размери ----------------------------------------------------------
    def dim_h(self, x1, x2, y, label, ext_from=None) -> None:
        t = self.u(0.75)
        self.line(x1, y, x2, y, "dim")
        self.line(x1 - t, y + t, x1 + t, y - t, "dim")
        self.line(x2 - t, y + t, x2 + t, y - t, "dim")
        if ext_from is not None:
            self.line(x1, ext_from, x1, y, "dim")
            self.line(x2, ext_from, x2, y, "dim")
        if abs(x2 - x1) > self.u(4.0):
            self.text((x1 + x2) / 2, y - self.u(1.0), label, "dimt")

    def dim_v(self, y1, y2, x, label, ext_from=None, side="left") -> None:
        t = self.u(0.75)
        self.line(x, y1, x, y2, "dim")
        self.line(x - t, y1 + t, x + t, y1 - t, "dim")
        self.line(x - t, y2 + t, x + t, y2 - t, "dim")
        if ext_from is not None:
            self.line(ext_from, y1, x, y1, "dim")
            self.line(ext_from, y2, x, y2, "dim")
        if abs(y2 - y1) > self.u(4.0):
            dx = -self.u(1.1) if side == "left" else self.u(1.1)
            self.text(x + dx, (y1 + y2) / 2, label, "dimt", rot=-90)

    # --- рамка ------------------------------------------------------------
    def title_block(self, x, y, w, lines, sheet, scale_text) -> None:
        h1, h2 = self.u(8.0), self.u(7.0)
        h3 = self.u(5.2) * (len(lines) - 2) + self.u(4.0)
        total = h1 + h2 + h3

        self.els.append(
            f'<rect class="tb" x="{x:.1f}" y="{y:.1f}" '
            f'width="{w:.1f}" height="{total:.1f}"/>'
        )
        self.line(x, y + h1, x + w, y + h1, "tb")
        self.line(x, y + h1 + h2, x + w, y + h1 + h2, "tb")
        split = x + w - self.u(52)
        self.line(split, y, split, y + h1 + h2, "tb")

        # заглавието се смалява, ако не се побира в лявата клетка
        avail = split - x - self.u(6)
        fs = self.u(2.6)
        need = len(lines[0]) * 0.63 * fs
        if need > avail:
            fs = avail / (len(lines[0]) * 0.63)
        self.text(x + self.u(3), y + h1 * 0.5 + fs * 0.36, lines[0],
                  "tbmain", "start", size=fs)
        self.text(x + self.u(3), y + h1 + h2 * 0.68, lines[1], "tbsub", "start")
        self.text(split + self.u(3), y + h1 * 0.64, sheet, "tbsmall", "start")
        self.text(split + self.u(3), y + h1 + h2 * 0.68, scale_text,
                  "tbsmall", "start")
        for i, note in enumerate(lines[2:]):
            self.text(x + self.u(3), y + h1 + h2 + self.u(4.0) + i * self.u(5.2),
                      note, "tbsmall", "start")

    # --- стил ---------------------------------------------------------------
    def _style(self) -> str:
        s = self.scale

        def q(mm: float) -> str:
            return f"{mm * s:.2f}"

        return (
            '<style type="text/css"><![CDATA[\n'
            f'.wall   {{ fill:#dcdcdc; stroke:#111; stroke-width:{q(0.28)}; }}\n'
            f'.wall-l {{ fill:none; stroke:#111; stroke-width:{q(0.22)}; }}\n'
            f'.part   {{ fill:#eeeeee; stroke:#111; stroke-width:{q(0.16)}; }}\n'
            f'.win    {{ fill:#ffffff; stroke:#111; stroke-width:{q(0.24)}; }}\n'
            f'.glass  {{ fill:none; stroke:#111; stroke-width:{q(0.14)}; }}\n'
            f'.sym    {{ fill:#ffffff; stroke:#111; stroke-width:{q(0.20)}; }}\n'
            f'.sym-f  {{ fill:#f2f2f2; stroke:#111; stroke-width:{q(0.20)}; }}\n'
            f'.sym-l  {{ fill:none; stroke:#111; stroke-width:{q(0.18)}; }}\n'
            f'.soft   {{ fill:none; stroke:#777; stroke-width:{q(0.16)}; '
            f'stroke-dasharray:{q(0.9)} {q(0.55)}; }}\n'
            f'.ghost  {{ fill:none; stroke:#aaa; stroke-width:{q(0.15)}; '
            f'stroke-dasharray:{q(1.2)} {q(0.6)}; }}\n'
            f'.door   {{ fill:none; stroke:#111; stroke-width:{q(0.22)}; }}\n'
            f'.door-a {{ fill:none; stroke:#888; stroke-width:{q(0.15)}; '
            f'stroke-dasharray:{q(0.7)} {q(0.5)}; }}\n'
            f'.dim    {{ fill:none; stroke:#666; stroke-width:{q(0.14)}; }}\n'
            f'.dimt   {{ fill:#333; font-size:{q(1.95)}px;  }}\n'
            f'.lbl    {{ fill:#111; font-size:{q(2.5)}px;  }}\n'
            f'.lbl-s  {{ fill:#555; font-size:{q(1.95)}px;  }}\n'
            f'.lbl-f  {{ fill:#222; font-size:{q(1.7)}px;  }}\n'
            f'.code   {{ fill:#111; font-size:{q(2.0)}px; font-weight:bold; }}\n'
            f'.sub    {{ fill:#555; font-size:{q(2.2)}px; }}\n'
            f'.note   {{ fill:#222; font-size:{q(1.95)}px; }}\n'
            f'.el     {{ fill:#fff; stroke:#111; stroke-width:{q(0.22)}; }}\n'
            f'.el-f   {{ fill:#111; stroke:#111; stroke-width:{q(0.22)}; }}\n'
            f'.el-d   {{ fill:none; stroke:#111; stroke-width:{q(0.22)}; }}\n'
            f'.tb     {{ fill:none; stroke:#111; stroke-width:{q(0.25)}; }}\n'
            f'.tbmain {{ fill:#111; font-size:{q(2.6)}px; font-weight:bold; }}\n'
            f'.tbsub  {{ fill:#333; font-size:{q(2.4)}px; }}\n'
            f'.tbsmall{{ fill:#444; font-size:{q(1.95)}px; }}\n'
            f'.plate  {{ fill:#ffffff; fill-opacity:0.92; stroke:none; }}\n'
            f'.mask   {{ fill:#ffffff; stroke:none; }}\n'
            ']]></style>'
        )

    # --- запис --------------------------------------------------------------
    def render(self, viewbox, out_path: Path) -> Path:
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
        parts.append(self._style())
        parts.append(
            f'<rect x="{x:.0f}" y="{y:.0f}" width="{w:.0f}" height="{h:.0f}" '
            'fill="#ffffff"/>'
        )
        parts.extend(self.els)
        parts.append("</svg>")

        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text("\n".join(parts), encoding="utf-8")
        return out_path

#!/usr/bin/env python3
"""
Растеризира SVG чертежи в PNG чрез headless Chrome или Edge.

Търси SVG файлове в plans/ на съответната папка и записва PNG в images/.
cairosvg не се използва — на Windows му липсва cairo DLL.

Употреба:
    python export_png.py furniture
    python export_png.py electrical --width 2000
    python export_png.py furniture electrical architecture icf
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
import tempfile
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent

BROWSERS = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
]


def find_browser() -> Path:
    for candidate in BROWSERS:
        path = Path(candidate)
        if path.exists():
            return path
    raise SystemExit("Не е намерен Chrome или Edge.")


def svg_size(svg_path: Path) -> tuple[float, float]:
    head = svg_path.read_text(encoding="utf-8")[:600]
    w = re.search(r'width="([\d.]+)(mm)?"', head)
    h = re.search(r'height="([\d.]+)(mm)?"', head)
    if not w or not h:
        raise SystemExit(f"Не мога да прочета размерите на {svg_path.name}")
    # mm и px се третират еднакво — важно е само съотношението
    return float(w.group(1)), float(h.group(1))


def render(browser: Path, svg_path: Path, out_path: Path, width: int) -> None:
    w_mm, h_mm = svg_size(svg_path)
    height = round(width * h_mm / w_mm)
    html = (
        '<!DOCTYPE html><html><head><meta charset="utf-8"><style>'
        "html,body{margin:0;padding:0;background:#fff}"
        f"img{{display:block;width:{width}px;height:{height}px}}"
        f'</style></head><body><img src="{svg_path.as_uri()}"></body></html>'
    )
    with tempfile.TemporaryDirectory() as tmp:
        html_path = Path(tmp) / "view.html"
        html_path.write_text(html, encoding="utf-8")
        cmd = [
            str(browser), "--headless=new", "--disable-gpu", "--hide-scrollbars",
            "--force-device-scale-factor=1",
            f"--window-size={width + 20},{height + 20}",
            f"--screenshot={out_path}",
            "--virtual-time-budget=4000",
            html_path.as_uri(),
        ]
        subprocess.run(cmd, check=True, capture_output=True, timeout=180)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="SVG → PNG за чертежите.")
    parser.add_argument("areas", nargs="+",
                        help="папки: furniture, electrical, architecture, icf")
    parser.add_argument("--width", type=int, default=2400)
    args = parser.parse_args(argv)

    browser = find_browser()
    print(f"Браузър: {browser}")

    for area in args.areas:
        plans = ROOT / area / "plans"
        images = ROOT / area / "images"
        svgs = sorted(plans.glob("*.svg"))
        if not svgs:
            print(f"  ({area}: няма SVG)")
            continue
        images.mkdir(parents=True, exist_ok=True)
        for svg_path in svgs:
            out = images / (svg_path.stem + ".png")
            render(browser, svg_path, out, args.width)
            print(f"  {area}/{out.name:<28} {args.width}px  "
                  f"({out.stat().st_size // 1024} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

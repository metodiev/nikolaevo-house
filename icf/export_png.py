#!/usr/bin/env python3
"""
Растеризира SVG скиците от icf/plans в PNG (icf/images).

Използва headless Chrome/Edge — единственият надежден начин за точен SVG рендер
на Windows без допълнителни библиотеки (cairosvg иска cairo DLL, който липсва).

За всеки SVG се създава временна HTML обвивка с <img> на фиксирана ширина,
след което браузърът прави screenshot. Временните файлове се изтриват.

Употреба:
    python export_png.py            # всички файлове от icf/plans
    python export_png.py --width 2400
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

ROOT = Path(__file__).resolve().parent
PLANS = ROOT / "plans"
IMAGES = ROOT / "images"

BROWSERS = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
]


def find_browser() -> Path:
    """Намира първия наличен Chromium браузър."""
    for candidate in BROWSERS:
        path = Path(candidate)
        if path.exists():
            return path
    raise SystemExit(
        "Не е намерен Chrome или Edge. Инсталирайте един от тях или конвертирайте "
        "SVG файловете ръчно."
    )


def svg_size(svg_path: Path) -> tuple[float, float]:
    """Чете width/height (в mm) от SVG файла."""
    head = svg_path.read_text(encoding="utf-8")[:600]
    width = re.search(r'width="([\d.]+)mm"', head)
    height = re.search(r'height="([\d.]+)mm"', head)
    if not width or not height:
        raise SystemExit(f"Не мога да прочета размерите на {svg_path.name}")
    return float(width.group(1)), float(height.group(1))


def render(browser: Path, svg_path: Path, out_path: Path, target_width: int) -> None:
    """Рендерира един SVG в PNG с ширина target_width пиксела."""
    w_mm, h_mm = svg_size(svg_path)
    px_height = round(target_width * h_mm / w_mm)

    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>
  html, body {{ margin:0; padding:0; background:#fff; }}
  img {{ display:block; width:{target_width}px; height:{px_height}px; }}
</style></head>
<body><img src="{svg_path.as_uri()}"></body></html>
"""

    with tempfile.TemporaryDirectory() as tmp:
        html_path = Path(tmp) / "view.html"
        html_path.write_text(html, encoding="utf-8")
        # Малко допълнително място, за да не се появяват скролбари
        win_w = target_width + 20
        win_h = px_height + 20
        cmd = [
            str(browser),
            "--headless=new",
            "--disable-gpu",
            "--hide-scrollbars",
            "--force-device-scale-factor=1",
            f"--window-size={win_w},{win_h}",
            f"--screenshot={out_path}",
            "--virtual-time-budget=4000",
            html_path.as_uri(),
        ]
        subprocess.run(cmd, check=True, capture_output=True, timeout=120)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="SVG → PNG за ICF скиците.")
    parser.add_argument("--width", type=int, default=2400,
                        help="ширина на PNG в пиксели (по подразбиране 2400)")
    parser.add_argument("--only", type=str, default=None,
                        help="рендерира само файл, чието име съдържа този низ")
    args = parser.parse_args(argv)

    browser = find_browser()
    IMAGES.mkdir(parents=True, exist_ok=True)

    svgs = sorted(PLANS.glob("*.svg"))
    if args.only:
        svgs = [p for p in svgs if args.only in p.name]
    if not svgs:
        raise SystemExit("Няма SVG файлове за конвертиране.")

    print(f"Браузър: {browser}")
    for svg_path in svgs:
        out_path = IMAGES / (svg_path.stem + ".png")
        render(browser, svg_path, out_path, args.width)
        size_kb = out_path.stat().st_size / 1024
        print(f"  {out_path.name:<22} {args.width}px  ({size_kb:.0f} KB)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

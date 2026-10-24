#!/usr/bin/env python3
"""
Проверка на площите в целия проект.

Прави две неща:

1. Изчислява площите от геометрията и ги сравнява с каноничните стойности.
2. Обхожда всички .md, .py и .svg файлове и търси числа, които противоречат
   на каноничните (например остатъци от стара версия на къщата).

Канонични стойности (единствен източник на истина):
    габарит            12,00 × 8,20 m
    застроена площ     98,40 m²
    вътрешна (светли)  84,75 m²
    чиста използваема  80,28 m²

Употреба:
    python tools/check_areas.py

Изходен код: 0 = всичко съвпада, 1 = има разминаване.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent

# =========================================================================
# 1. КАНОНИЧНА ГЕОМЕТРИЯ
# =========================================================================

HOUSE_L = 12.00
HOUSE_D = 8.20
WALL_EXT = 0.35

# (име, x1, y1, x2, y2) — по вътрешни стени, y от юг
ROOMS = [
    ("Спалня 1", 0.35, 0.35, 3.50, 4.45),
    ("Спалня 2", 3.65, 0.35, 6.80, 4.45),
    ("Хол + трапезария", 6.95, 0.35, 11.65, 5.63),
    ("Кухня", 6.95, 5.63, 9.63, 7.85),
    ("Коридор", 0.35, 4.60, 6.80, 5.70),
    ("Баня", 0.35, 5.85, 3.50, 7.85),
    ("Мокро помещение", 3.65, 5.85, 6.80, 7.85),
    ("Антре", 9.75, 5.75, 11.65, 7.85),
]

BUILT = HOUSE_L * HOUSE_D
INTERIOR = (HOUSE_L - 2 * WALL_EXT) * (HOUSE_D - 2 * WALL_EXT)
NET = sum((x2 - x1) * (y2 - y1) for _, x1, y1, x2, y2 in ROOMS)

# =========================================================================
# 2. ПРАВИЛА ЗА ТЪРСЕНЕ
# =========================================================================

# (regex, описание, позволени файлове)
FORBIDDEN = [
    (r"7[.,]60", "стара дълбочина 7,60 m", set()),
    (r"91[.,]20?\b", "стара застроена площ 91,2 m²", set()),
    (r"78[.,]98", "стара чиста площ 78,98 m²", set()),
    (r"2680\s*×\s*2100", "стара кухня 2680 × 2100", set()),
    (r"25[.,]2\s*m²", "стар хол 25,2 m²", set()),
]

# Файлове, в които историческите варианти са нарочно описани
ALLOWED_FILES = {
    "architecture/04-diagrams.md",        # таблица с отхвърлени варианти
    "architecture/01-concept-plan.md",    # обяснение защо не 96 m²
}

# Ключови документи, в които трябва да фигурират каноничните числа
REQUIRED = [
    ("README.md", "98,40"),
    ("README.md", "84,75"),
    ("README.md", "80,3"),
    ("architecture/02-areas.md", "98,40"),
    ("architecture/02-areas.md", "84,75"),
    ("architecture/02-areas.md", "80,3"),
    ("architecture/01-concept-plan.md", "98,40"),
    ("documentation/01-design-brief.md", "98,4"),
    ("budget/01-cost-estimate.md", "98,4"),
    ("budget/02-turnkey-max.md", "98,4"),
    ("icf/README.md", "98,4"),
]

SCAN_SUFFIXES = {".md", ".py", ".svg"}


# =========================================================================
# 3. ПРОВЕРКИ
# =========================================================================


def check_model() -> list[str]:
    """Сравнява изчислените площи с каноничните."""
    problems = []
    expected = {
        "застроена": (BUILT, 98.40),
        "вътрешна": (INTERIOR, 84.75),
        "чиста": (NET, 80.28),
    }
    for name, (value, want) in expected.items():
        if abs(value - want) > 0.02:
            problems.append(f"{name}: изчислено {value:.2f}, очаквано {want:.2f}")
    return problems


def iter_files():
    for path in sorted(ROOT.rglob("*")):
        if path.suffix not in SCAN_SUFFIXES:
            continue
        if any(part in {".git", ".venv", "__pycache__"} for part in path.parts):
            continue
        yield path


def scan_text(path: Path) -> str:
    """
    Връща само текста, който подлежи на проверка.

    За SVG се взимат само текстовите елементи — координатите в пътищата
    случайно съдържат числа като „7.60“ и дават фалшиви сигнали.
    """
    raw = path.read_text(encoding="utf-8", errors="replace")
    if path.suffix == ".svg":
        return "\n".join(re.findall(r"<text[^>]*>(.*?)</text>", raw, re.S))
    return raw


def check_forbidden() -> list[str]:
    """Търси остарели числа в целия проект."""
    problems = []
    for path in iter_files():
        rel = path.relative_to(ROOT).as_posix()
        if rel in ALLOWED_FILES or rel.endswith("check_areas.py"):
            continue
        text = scan_text(path)
        for pattern, what, _ in FORBIDDEN:
            for match in re.finditer(pattern, text):
                line = text.count("\n", 0, match.start()) + 1
                problems.append(f"{rel}:{line}  {what}  → „{match.group(0)}“")
    return problems


def check_svg_titles() -> list[str]:
    """Всеки чертеж, който споменава застроена площ, трябва да сочи 98,40."""
    problems = []
    for path in iter_files():
        if path.suffix != ".svg":
            continue
        rel = path.relative_to(ROOT).as_posix()
        text = scan_text(path)
        if "астроена" not in text:
            continue
        if "98,40" not in text and "98,4 " not in text:
            problems.append(f"{rel} — споменава застроена площ, но не 98,40 m²")
    return problems


def check_required() -> list[str]:
    """Проверява дали ключовите документи съдържат каноничните числа."""
    problems = []
    for rel, needle in REQUIRED:
        path = ROOT / rel
        if not path.exists():
            problems.append(f"{rel} — файлът липсва")
            continue
        if needle not in path.read_text(encoding="utf-8", errors="replace"):
            problems.append(f"{rel} — липсва „{needle}“")
    return problems


def main() -> int:
    print("ПЛОЩИ НА КЪЩАТА — проверка на целия проект")
    print("=" * 60)
    print(f"  Габарит:            {HOUSE_L:.2f} × {HOUSE_D:.2f} m")
    print(f"  Застроена площ:     {BUILT:.2f} m²")
    print(f"  Вътрешна (светли):  {INTERIOR:.2f} m²")
    print(f"  Чиста използваема:  {NET:.2f} m²")
    print()
    print("  По помещения:")
    for name, x1, y1, x2, y2 in ROOMS:
        area = (x2 - x1) * (y2 - y1)
        print(f"    {name:<18} {(x2 - x1):.2f} × {(y2 - y1):.2f} = {area:>6.2f} m²")
    print()

    model = check_model()
    forbidden = check_forbidden()
    svg_titles = check_svg_titles()
    required = check_required()

    print(f"1) Геометрия ..................... {'OK' if not model else 'ГРЕШКИ'}")
    for p in model:
        print(f"     ✗ {p}")
    print(f"2) Остарели числа в текста ....... {'OK' if not forbidden else 'ГРЕШКИ'}")
    for p in forbidden:
        print(f"     ✗ {p}")
    print(f"3) Застроена площ в чертежите .... {'OK' if not svg_titles else 'ГРЕШКИ'}")
    for p in svg_titles:
        print(f"     ✗ {p}")
    print(f"4) Канонични числа в документите . {'OK' if not required else 'ГРЕШКИ'}")
    for p in required:
        print(f"     ✗ {p}")

    ok = not (model or forbidden or svg_titles or required)
    print()
    print("РЕЗУЛТАТ:", "✓ всичко съвпада" if ok else "✗ има разминавания")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

"""Прогон детекции по серии кадров (папка с frame_*.png) — оценка устойчивости сапога.

По каждому кадру печатает позицию сапога/тележки, в конце — сводка: доля кадров с
детектированным сапогом, самые длинные пропуски, разброс площади блоба. Плюс сохраняет
overlay для кадров-пропусков, чтобы видеть, где теряется (§3 CLAUDE.md).

    python debug/detect_series.py debug/record
"""

from __future__ import annotations

import sys
from pathlib import Path

import cv2

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import detect  # noqa: E402


def main(folder: str, dump_misses: int = 5) -> int:
    frames = sorted(Path(folder).glob("frame_*.png"))
    if not frames:
        print(f"Нет кадров frame_*.png в {folder}")
        return 1

    miss_dir = Path(folder) / "misses"
    n = len(frames)
    boot_hits = 0
    areas: list[float] = []
    miss_indices: list[int] = []
    cur_gap = max_gap = 0
    dumped = 0

    for i, path in enumerate(frames):
        frame = cv2.imread(str(path))
        if frame is None:
            print(f"[{i:04d}] не прочитан")
            continue
        field = detect.detect_field(frame)
        cart = detect.detect_cart(frame, field)
        boot = detect.detect_boot(frame, field)
        if boot is not None:
            boot_hits += 1
            areas.append(boot.area)
            cur_gap = 0
            b = f"boot=({boot.x:6.1f},{boot.y:6.1f}) a={boot.area:5.0f}"
        else:
            miss_indices.append(i)
            cur_gap += 1
            max_gap = max(max_gap, cur_gap)
            b = "boot=MISS"
            if dumped < dump_misses:
                miss_dir.mkdir(exist_ok=True)
                cv2.imwrite(str(miss_dir / path.name),
                            detect.draw_overlay(frame, field, cart, boot))
                dumped += 1
        c = f"cart=({cart.x:6.1f},{cart.y:6.1f})" if cart else "cart=MISS"
        print(f"[{i:04d}] {b}  {c}")

    print("\n=== Сводка ===")
    print(f"кадров: {n}, сапог найден: {boot_hits} ({100*boot_hits//max(n,1)}%)")
    print(f"самый длинный пропуск сапога: {max_gap} кадров подряд")
    if areas:
        print(f"площадь сапога: min={min(areas):.0f} max={max(areas):.0f} "
              f"avg={sum(areas)/len(areas):.0f}")
    if miss_indices:
        print(f"пропуски (индексы): {miss_indices[:40]}{' …' if len(miss_indices)>40 else ''}")
        if dumped:
            print(f"overlay пропусков → {miss_dir}")
    return 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Использование: python debug/detect_series.py <folder> [dump_misses]")
        raise SystemExit(2)
    raise SystemExit(main(sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 5))

"""Визуализация детектированной траектории сапога по серии кадров.

Прогоняет детекцию по папке, рисует путь сапога (градиент по времени: синий→жёлтый),
поле и тележку поверх последнего кадра. Помогает глазами оценить качество детекции на
всей дуге (§3 CLAUDE.md).

    python debug/plot_trajectory.py debug/record debug/trajectory.png
"""

from __future__ import annotations

import sys
from pathlib import Path

import cv2

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import detect  # noqa: E402


def main(folder: str, out: str) -> int:
    frames = sorted(Path(folder).glob("frame_*.png"))
    if not frames:
        print(f"Нет кадров в {folder}")
        return 1

    last = cv2.imread(str(frames[-1]))
    field = detect.detect_field(last)
    cart = detect.detect_cart(last, field)

    pts = []
    for path in frames:
        frame = cv2.imread(str(path))
        if frame is None:
            continue
        boot = detect.detect_boot(frame, field)
        if boot is not None:
            pts.append((int(boot.x), int(boot.y)))

    canvas = last.copy()
    cv2.rectangle(canvas, (field.left, field.top), (field.right, field.bottom), (0, 255, 0), 1)
    n = max(len(pts) - 1, 1)
    for i, (x, y) in enumerate(pts):
        # градиент BGR: начало синее (255,0,0) → конец жёлтое (0,255,255)
        t = i / n
        color = (int(255 * (1 - t)), int(255 * t), int(255 * t))
        cv2.circle(canvas, (x, y), 3, color, -1)
        if i > 0:
            cv2.line(canvas, pts[i - 1], (x, y), color, 1)
    if cart is not None:
        cv2.circle(canvas, (int(cart.x), int(cart.y)), 8, (0, 0, 255), 2)

    cv2.imwrite(out, canvas)
    print(f"Точек траектории: {len(pts)} → {out}")
    return 0


if __name__ == "__main__":
    folder = sys.argv[1] if len(sys.argv) > 1 else "debug/record"
    out = sys.argv[2] if len(sys.argv) > 2 else "debug/trajectory.png"
    raise SystemExit(main(folder, out))

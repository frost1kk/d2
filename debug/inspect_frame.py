"""Инспекция реальных пикселей кадра: HSV-статистика по именованным ROI + вырезка патчей.

Помогает калибровать пороги детекции по РЕАЛЬНЫМ данным, а не на глаз (§3 CLAUDE.md).

    python debug/inspect_frame.py assets/frames/inflight.png
"""

from __future__ import annotations

import sys
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parent.parent

# Именованные ROI в АБСОЛЮТНЫХ пикселях кадра 1920×1080 (первичная оценка глазами).
# (name, x0, y0, x1, y1)
ROIS = [
    ("boot",       892, 598, 936, 646),   # сапог в полёте (inflight)
    ("cart_red",   905, 862, 1000, 900),  # красный баннер тележки
    ("brick",      930, 175, 1000, 205),  # кирпич арки (для сравнения с сапогом)
    ("bg_navy",    820, 700, 900, 780),   # тёмно-синий фон поля
    ("pillar_l",   640, 400, 664, 460),   # левая золотая колонна
    ("pillar_r",   1236, 400, 1260, 460), # правая золотая колонна
]


def hsv_stats(bgr_patch: np.ndarray) -> str:
    hsv = cv2.cvtColor(bgr_patch, cv2.COLOR_BGR2HSV)
    h, s, v = hsv[..., 0], hsv[..., 1], hsv[..., 2]
    return (
        f"H[{h.min():3d}..{h.max():3d}]~{int(h.mean()):3d}  "
        f"S[{s.min():3d}..{s.max():3d}]~{int(s.mean()):3d}  "
        f"V[{v.min():3d}..{v.max():3d}]~{int(v.mean()):3d}"
    )


def main(path: str) -> int:
    frame = cv2.imread(path)
    if frame is None:
        print(f"Не прочитать: {path}")
        return 1
    print(f"Кадр: {frame.shape[1]}×{frame.shape[0]}\n")
    out_dir = ROOT / "debug" / "patches"
    out_dir.mkdir(exist_ok=True)
    for name, x0, y0, x1, y1 in ROIS:
        patch = frame[y0:y1, x0:x1]
        if patch.size == 0:
            print(f"{name:10s}: ПУСТО (координаты вне кадра)")
            continue
        print(f"{name:10s}: {hsv_stats(patch)}")
        crop_path = out_dir / f"{Path(path).stem}_{name}.png"
        # Увеличим x8 для наглядности при просмотре.
        big = cv2.resize(patch, None, fx=8, fy=8, interpolation=cv2.INTER_NEAREST)
        cv2.imwrite(str(crop_path), big)
    print(f"\nПатчи (x8) → {out_dir}")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Использование: python debug/inspect_frame.py <frame.png>")
        raise SystemExit(2)
    raise SystemExit(main(sys.argv[1]))

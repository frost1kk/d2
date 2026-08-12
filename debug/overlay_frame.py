"""Оффлайн-проверка детекции на сохранённом кадре (§3 CLAUDE.md).

Читает PNG, прогоняет detect_field/cart/boot, печатает координаты и сохраняет кадр с
разметкой рядом (<name>.overlay.png) для визуальной сверки.

    python debug/overlay_frame.py assets/frames/prelaunch.png
    python debug/overlay_frame.py assets/frames/inflight.png
"""

from __future__ import annotations

import sys
from pathlib import Path

import cv2

# Позволяем запускать как обычный скрипт (без -m): добавляем корень в путь.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import detect  # noqa: E402


def main(path: str) -> int:
    frame = cv2.imread(path)
    if frame is None:
        print(f"Не удалось прочитать кадр: {path}")
        return 1

    field = detect.detect_field(frame)
    cart = detect.detect_cart(frame, field)
    boot = detect.detect_boot(frame, field)

    print(f"Кадр:  {frame.shape[1]}×{frame.shape[0]}")
    print(f"Поле:  left={field.left} top={field.top} right={field.right} bottom={field.bottom}")
    print(f"Тележка: {cart}")
    print(f"Сапог:   {boot}")

    overlay = detect.draw_overlay(frame, field, cart, boot)
    out = str(Path(path).with_suffix(".overlay.png"))
    cv2.imwrite(out, overlay)
    print(f"Разметка → {out}")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Использование: python debug/overlay_frame.py <path-to-frame.png>")
        raise SystemExit(2)
    raise SystemExit(main(sys.argv[1]))

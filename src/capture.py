"""Захват кадров игры через dxcam (быстрый DXGI-грабинг, §7 CLAUDE.md).

⚠️ Требует dxcam + opencv-python и запущенную Windows-сессию. НЕ валидировано вживую.

CLI-режим сохранения опорного кадра (для оффлайн-тестов детекции, §3):
    python -m src.capture --save assets/frames/prelaunch.png
Наведи игру на экран, дождись нужного состояния — скрипт грабит один кадр и пишет PNG.
"""

from __future__ import annotations

import argparse
import sys

import numpy as np

from . import config


class Capturer:
    """Обёртка над dxcam: грабит регион экрана как BGR-кадр numpy."""

    def __init__(self, region: tuple[int, int, int, int] | None = None) -> None:
        try:
            import dxcam
        except ImportError as exc:  # pragma: no cover
            raise ImportError("capture.py требует dxcam. Установи: pip install dxcam") from exc
        # dxcam отдаёт BGR при color='BGR' — совпадает с ожиданиями OpenCV.
        self._camera = dxcam.create(output_color="BGR")
        self._region = region if region is not None else config.CAPTURE_REGION

    def grab(self) -> np.ndarray | None:
        """Один кадр BGR (H×W×3) или None, если dxcam ещё не отдал новый кадр."""
        return self._camera.grab(region=self._region)

    def grab_blocking(self, retries: int = 30) -> np.ndarray:
        """Дождаться валидного кадра (dxcam.grab может вернуть None между кадрами)."""
        for _ in range(retries):
            frame = self.grab()
            if frame is not None:
                return frame
        raise RuntimeError("dxcam не вернул кадр — проверь регион/монитор/драйвер")


def _save_frame(path: str) -> None:
    import cv2

    cam = Capturer()
    frame = cam.grab_blocking()
    cv2.imwrite(path, frame)
    print(f"Сохранён кадр {frame.shape[1]}×{frame.shape[0]} → {path}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Захват кадра игры (dxcam)")
    parser.add_argument("--save", metavar="PATH", help="сохранить один кадр в PNG и выйти")
    args = parser.parse_args(argv)
    if args.save:
        _save_frame(args.save)
        return 0
    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())

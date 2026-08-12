"""Захват кадров игры через dxcam (быстрый DXGI-грабинг, §7 CLAUDE.md).

⚠️ Требует dxcam + opencv-python и запущенную Windows-сессию. НЕ валидировано вживую.

CLI-режимы (для оффлайн-тестов детекции, §3):
    # один кадр:
    python -m src.capture --save assets/frames/prelaunch.png --delay 3
    # серия кадров полёта (ровная частота, различимые кадры):
    python -m src.capture --record 150 --fps 60 --delay 4 --out debug/record
Наведи игру на экран, верни ей фокус за время --delay — скрипт грабит и пишет PNG.
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

    def start_video(self, fps: int) -> None:
        """Включить видео-режим dxcam с целевой частотой (для серийной записи/цикла)."""
        self._camera.start(target_fps=fps, video_mode=True, region=self._region)

    def latest(self) -> np.ndarray:
        """Свежий кадр в видео-режиме (блокирует до следующего кадра по target_fps)."""
        return self._camera.get_latest_frame()

    def stop_video(self) -> None:
        self._camera.stop()


def _save_frame(path: str, delay: float) -> None:
    import time

    import cv2

    if delay > 0:
        # Игра встаёт на паузу без фокуса окна. Пауза даёт время кликнуть по игре,
        # чтобы поймать ЖИВОЙ кадр (напр. сапог в полёте), а не замороженный.
        print(f"Верни фокус игре — захват через {delay:.0f} с…")
        time.sleep(delay)
    cam = Capturer()
    frame = cam.grab_blocking()
    cv2.imwrite(path, frame)
    print(f"Сохранён кадр {frame.shape[1]}×{frame.shape[0]} → {path}")


def _record(out_dir: str, n: int, fps: int, delay: float) -> None:
    import time
    from pathlib import Path

    import cv2

    if delay > 0:
        print(f"Верни фокус игре и запусти сапог — запись {n} кадров через {delay:.0f} с…")
        time.sleep(delay)

    cam = Capturer()
    # Буферим в RAM (запись на диск в цикле роняет частоту). Полный кадр ~6 МБ:
    # 150 кадров ≈ 0.9 ГБ. Уменьшай --record, если памяти мало.
    frames: list[np.ndarray] = []
    cam.start_video(fps)
    try:
        for _ in range(n):
            frames.append(cam.latest().copy())
    finally:
        cam.stop_video()

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    for i, frame in enumerate(frames):
        cv2.imwrite(str(out / f"frame_{i:04d}.png"), frame)
    print(f"Записано {len(frames)} кадров {frames[0].shape[1]}×{frames[0].shape[0]} → {out}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Захват кадров игры (dxcam)")
    parser.add_argument("--save", metavar="PATH", help="сохранить один кадр в PNG и выйти")
    parser.add_argument("--record", type=int, metavar="N",
                        help="записать серию из N кадров и выйти")
    parser.add_argument("--out", default="debug/record",
                        help="папка для серии (--record); по умолчанию debug/record")
    parser.add_argument("--fps", type=int, default=60, help="целевая частота записи (--record)")
    parser.add_argument("--delay", type=float, default=0.0,
                        help="пауза перед захватом, с (чтобы вернуть фокус игре)")
    args = parser.parse_args(argv)
    if args.save:
        _save_frame(args.save, args.delay)
        return 0
    if args.record:
        _record(args.out, args.record, args.fps, args.delay)
        return 0
    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())

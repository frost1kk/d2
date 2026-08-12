"""Регрессионные тесты детекции на РЕАЛЬНЫХ кадрах (assets/frames/).

Проверяют, что детекция поля/тележки/сапога совпадает с ручной разметкой опорных кадров
(§3 CLAUDE.md — реальные данные, не моки). Пропускаются, если нет cv2 или файлов кадров.
"""

from __future__ import annotations

from pathlib import Path

import pytest

cv2 = pytest.importorskip("cv2")

from src import detect  # noqa: E402

FRAMES = Path(__file__).resolve().parent.parent / "assets" / "frames"


def _load(name: str):
    path = FRAMES / name
    if not path.exists():
        pytest.skip(f"нет опорного кадра {path}")
    frame = cv2.imread(str(path))
    if frame is None:
        pytest.skip(f"не прочитать {path}")
    return frame


class TestInflightFrame:
    """Кадр с сапогом в полёте: поле, тележка и сапог должны детектироваться."""

    def test_field_bounds(self):
        frame = _load("inflight.png")
        field = detect.detect_field(frame)
        assert (field.left, field.top, field.right, field.bottom) == (655, 155, 1272, 965)

    def test_boot_detected_near_expected(self):
        frame = _load("inflight.png")
        field = detect.detect_field(frame)
        boot = detect.detect_boot(frame, field)
        assert boot is not None
        assert abs(boot.x - 934) <= 30
        assert abs(boot.y - 620) <= 30

    def test_cart_detected_near_expected(self):
        frame = _load("inflight.png")
        field = detect.detect_field(frame)
        cart = detect.detect_cart(frame, field)
        assert cart is not None
        assert abs(cart.x - 988) <= 40
        assert cart.y > 850  # в нижней полосе поля


class TestPrelaunchFrame:
    """Кадр до запуска: сапог на тележке, в полёте его нет → boot=None; тележка есть."""

    def test_no_boot_in_flight(self):
        frame = _load("prelaunch.png")
        field = detect.detect_field(frame)
        assert detect.detect_boot(frame, field) is None

    def test_cart_detected(self):
        frame = _load("prelaunch.png")
        field = detect.detect_field(frame)
        cart = detect.detect_cart(frame, field)
        assert cart is not None

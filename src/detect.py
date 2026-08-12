"""Детекция игрового поля, тележки и сапога на кадре (OpenCV).

⚠️ НЕ ВАЛИДИРОВАНО на реально захваченных кадрах. Пороги в config.py — первый прикид с
опорных скриншотов. По §3 CLAUDE.md перед заявлением «работает» прогнать на кадрах из
assets/frames/ через debug/overlay_frame.py и подстроить пороги.

Требует opencv-python (cv2) и numpy.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

try:
    import cv2
except ImportError as exc:  # pragma: no cover - зависит от окружения
    raise ImportError(
        "detect.py требует opencv-python. Установи: pip install opencv-python"
    ) from exc

from . import config


@dataclass(frozen=True)
class FieldROI:
    """Прямоугольник игрового поля в пикселях кадра."""

    left: int
    top: int
    right: int
    bottom: int

    @property
    def width(self) -> int:
        return self.right - self.left


@dataclass(frozen=True)
class Detection:
    """Точка детекции: центр объекта + уверенность (площадь блоба)."""

    x: float
    y: float
    area: float


def _scale_x(px: int, w: int) -> int:
    return int(px * w / config.REF_W)


def _scale_y(px: int, h: int) -> int:
    return int(px * h / config.REF_H)


def detect_field(frame: np.ndarray) -> FieldROI:
    """Область поля по измеренным абсолютным пикселям, масштабированным под кадр.

    Геометрия снята с реального захвата 1920×1080 (колонны, HUD). При другом размере
    кадра координаты пропорционально масштабируются.
    """
    h, w = frame.shape[:2]
    return FieldROI(
        left=_scale_x(config.FIELD_LEFT_PX, w),
        top=_scale_y(config.FIELD_TOP_PX, h),
        right=_scale_x(config.FIELD_RIGHT_PX, w),
        bottom=_scale_y(config.FIELD_BOTTOM_PX, h),
    )


def _cart_band_top(frame: np.ndarray, field: FieldROI) -> int:
    """Верхняя граница полосы тележки (абс. px из config, масштаб под кадр)."""
    h = frame.shape[0]
    return max(field.top, _scale_y(config.CART_BAND_TOP_PX, h))


def _largest_blob(mask: np.ndarray, min_area: float) -> Detection | None:
    """Центр крупнейшего контура в маске, если его площадь >= min_area."""
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None
    c = max(contours, key=cv2.contourArea)
    area = cv2.contourArea(c)
    if area < min_area:
        return None
    m = cv2.moments(c)
    if m["m00"] == 0:
        return None
    return Detection(x=m["m10"] / m["m00"], y=m["m01"] / m["m00"], area=area)


def detect_cart(frame_bgr: np.ndarray, field: FieldROI) -> Detection | None:
    """Тележка по красному баннеру в нижней полосе поля. Координаты — в кадре."""
    band_top = _cart_band_top(frame_bgr, field)
    roi = frame_bgr[band_top:field.bottom, field.left:field.right]
    if roi.size == 0:
        return None
    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, np.array(config.CART_RED_LOW_1), np.array(config.CART_RED_HIGH_1))
    mask |= cv2.inRange(hsv, np.array(config.CART_RED_LOW_2), np.array(config.CART_RED_HIGH_2))
    det = _largest_blob(mask, config.MIN_CART_AREA)
    if det is None:
        return None
    return Detection(x=det.x + field.left, y=det.y + band_top, area=det.area)


def detect_boot(frame_bgr: np.ndarray, field: FieldROI) -> Detection | None:
    """Сапог в полёте по бирюзовому блику в поле (выше полосы тележки)."""
    band_top = _cart_band_top(frame_bgr, field)
    roi = frame_bgr[field.top:band_top, field.left:field.right]
    if roi.size == 0:
        return None
    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, np.array(config.BOOT_TEAL_LOW), np.array(config.BOOT_TEAL_HIGH))
    det = _largest_blob(mask, config.MIN_BOOT_AREA)
    if det is None:
        return None
    return Detection(x=det.x + field.left, y=det.y + field.top, area=det.area)


def draw_overlay(
    frame_bgr: np.ndarray,
    field: FieldROI,
    cart: Detection | None,
    boot: Detection | None,
) -> np.ndarray:
    """Кадр с наложенной разметкой — для отладочной визуальной проверки детекции."""
    out = frame_bgr.copy()
    cv2.rectangle(out, (field.left, field.top), (field.right, field.bottom), (0, 255, 0), 2)
    if cart is not None:
        cv2.circle(out, (int(cart.x), int(cart.y)), 8, (0, 0, 255), 2)
        cv2.putText(out, "cart", (int(cart.x) + 10, int(cart.y)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)
    if boot is not None:
        cv2.circle(out, (int(boot.x), int(boot.y)), 8, (255, 255, 0), 2)
        cv2.putText(out, "boot", (int(boot.x) + 10, int(boot.y)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 0), 1)
    return out

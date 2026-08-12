"""Управляющая логика: куда двигать платформу под предсказанную точку падения.

Чистая логика — без OpenCV/ввода, тестируется юнит-тестами (§3 CLAUDE.md).
Направление: -1 = влево, 0 = стоять, +1 = вправо.
"""

from __future__ import annotations

from dataclasses import dataclass

LEFT = -1
STAY = 0
RIGHT = 1


def decide_direction(platform_x: float, target_x: float | None, deadzone: float) -> int:
    """Направление движения платформы к target_x с гистерезисом deadzone.

    target_x=None (сапог не детектирован / летит вверх, предсказания нет) → STAY:
    не дёргаем платформу вслепую. Стратегию ожидания на этот случай решает вызывающий код.
    """
    if target_x is None:
        return STAY
    delta = target_x - platform_x
    if abs(delta) <= deadzone:
        return STAY
    return RIGHT if delta > 0 else LEFT


@dataclass
class Controller:
    """Обёртка над decide_direction с фиксированной мёртвой зоной."""

    deadzone: float

    def decide(self, platform_x: float, target_x: float | None) -> int:
        return decide_direction(platform_x, target_x, self.deadzone)

"""Управляющая логика: куда двигать платформу под предсказанную точку падения.

Чистая логика — без OpenCV/ввода, тестируется юнит-тестами (§3 CLAUDE.md).
Направление: -1 = влево, 0 = стоять, +1 = вправо.
"""

from __future__ import annotations

from dataclasses import dataclass

LEFT = -1
STAY = 0
RIGHT = 1


def select_target(
    boot: tuple[float, float] | None,
    vy: float | None,
    predicted_x: float | None,
    blocks_line_y: float,
    max_shift: float = float("inf"),
) -> float | None:
    """Выбрать целевую x для платформы по двухрежимной стратегии.

    - Сапог не виден → None (держим позицию, вслепую не дёргаем).
    - Сапог в открытой нижней зоне (y ≥ линия блоков) и падает (vy > 0), есть предсказание
      → целимся в **точку падения** (точный прицел, отскоки только от стенок предсказуемы).
    - Иначе (сапог вверху среди блоков — рикошет непредсказуем) → **следуем за x сапога**.

    Предохранитель `max_shift`: если предсказание уводит дальше max_shift от текущего x
    сапога (спуск почти вертикален — далёкий прыжок = выброс скорости), игнорируем его и
    следуем за сапогом. Защищает от рывков тележки на шумной скорости.
    """
    if boot is None:
        return None
    x, y = boot
    if (
        y >= blocks_line_y
        and vy is not None
        and vy > 0
        and predicted_x is not None
        and abs(predicted_x - x) <= max_shift
    ):
        return predicted_x
    return x


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

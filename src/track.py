"""Трекинг сапога и предсказание точки падения на линию платформы.

Чистая математика — **без OpenCV/dxcam**, чтобы модуль тестировался юнит-тестами без
запущенной игры (§3 CLAUDE.md).

Система координат — экранная: x вправо, **y вниз** (как в кадре OpenCV). Значит сапог,
летящий вниз к платформе, имеет vy > 0.

Ключевое наблюдение: точка падения зависит только от **наклона** vx/vy, а не от абсолютной
скорости (время сокращается). Поэтому скорость берём как попиксельную разницу между двумя
последовательными кадрами — реальное время не нужно.
"""

from __future__ import annotations

from dataclasses import dataclass


def reflect_1d(value: float, lo: float, hi: float) -> float:
    """Отразить координату в отрезок [lo, hi] по закону «треугольной волны».

    Моделирует многократные отскоки от левой/правой стенок. Например, для [0, 100]:
    130 → 70 (один отскок), 310 → 90 (несколько отскоков).
    """
    if hi <= lo:
        raise ValueError(f"Некорректные границы: lo={lo} >= hi={hi}")
    width = hi - lo
    p = (value - lo) % (2 * width)  # период волны = 2*width; p ∈ [0, 2*width)
    if p > width:
        p = 2 * width - p
    return lo + p


def predict_landing_x(
    x: float,
    y: float,
    vx: float,
    vy: float,
    x_left: float,
    x_right: float,
    y_platform: float,
) -> float | None:
    """Предсказать x, где сапог пересечёт линию платформы y_platform, с учётом отскоков.

    Возвращает None, если сапог не движется вниз к платформе (vy <= 0) или уже ниже неё —
    в этом случае предсказывать нечего (вызывающий код решает, что делать, см. control).
    """
    if vy <= 0:
        return None
    if y >= y_platform:
        return None
    if x_right <= x_left:
        raise ValueError(f"Некорректные стенки: x_left={x_left} >= x_right={x_right}")
    t = (y_platform - y) / vy
    x_raw = x + vx * t
    return reflect_1d(x_raw, x_left, x_right)


@dataclass
class BootTracker:
    """Стейтфул-трекер: копит позиции сапога по кадрам, считает скорость и предсказание.

    Скорость — разница последних двух валидных позиций (пиксели/кадр). Пропущенные
    детекции (None) не рвут трекер: скорость сохраняется до следующей валидной позиции.
    """

    x_left: float
    x_right: float
    y_platform: float
    _prev: tuple[float, float] | None = None
    _vel: tuple[float, float] | None = None
    _last: tuple[float, float] | None = None

    def update(self, pos: tuple[float, float] | None) -> float | None:
        """Добавить позицию сапога (или None при промахе). Вернуть предсказание x или None."""
        if pos is not None:
            if self._prev is not None:
                self._vel = (pos[0] - self._prev[0], pos[1] - self._prev[1])
            self._prev = pos
            self._last = pos
        return self.predict()

    def predict(self) -> float | None:
        """Текущее предсказание точки падения по последней позиции и скорости."""
        if self._last is None or self._vel is None:
            return None
        return predict_landing_x(
            self._last[0], self._last[1], self._vel[0], self._vel[1],
            self.x_left, self.x_right, self.y_platform,
        )

    def reset(self) -> None:
        """Сбросить состояние (новый запуск сапога / новый уровень)."""
        self._prev = self._vel = self._last = None

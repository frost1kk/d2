"""Эмуляция ввода в игру: движение платформы (pydirectinput/SendInput).

⚠️ НЕ валидировано вживую. Обычный pyautogui игра на Source 2 часто игнорирует — используем
pydirectinput (SendInput). Направление: -1 влево, 0 стоять, +1 вправо (совпадает с control).

Реализация «удержание»: держим нажатой стрелку, пока цель в одной стороне, отпускаем при
смене направления/стопе. Это плавнее, чем частые тапы.
"""

from __future__ import annotations

from . import config
from .control import LEFT, RIGHT, STAY


class PlatformInput:
    """Управление платформой через удержание стрелок. Гарантирует отпускание клавиш."""

    def __init__(self) -> None:
        try:
            import pydirectinput
        except ImportError as exc:  # pragma: no cover
            raise ImportError(
                "input.py требует pydirectinput. Установи: pip install pydirectinput"
            ) from exc
        self._pdi = pydirectinput
        self._pdi.PAUSE = 0  # без искусственных задержек в горячем цикле
        self._held: str | None = None  # какая стрелка сейчас удерживается

    def apply(self, direction: int) -> None:
        """Привести удерживаемую клавишу в соответствие с направлением (-1/0/+1)."""
        want = {LEFT: config.KEY_LEFT, RIGHT: config.KEY_RIGHT, STAY: None}[direction]
        if want == self._held:
            return
        self._release()
        if want is not None:
            self._pdi.keyDown(want)
            self._held = want

    def launch(self) -> None:
        """Запустить сапог (пробел)."""
        self._pdi.press(config.KEY_LAUNCH)

    def _release(self) -> None:
        if self._held is not None:
            self._pdi.keyUp(self._held)
            self._held = None

    def stop(self) -> None:
        """Отпустить все клавиши — вызывать в finally и в kill-switch (§10)."""
        self._release()

    def __enter__(self) -> "PlatformInput":
        return self

    def __exit__(self, *exc) -> None:
        self.stop()

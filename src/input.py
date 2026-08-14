"""Эмуляция ввода в игру: движение платформы (pydirectinput/SendInput).

⚠️ Обычный pyautogui игра на Source 2 часто игнорирует — используем pydirectinput (SendInput).
Направление: -1 влево (A), 0 стоять, +1 вправо (D) — совпадает с control.

Движение: держим клавишу, пока цель в одной стороне (плавнее частых тапов).
Пуск/подтверждение (пробел): нажатие с УДЕРЖАНИЕМ ~KEY_TAP_HOLD_S — мгновенный keyDown/keyUp
игра нередко не успевает считать.
"""

from __future__ import annotations

import time

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

    def tap(self, key: str, hold: float | None = None) -> None:
        """Нажать клавишу с удержанием hold секунд (по умолчанию KEY_TAP_HOLD_S)."""
        hold = config.KEY_TAP_HOLD_S if hold is None else hold
        self._pdi.keyDown(key)
        time.sleep(hold)
        self._pdi.keyUp(key)

    def hold(self, key: str, seconds: float) -> None:
        """Удерживать клавишу seconds секунд (для калибровки движения тележки)."""
        self._release()
        self._pdi.keyDown(key)
        time.sleep(seconds)
        self._pdi.keyUp(key)

    def launch(self) -> None:
        """Пуск/подтверждение (пробел) с удержанием."""
        self.tap(config.KEY_LAUNCH)

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

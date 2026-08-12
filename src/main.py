"""Управляющий цикл бота: захват → детекция → трекинг → решение → ввод.

⚠️ НЕ валидировано вживую. Запускать ТОЛЬКО по явной просьбе пользователя (§10 CLAUDE.md):
бот перехватывает клавиатуру. Аварийный стоп — клавиша config.KEY_KILL (по умолчанию F12)
и Ctrl+C. При любом выходе клавиши гарантированно отпускаются.

Запуск:  python -m src.main
"""

from __future__ import annotations

import time

from . import config, detect
from .capture import Capturer
from .control import Controller
from .input import PlatformInput
from .track import BootTracker


def _make_kill_switch():
    """Вернуть функцию is_killed(). Если есть keyboard — слушаем KEY_KILL; иначе только Ctrl+C."""
    try:
        import keyboard

        keyboard.add_hotkey(config.KEY_KILL, lambda: None)  # регистрируем клавишу

        def is_killed() -> bool:
            return keyboard.is_pressed(config.KEY_KILL)

        print(f"Kill-switch: клавиша {config.KEY_KILL.upper()} или Ctrl+C")
        return is_killed
    except ImportError:
        print("Kill-switch: только Ctrl+C (для F12 установи: pip install keyboard)")
        return lambda: False


def run() -> None:
    cam = Capturer()
    controller = Controller(deadzone=config.CONTROL_DEADZONE_PX)
    is_killed = _make_kill_switch()

    # Инициализируем геометрию по первому кадру.
    frame = cam.grab_blocking()
    field = detect.detect_field(frame)
    platform_line = field.bottom  # линия, на которой ловим сапог (низ поля)
    tracker = BootTracker(x_left=field.left, x_right=field.right, y_platform=platform_line)

    loop_ms = 0.0
    with PlatformInput() as pinput:
        try:
            while not is_killed():
                t0 = time.perf_counter()

                frame = cam.grab()
                if frame is None:
                    continue

                cart = detect.detect_cart(frame, field)
                boot = detect.detect_boot(frame, field)

                boot_pos = (boot.x, boot.y) if boot else None
                target_x = tracker.update(boot_pos)

                if cart is not None:
                    direction = controller.decide(cart.x, target_x)
                    pinput.apply(direction)

                loop_ms = (time.perf_counter() - t0) * 1000.0
                if loop_ms > config.TARGET_LOOP_MS:
                    # Логируем превышение бюджета цикла (§7), но не спамим каждый кадр.
                    pass
        except KeyboardInterrupt:
            print("\nОстановлено (Ctrl+C).")
        finally:
            pinput.stop()
            print(f"Последний замер цикла: {loop_ms:.1f} мс")


if __name__ == "__main__":
    run()

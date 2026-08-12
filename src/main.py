"""Управляющий цикл бота: захват → детекция → трекинг → решение → ввод (A/D).

Конечный автомат с учётом стартовой секвенции мини-игры:
    SETUP  — сапог не в полёте. При --auto-launch выполняется пуск:
             центровка тележки (A/D) → пробел (фиксация позиции) →
             пробел (подтверждение направления) → сапог летит.
    PLAYING — сапог в полёте: двухрежимная ловля (следовать вверху / точный прицел на спуске).

⚠️ Управление перехватывает клавиатуру. Держи игру в фокусе. Аварийный стоп — F12
(нужен пакет keyboard) или Ctrl+C; при любом выходе клавиши отпускаются (§10 CLAUDE.md).

Запуск:
    python -m src.main               # автозапуск сапога включён
    python -m src.main --manual      # пуск руками, бот только ловит
    python -m src.main --delay 3     # пауза перед стартом (сделать игру активной)
"""

from __future__ import annotations

import argparse
import sys
import time

from . import config, detect
from .capture import Capturer
from .control import STAY, Controller, select_target
from .input import PlatformInput
from .track import BootTracker


def _make_kill_switch():
    """Вернуть функцию is_killed(): слушаем KEY_KILL (если есть keyboard), иначе Ctrl+C."""
    try:
        import keyboard

        def is_killed() -> bool:
            return keyboard.is_pressed(config.KEY_KILL)

        print(f"Kill-switch: клавиша {config.KEY_KILL.upper()} или Ctrl+C")
        return is_killed
    except ImportError:
        print("Kill-switch: только Ctrl+C (для F12 установи: pip install keyboard)")
        return lambda: False


def _center_cart(cam: Capturer, field, pinput: PlatformInput, controller: Controller) -> None:
    """Фаза позиции: подвести тележку к центру поля через A/D (предохранитель по шагам)."""
    for _ in range(config.LAUNCH_MAX_MOVE_STEPS):
        frame = cam.grab()
        if frame is None:
            continue
        cart = detect.detect_cart(frame, field)
        if cart is None:
            break
        direction = controller.decide(cart.x, field.center_x)
        if direction == STAY:
            break
        pinput.apply(direction)
        time.sleep(config.LAUNCH_MOVE_STEP_S)
    pinput.apply(STAY)


def _launch_sequence(cam: Capturer, field, pinput: PlatformInput, controller: Controller) -> None:
    """Стартовая секвенция: позиция → пробел → направление(по умолчанию) → пробел."""
    _center_cart(cam, field, pinput, controller)
    pinput.launch()  # зафиксировать позицию
    time.sleep(config.LAUNCH_STEP_PAUSE_S)
    pinput.launch()  # подтвердить направление пуска (значение по умолчанию)
    time.sleep(config.LAUNCH_STEP_PAUSE_S)


def run(auto_launch: bool = True, delay: float = 0.0) -> None:
    if delay > 0:
        print(f"Старт через {delay:.0f} с — сделай окно игры активным…")
        time.sleep(delay)

    cam = Capturer()
    controller = Controller(deadzone=config.CONTROL_DEADZONE_PX)
    is_killed = _make_kill_switch()

    frame = cam.grab_blocking()
    field = detect.detect_field(frame)
    blocks_line = detect.blocks_line_y(frame)
    tracker = BootTracker(x_left=field.left, x_right=field.right, y_platform=field.bottom)

    state = "SETUP"
    frames_seen = 0
    loop_ms_acc = 0.0
    last_ms = 0.0

    with PlatformInput() as pinput:
        try:
            if auto_launch:
                print("Автозапуск: центрирую тележку и запускаю сапог…")
                _launch_sequence(cam, field, pinput, controller)
                state = "PLAYING"

            while not is_killed():
                t0 = time.perf_counter()
                frame = cam.grab()
                if frame is None:
                    continue

                cart = detect.detect_cart(frame, field)
                boot = detect.detect_boot(frame, field)

                if boot is not None:
                    state = "PLAYING"
                    if cart is not None:
                        tracker.y_platform = cart.y
                    tracker.update((boot.x, boot.y))
                    predicted = tracker.predict() if config.USE_LANDING_PREDICTION else None
                    target = select_target(
                        (boot.x, boot.y), tracker.vy, predicted,
                        blocks_line, config.MAX_PREDICT_SHIFT_PX,
                    )
                    if cart is not None:
                        pinput.apply(controller.decide(cart.x, target))
                else:
                    pinput.apply(STAY)
                    if state == "PLAYING":
                        # Сапог пропал → мяч закончился. Возврат в SETUP.
                        state = "SETUP"
                        tracker.reset()
                        if auto_launch and not is_killed():
                            time.sleep(config.LAUNCH_STEP_PAUSE_S)
                            _launch_sequence(cam, field, pinput, controller)
                            state = "PLAYING"

                last_ms = (time.perf_counter() - t0) * 1000.0
                loop_ms_acc += last_ms
                frames_seen += 1
                if frames_seen % 120 == 0:
                    avg = loop_ms_acc / 120
                    print(f"[{state}] средний цикл {avg:.1f} мс (~{1000/avg:.0f} к/с)")
                    loop_ms_acc = 0.0
        except KeyboardInterrupt:
            print("\nОстановлено (Ctrl+C).")
        finally:
            pinput.stop()
            print(f"Последний замер цикла: {last_ms:.1f} мс")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Бот мини-игры «Сапожный снос»")
    parser.add_argument("--manual", action="store_true",
                        help="не запускать сапог автоматически (пуск руками, бот только ловит)")
    parser.add_argument("--delay", type=float, default=2.0,
                        help="пауза перед стартом, с (сделать игру активной); по умолчанию 2")
    args = parser.parse_args(argv)
    run(auto_launch=not args.manual, delay=args.delay)
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Управляющий цикл бота: захват → детекция → трекинг → решение → ввод (A/D).

Конечный автомат с учётом стартовой секвенции мини-игры:
    SETUP  — сапог не в полёте. При --auto-launch выполняется пуск:
             пробел (подтвердить старт) → пауза → пробел (запуск, направление по умолчанию).
    PLAYING — сапог в полёте: ловля (follow-x).

⚠️ Управление перехватывает клавиатуру. Держи игру в фокусе. Аварийный стоп — F12
(нужен пакет keyboard) или Ctrl+C; при любом выходе клавиши отпускаются (§10 CLAUDE.md).

Запуск:
    python -m src.main               # автозапуск сапога включён
    python -m src.main --manual      # пуск руками, бот только ловит
    python -m src.main --test-launch # прогнать ТОЛЬКО секвенцию пуска и выйти (подбор пауз)
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


def _launch_sequence(pinput: PlatformInput) -> None:
    """Стартовая секвенция: пробел (подтвердить старт) → пауза → пробел (запуск)."""
    print("  пуск: пробел (подтвердить старт)")
    pinput.launch()
    time.sleep(config.LAUNCH_CONFIRM_PAUSE_S)
    print("  пуск: пробел (запуск)")
    pinput.launch()
    time.sleep(config.LAUNCH_AFTER_PAUSE_S)


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
                print("Автозапуск сапога…")
                _launch_sequence(pinput)
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
                            _launch_sequence(pinput)
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


def test_launch(delay: float) -> None:
    """Прогнать ТОЛЬКО секвенцию пуска и выйти — для подбора пауз/удержания вживую."""
    if delay > 0:
        print(f"Старт через {delay:.0f} с — сделай окно игры активным…")
        time.sleep(delay)
    with PlatformInput() as pinput:
        print("Тест секвенции пуска:")
        _launch_sequence(pinput)
    print("Готово. Если сапог не полетел — правь LAUNCH_*_PAUSE_S / KEY_TAP_HOLD_S в config.py.")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Бот мини-игры «Сапожный снос»")
    parser.add_argument("--manual", action="store_true",
                        help="не запускать сапог автоматически (пуск руками, бот только ловит)")
    parser.add_argument("--test-launch", action="store_true",
                        help="прогнать только секвенцию пуска и выйти (подбор пауз)")
    parser.add_argument("--delay", type=float, default=2.0,
                        help="пауза перед стартом, с (сделать игру активной); по умолчанию 2")
    args = parser.parse_args(argv)
    if args.test_launch:
        test_launch(args.delay)
        return 0
    run(auto_launch=not args.manual, delay=args.delay)
    return 0


if __name__ == "__main__":
    sys.exit(main())

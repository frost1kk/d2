"""Управляющий цикл бота: захват → детекция → трекинг → решение → ввод (A/D).

Единая модель состояний (по кадру), надёжна для всех уровней и переходов между ними:
    PLAY — сапог ЛЕТИТ (большой разброс y за окно) → ловим (follow-x).
    AIM  — сапог ВИСИТ в пред-пуске/прицеле (y почти постоянна) → жмём пробел (запуск),
           тележку не двигаем (чтобы не сбивать прицел).
    LOST — сапога нет (меню/переход между уровнями) → после дебаунса жмём пробел (проходим).
Нажатия пробела — с кулдауном LAUNCH_COOLDOWN_S (без спама). Так один и тот же механизм
проходит старт, пред-пуск, потерю мяча и экраны «уровень пройден → новый пуск».
При --manual пробел не жмётся: бот только ловит летящий сапог.

⚠️ Управление перехватывает клавиатуру. Держи игру в фокусе. Аварийный стоп — F12
(нужен пакет keyboard) или Ctrl+C; при любом выходе клавиши отпускаются (§10 CLAUDE.md).

Запуск:
    python -m src.main               # автозапуск сапога включён
    python -m src.main --manual      # пуск руками, бот только ловит
    python -m src.main --test-launch # прогнать ТОЛЬКО секвенцию пуска и выйти (подбор пауз)
    python -m src.main --calibrate   # проверить направление/скорость тележки (D, затем A)
    python -m src.main --log run.csv # писать CSV-лог сессии для диагностики ловли
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


def _read_cart_x(cam: Capturer, field, retries: int = 40) -> float | None:
    """Дождаться кадра и вернуть x тележки (для калибровки)."""
    for _ in range(retries):
        frame = cam.grab()
        if frame is None:
            continue
        cart = detect.detect_cart(frame, field)
        if cart is not None:
            return cart.x
    return None


def calibrate(delay: float, hold: float = 0.4) -> None:
    """Проверить направление и скорость тележки: нажать D, затем A, замерить сдвиг x.

    Запускать на экране, где A/D двигают тележку (выбор позиции ИЛИ во время полёта).
    """
    if delay > 0:
        print(f"Старт через {delay:.0f} с — открой экран, где тележка двигается (A/D)…")
        time.sleep(delay)
    cam = Capturer()
    field = detect.detect_field(cam.grab_blocking())
    with PlatformInput() as pinput:
        x0 = _read_cart_x(cam, field)
        print(f"тележка x0 = {x0}")
        if x0 is None:
            print("Тележка не детектируется — проверь, что открыт нужный экран.")
            return
        pinput.hold(config.KEY_RIGHT, hold)
        time.sleep(0.15)
        xd = _read_cart_x(cam, field)
        pinput.hold(config.KEY_LEFT, hold)
        time.sleep(0.15)
        xa = _read_cart_x(cam, field)
    d_delta = (xd - x0) if xd is not None else None
    a_delta = (xa - xd) if (xa is not None and xd is not None) else None
    print(f"D ({config.KEY_RIGHT!r}, ожидаем вправо +x): сдвиг {d_delta:+.0f} px" if d_delta is not None else "D: тележка не найдена после нажатия")
    print(f"A ({config.KEY_LEFT!r}, ожидаем влево −x): сдвиг {a_delta:+.0f} px" if a_delta is not None else "A: тележка не найдена после нажатия")
    if d_delta is not None and a_delta is not None:
        if d_delta > 5 and a_delta < -5:
            print(f"✅ направление верное; скорость ~{abs(d_delta)/hold:.0f} px/с")
        elif d_delta < -5 and a_delta > 5:
            print("❗ ИНВЕРСИЯ: D едет влево, A вправо → поменяй местами KEY_LEFT/KEY_RIGHT в config.py")
        else:
            print("❗ тележка почти не сдвинулась — клавиши не доходят до игры или экран не тот")


def run(auto_launch: bool = True, delay: float = 0.0, log_path: str | None = None,
        sweep: bool = False) -> None:
    if delay > 0:
        print(f"Старт через {delay:.0f} с — сделай окно игры активным…")
        time.sleep(delay)

    cam = Capturer()
    controller = Controller(deadzone=config.CONTROL_DEADZONE_PX)
    is_killed = _make_kill_switch()

    frame = cam.grab_blocking()
    field = detect.detect_field(frame)
    blocks_line = detect.blocks_line_y(frame)
    sweep_arm_y = detect._scale_y(config.SWEEP_ARM_Y_PX, frame.shape[0])
    tracker = BootTracker(x_left=field.left, x_right=field.right, y_platform=field.bottom)

    from collections import deque

    recent_y: deque[float] = deque(maxlen=config.FLIGHT_WINDOW)
    miss_count = 0          # подряд кадров без сапога
    aim_spaces = 0          # нажатий пробела в текущем «зависании» (защита от спама)
    aim_warned = False
    last_space = 0.0        # perf_counter последнего нажатия пробела (кулдаун)
    state = "LOST"
    frames_seen = 0
    loop_ms_acc = 0.0
    last_ms = 0.0
    # --- состояние свипа ---
    sweep_idx = -1          # первый заход выберет SWEEP_OFFSETS[0]
    commanded_offset = 0    # до первого захода — нейтрально
    sweep_armed = False     # сапог заходит на касание (спускается в зоне тележки)
    last_present_y: float | None = None
    if sweep:
        print(f"РЕЖИМ СВИПА: смещения {config.SWEEP_OFFSETS} px, перебор по касаниям.")
    log = open(log_path, "w", encoding="utf-8") if log_path else None
    if log:
        log.write("frame,state,boot_x,boot_y,cart_x,target,direction,commanded_offset,loop_ms\n")

    def maybe_space() -> bool:
        """Нажать пробел, если прошёл кулдаун (запуск/проход экранов). Вернуть, нажали ли."""
        nonlocal last_space
        if not auto_launch:
            return False
        now = time.perf_counter()
        if now - last_space >= config.LAUNCH_COOLDOWN_S:
            pinput.launch()
            last_space = now
            return True
        return False

    with PlatformInput() as pinput:
        try:
            while not is_killed():
                t0 = time.perf_counter()
                frame = cam.grab()
                if frame is None:
                    continue

                cart = detect.detect_cart(frame, field)
                boot = detect.detect_boot(frame, field)
                target = None
                direction = STAY

                if boot is not None:
                    prev_y = last_present_y
                    last_present_y = boot.y
                    miss_count = 0
                    recent_y.append(boot.y)
                    in_flight = (
                        len(recent_y) >= config.MIN_FLIGHT_POINTS
                        and (max(recent_y) - min(recent_y)) > config.FLIGHT_Y_RANGE_PX
                    )
                    if in_flight:
                        # Сапог летит → ловим (follow-x).
                        state = "PLAY"
                        aim_spaces = 0
                        aim_warned = False
                        if cart is not None:
                            tracker.y_platform = cart.y
                        tracker.update((boot.x, boot.y))
                        # Свип: на заходе в зону касания (начало спуска) выбираем следующее
                        # смещение — оно держится весь спуск и контакт; на подъёме разоружаем.
                        if sweep and prev_y is not None:
                            vy = boot.y - prev_y
                            if not sweep_armed and vy > 0 and boot.y > sweep_arm_y:
                                sweep_idx = (sweep_idx + 1) % len(config.SWEEP_OFFSETS)
                                commanded_offset = config.SWEEP_OFFSETS[sweep_idx]
                                sweep_armed = True
                            elif sweep_armed and vy < 0:
                                sweep_armed = False
                        predicted = tracker.predict() if config.USE_LANDING_PREDICTION else None
                        if sweep:
                            # Ставим тележку со смещением: цель = boot.x − смещение (в пределах поля).
                            target = max(field.left, min(field.right, boot.x - commanded_offset))
                        else:
                            target = select_target(
                                (boot.x, boot.y), tracker.vy, predicted,
                                blocks_line, config.MAX_PREDICT_SHIFT_PX,
                            )
                        if cart is not None:
                            direction = controller.decide(cart.x, target)
                            pinput.apply(direction)
                    else:
                        # Сапог «висит» → пробуем запустить пробелом (ограниченно). Если не полетел
                        # после AIM_MAX_SPACES — это ложная детекция фона, перестаём жать.
                        state = "AIM"
                        pinput.apply(STAY)
                        tracker.reset()
                        if aim_spaces < config.AIM_MAX_SPACES:
                            if maybe_space():
                                aim_spaces += 1
                        elif not aim_warned:
                            print(f"⚠ сапог «висит» на ({boot.x:.0f},{boot.y:.0f}) и не запускается "
                                  f"после {config.AIM_MAX_SPACES} нажатий — вероятно, ложная детекция.")
                            aim_warned = True
                else:
                    miss_count += 1
                    pinput.apply(STAY)
                    if miss_count >= config.BALL_LOST_FRAMES:
                        # Устойчивое отсутствие = меню/переход между уровнями → проходим пробелом.
                        state = "LOST"
                        recent_y.clear()
                        tracker.reset()
                        aim_spaces = 0
                        aim_warned = False
                        last_present_y = None
                        sweep_armed = False
                        maybe_space()
                    else:
                        # Краткий пропуск (сапог нырнул к тележке) — держим, НЕ чистим окно,
                        # чтобы полёт продолжил ловиться сразу после появления сапога.
                        state = "MISS"

                last_ms = (time.perf_counter() - t0) * 1000.0
                loop_ms_acc += last_ms
                frames_seen += 1
                if log:
                    bx = f"{boot.x:.0f}" if boot else ""
                    by = f"{boot.y:.0f}" if boot else ""
                    cx = f"{cart.x:.0f}" if cart else ""
                    tg = f"{target:.0f}" if target is not None else ""
                    co = f"{commanded_offset:+d}" if sweep else ""
                    log.write(f"{frames_seen},{state},{bx},{by},{cx},{tg},{direction},{co},{last_ms:.1f}\n")
                if frames_seen % 120 == 0:
                    avg = loop_ms_acc / 120
                    print(f"[{state}] средний цикл {avg:.1f} мс (~{1000/avg:.0f} к/с)")
                    loop_ms_acc = 0.0
        except KeyboardInterrupt:
            print("\nОстановлено (Ctrl+C).")
        finally:
            pinput.stop()
            if log:
                log.close()
                print(f"Лог сессии → {log_path}")
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
    parser.add_argument("--calibrate", action="store_true",
                        help="проверить направление и скорость тележки (нажать D, затем A)")
    parser.add_argument("--log", metavar="PATH",
                        help="писать CSV-лог сессии (boot/cart/target/direction/latency) для диагностики")
    parser.add_argument("--sweep", action="store_true",
                        help="режим сбора данных: намеренно варьировать смещение точки касания "
                             "(нужен --log для анализа)")
    parser.add_argument("--delay", type=float, default=2.0,
                        help="пауза перед стартом, с (сделать игру активной); по умолчанию 2")
    args = parser.parse_args(argv)
    if args.test_launch:
        test_launch(args.delay)
        return 0
    if args.calibrate:
        calibrate(args.delay)
        return 0
    if args.sweep and not args.log:
        args.log = "debug/sweep.csv"
        print("(--sweep без --log: пишу в debug/sweep.csv)")
    run(auto_launch=not args.manual, delay=args.delay, log_path=args.log, sweep=args.sweep)
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Юнит-тесты трекинга/предсказания траектории (чистая математика, без игры)."""

from __future__ import annotations

import math

import pytest

from src.track import BootTracker, predict_landing_x, reflect_1d


class TestReflect1d:
    def test_inside_returns_value(self):
        assert reflect_1d(50, 0, 100) == 50

    def test_single_bounce_right(self):
        # 130 в отрезке [0,100] → один отскок → 70
        assert reflect_1d(130, 0, 100) == 70

    def test_single_bounce_left(self):
        # -30 в [0,100] → отскок от левой стенки → 30
        assert reflect_1d(-30, 0, 100) == 30

    def test_multiple_bounces(self):
        # 310 в [0,100] → несколько отскоков → 90 (ручная проверка развёртки)
        assert reflect_1d(310, 0, 100) == 90

    def test_nonzero_offset_walls(self):
        # отрезок [100, 500], width=400; 550 → отскок → 450
        assert reflect_1d(550, 100, 500) == 450

    def test_on_boundary(self):
        assert reflect_1d(100, 0, 100) == 100
        assert reflect_1d(0, 0, 100) == 0

    def test_invalid_walls_raise(self):
        with pytest.raises(ValueError):
            reflect_1d(5, 100, 100)
        with pytest.raises(ValueError):
            reflect_1d(5, 100, 0)


class TestPredictLandingX:
    def test_straight_down(self):
        # вертикальное падение → x не меняется
        assert predict_landing_x(300, 100, 0, 5, 100, 500, 800) == 300

    def test_diagonal_no_wall(self):
        # x=200,y=0, наклон vx/vy=1, до y=100 → +100 по x → 300 (внутри поля)
        assert predict_landing_x(200, 0, 1, 1, 0, 1000, 100) == 300

    def test_diagonal_with_bounce(self):
        # x_raw=130 в [0,100] → отскок → 70
        got = predict_landing_x(90, 0, 4, 1, 0, 100, 10)  # t=10, x_raw=90+40=130
        assert got == 70

    def test_moving_up_returns_none(self):
        # vy<=0 — сапог летит вверх, к платформе не идёт
        assert predict_landing_x(300, 400, 2, -5, 0, 600, 800) is None

    def test_already_below_platform_returns_none(self):
        assert predict_landing_x(300, 850, 0, 5, 0, 600, 800) is None

    def test_invalid_walls_raise(self):
        with pytest.raises(ValueError):
            predict_landing_x(300, 100, 0, 5, 500, 100, 800)

    def test_realistic_slope(self):
        # правдоподобная траектория: с (455,250) вниз-вправо к платформе y=790
        got = predict_landing_x(455, 250, 3, 6, 165, 800, 790)
        assert got is not None
        assert 165 <= got <= 800


class TestBootTracker:
    def test_needs_two_points_for_velocity(self):
        t = BootTracker(x_left=0, x_right=600, y_platform=800)
        assert t.update((300, 100)) is None  # ещё нет скорости

    def test_predicts_after_two_points_descending(self):
        t = BootTracker(x_left=0, x_right=600, y_platform=800)
        t.update((300, 100))
        got = t.update((300, 200))  # vy=+100, vx=0 → падение прямо вниз
        assert got == 300

    def test_ascending_gives_none(self):
        t = BootTracker(x_left=0, x_right=600, y_platform=800)
        t.update((300, 400))
        got = t.update((305, 300))  # летит вверх (vy=-100)
        assert got is None

    def test_missing_detection_keeps_velocity(self):
        t = BootTracker(x_left=0, x_right=600, y_platform=800)
        t.update((300, 100))
        t.update((300, 200))
        got = t.update(None)  # промах детекции — предсказание не рвётся
        assert got == 300

    def test_reset_clears_state(self):
        t = BootTracker(x_left=0, x_right=600, y_platform=800)
        t.update((300, 100))
        t.update((300, 200))
        t.reset()
        assert t.predict() is None

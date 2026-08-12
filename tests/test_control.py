"""Юнит-тесты управляющей логики (чистая логика, без игры/ввода)."""

from __future__ import annotations

from src.control import LEFT, RIGHT, STAY, Controller, decide_direction, select_target


class TestDecideDirection:
    def test_target_right(self):
        assert decide_direction(100, 200, deadzone=8) == RIGHT

    def test_target_left(self):
        assert decide_direction(200, 100, deadzone=8) == LEFT

    def test_within_deadzone_stays(self):
        assert decide_direction(100, 105, deadzone=8) == STAY
        assert decide_direction(100, 95, deadzone=8) == STAY

    def test_exactly_on_deadzone_edge_stays(self):
        assert decide_direction(100, 108, deadzone=8) == STAY

    def test_just_outside_deadzone_moves(self):
        assert decide_direction(100, 109, deadzone=8) == RIGHT

    def test_none_target_stays(self):
        assert decide_direction(100, None, deadzone=8) == STAY


class TestController:
    def test_wraps_decide_direction(self):
        c = Controller(deadzone=5)
        assert c.decide(100, 200) == RIGHT
        assert c.decide(200, 100) == LEFT
        assert c.decide(100, 102) == STAY
        assert c.decide(100, None) == STAY


class TestSelectTarget:
    BLOCKS = 640

    def test_no_boot_returns_none(self):
        assert select_target(None, vy=5, predicted_x=500, blocks_line_y=self.BLOCKS) is None

    def test_below_line_descending_uses_prediction(self):
        # сапог в нижней зоне и падает → целимся в предсказанную точку падения
        got = select_target((900, 700), vy=10, predicted_x=512, blocks_line_y=self.BLOCKS)
        assert got == 512

    def test_above_line_follows_boot_x(self):
        # сапог вверху среди блоков → следуем за его x, а не за (шумным) предсказанием
        got = select_target((900, 300), vy=10, predicted_x=512, blocks_line_y=self.BLOCKS)
        assert got == 900

    def test_below_line_but_ascending_follows_boot_x(self):
        # ниже линии, но летит вверх (vy<0) — предсказания точки падения нет → следуем
        got = select_target((900, 700), vy=-10, predicted_x=512, blocks_line_y=self.BLOCKS)
        assert got == 900

    def test_below_line_descending_but_no_prediction_follows(self):
        got = select_target((900, 700), vy=10, predicted_x=None, blocks_line_y=self.BLOCKS)
        assert got == 900

    def test_exactly_on_line_counts_as_below(self):
        got = select_target((900, 640), vy=10, predicted_x=512, blocks_line_y=self.BLOCKS)
        assert got == 512

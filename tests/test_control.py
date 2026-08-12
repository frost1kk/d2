"""Юнит-тесты управляющей логики (чистая логика, без игры/ввода)."""

from __future__ import annotations

from src.control import LEFT, RIGHT, STAY, Controller, decide_direction


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

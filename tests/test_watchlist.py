import pytest
from cogs.watchlist import _direction_from_price, _gap_pct


class TestDirectionFromPrice:
    def test_target_above_current(self):
        assert _direction_from_price(100.0, 150.0) == "above"

    def test_target_below_current(self):
        assert _direction_from_price(100.0, 50.0) == "below"

    def test_target_equal_current(self):
        # equal target is treated as "below" (not strictly above)
        assert _direction_from_price(100.0, 100.0) == "below"


class TestGapPct:
    def test_positive_gap(self):
        result = _gap_pct(100.0, 110.0, "above")
        assert result == "+10.00%"

    def test_negative_gap(self):
        result = _gap_pct(100.0, 90.0, "below")
        assert result == "-10.00%"

    def test_zero_gap(self):
        result = _gap_pct(100.0, 100.0, "above")
        assert result == "+0.00%"

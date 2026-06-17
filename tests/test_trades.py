import pytest
from cogs.trades import _pnl, _since, _size_str


class TestPnl:
    def test_long_profit(self):
        assert _pnl("long", 100.0, 150.0, 10, None) == pytest.approx(500.0)

    def test_long_loss(self):
        assert _pnl("long", 150.0, 100.0, 10, None) == pytest.approx(-500.0)

    def test_long_breakeven(self):
        assert _pnl("long", 100.0, 100.0, 10, None) == pytest.approx(0.0)

    def test_short_profit(self):
        # Short $10k notional at $100, price drops to $50 → 100 shares × $50 gain = $5000
        assert _pnl("short", 100.0, 50.0, None, 10_000) == pytest.approx(5000.0)

    def test_short_loss(self):
        # Short $10k notional at $100, price rises to $150 → 100 shares × $50 loss = -$5000
        assert _pnl("short", 100.0, 150.0, None, 10_000) == pytest.approx(-5000.0)

    def test_short_breakeven(self):
        assert _pnl("short", 100.0, 100.0, None, 10_000) == pytest.approx(0.0)

    def test_long_zero_shares(self):
        assert _pnl("long", 100.0, 200.0, 0, None) == pytest.approx(0.0)

    def test_short_zero_notional(self):
        assert _pnl("short", 100.0, 50.0, None, 0) == pytest.approx(0.0)


class TestSince:
    def test_returns_string(self):
        result = _since("2026-06-01 10:00:00")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_invalid_date_returns_question_mark(self):
        assert _since("not-a-date") == "?"

    def test_empty_string_returns_question_mark(self):
        assert _since("") == "?"


class TestSizeStr:
    def test_long(self):
        assert _size_str("long", 100.0, None, 50.0) == "100.00 sh"

    def test_short(self):
        assert _size_str("short", None, 50_000.0, 100.0) == "$50,000 notional"

    def test_long_fractional_shares(self):
        assert _size_str("long", 0.5, None, 100.0) == "0.50 sh"

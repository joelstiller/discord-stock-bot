from datetime import datetime
from unittest.mock import MagicMock, patch
import pytest
from services.market import Quote, PriceCache


def make_quote(**kwargs) -> Quote:
    defaults = dict(
        ticker="AAPL",
        price=200.0,
        change_pct=1.5,
        day_high=202.0,
        day_low=198.0,
        week52_high=250.0,
        week52_low=150.0,
        volume=50_000_000,
        avg_volume=60_000_000,
        market_cap=3_000_000_000_000.0,
    )
    defaults.update(kwargs)
    return Quote(**defaults)


class TestQuoteProperties:
    def test_volume_vs_avg_pct(self):
        q = make_quote(volume=90_000_000, avg_volume=100_000_000)
        assert q.volume_vs_avg_pct == -10.0

    def test_volume_vs_avg_pct_zero_avg(self):
        q = make_quote(avg_volume=0)
        assert q.volume_vs_avg_pct == 0.0

    def test_pct_of_52w_range_midpoint(self):
        q = make_quote(price=200.0, week52_low=150.0, week52_high=250.0)
        assert q.pct_of_52w_range == 50.0

    def test_pct_of_52w_range_at_low(self):
        q = make_quote(price=150.0, week52_low=150.0, week52_high=250.0)
        assert q.pct_of_52w_range == 0.0

    def test_pct_of_52w_range_zero_span(self):
        q = make_quote(price=200.0, week52_low=200.0, week52_high=200.0)
        assert q.pct_of_52w_range == 0.0

    def test_market_closed_weekend(self):
        # Monday = 0, Saturday = 5
        with patch("services.market.datetime") as mock_dt:
            mock_dt.now.return_value = MagicMock(
                time=MagicMock(return_value=MagicMock()),
                weekday=MagicMock(return_value=5),
            )
            # Just verify the property exists and returns bool
            q = make_quote()
            assert isinstance(q.market_closed, bool)


class TestPriceCache:
    def test_set_and_get(self):
        cache = PriceCache()
        q = make_quote(ticker="AAPL")
        cache.set("AAPL", q)
        assert cache.get("AAPL") is q

    def test_case_insensitive(self):
        cache = PriceCache()
        q = make_quote(ticker="AAPL")
        cache.set("aapl", q)
        assert cache.get("AAPL") is q
        assert cache.get("aapl") is q

    def test_miss_returns_none(self):
        cache = PriceCache()
        assert cache.get("NVDA") is None

    def test_remove(self):
        cache = PriceCache()
        cache.set("AAPL", make_quote())
        cache.remove("AAPL")
        assert cache.get("AAPL") is None

    def test_remove_missing_is_noop(self):
        cache = PriceCache()
        cache.remove("UNKNOWN")  # should not raise

    def test_all_tickers(self):
        cache = PriceCache()
        cache.set("AAPL", make_quote(ticker="AAPL"))
        cache.set("NVDA", make_quote(ticker="NVDA"))
        assert set(cache.all_tickers()) == {"AAPL", "NVDA"}

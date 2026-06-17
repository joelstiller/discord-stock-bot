import pytest
from services.ai import _parse_signal, _build_prompt
from services.market import Quote
from datetime import datetime


def make_quote(**kwargs) -> Quote:
    defaults = dict(
        ticker="AAPL", price=200.0, change_pct=1.5,
        day_high=202.0, day_low=198.0,
        week52_high=250.0, week52_low=150.0,
        volume=50_000_000, avg_volume=60_000_000,
        market_cap=3_000_000_000_000.0,
    )
    defaults.update(kwargs)
    return Quote(**defaults)


class TestParseSignal:
    def test_buy(self):
        text = "Looks good.\nSignal: BUY\nConfidence: High"
        assert _parse_signal(text) == ("BUY", "High")

    def test_sell(self):
        text = "Bad news.\nSignal: SELL\nConfidence: Medium"
        assert _parse_signal(text) == ("SELL", "Medium")

    def test_hold(self):
        text = "Unclear.\nSignal: HOLD\nConfidence: Low"
        assert _parse_signal(text) == ("HOLD", "Low")

    def test_defaults_when_missing(self):
        assert _parse_signal("No signal here at all.") == ("HOLD", "Low")

    def test_case_insensitive_signal(self):
        text = "signal: buy\nconfidence: high"
        assert _parse_signal(text) == ("BUY", "High")

    def test_invalid_signal_ignored(self):
        text = "Signal: MAYBE\nConfidence: High"
        signal, confidence = _parse_signal(text)
        assert signal == "HOLD"  # falls back to default

    def test_invalid_confidence_ignored(self):
        text = "Signal: BUY\nConfidence: Kinda"
        signal, confidence = _parse_signal(text)
        assert confidence == "Low"  # falls back to default

    def test_deepseek_think_tags_stripped_upstream(self):
        """Verify _parse_signal still works after <think> tags are stripped."""
        import re
        raw = "<think>Lots of reasoning here...</think>\nGood stock.\nSignal: BUY\nConfidence: High"
        cleaned = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip()
        assert _parse_signal(cleaned) == ("BUY", "High")


class TestBuildPrompt:
    def test_contains_ticker(self):
        q = make_quote(ticker="NVDA")
        prompt = _build_prompt(q, {"pe": "30", "sector": "Tech", "trend": "+5%"}, ["Headline 1"])
        assert "NVDA" in prompt

    def test_no_headlines_fallback(self):
        q = make_quote()
        prompt = _build_prompt(q, {"pe": "N/A", "sector": "N/A", "trend": "N/A"}, [])
        assert "No recent headlines available" in prompt

    def test_market_cap_formatted(self):
        q = make_quote(market_cap=3_000_000_000_000.0)
        prompt = _build_prompt(q, {"pe": "N/A", "sector": "N/A", "trend": "N/A"}, [])
        assert "$3000.00B" in prompt

    def test_no_market_cap(self):
        q = make_quote(market_cap=None)
        prompt = _build_prompt(q, {"pe": "N/A", "sector": "N/A", "trend": "N/A"}, [])
        assert "N/A" in prompt

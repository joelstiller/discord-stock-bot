import asyncio
import logging
import math
from dataclasses import dataclass, field
from datetime import datetime, time, timezone, timedelta
from functools import partial
from typing import Optional

import yfinance as yf

log = logging.getLogger("stonks.market")

ET = timezone(timedelta(hours=-5))  # ET (no DST adjustment — close enough for open/close check)
MARKET_OPEN = time(9, 30)
MARKET_CLOSE = time(16, 0)


@dataclass
class Quote:
    ticker: str
    price: float
    change_pct: float
    day_high: float
    day_low: float
    week52_high: float
    week52_low: float
    volume: int
    avg_volume: int
    market_cap: Optional[float]
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def volume_vs_avg_pct(self) -> float:
        if not self.avg_volume:
            return 0.0
        return round((self.volume / self.avg_volume - 1) * 100, 1)

    @property
    def pct_of_52w_range(self) -> float:
        span = self.week52_high - self.week52_low
        if not span:
            return 0.0
        return round((self.price - self.week52_low) / span * 100, 1)

    @property
    def market_closed(self) -> bool:
        now_et = datetime.now(ET).time()
        weekday = datetime.now(ET).weekday()
        return weekday >= 5 or not (MARKET_OPEN <= now_et <= MARKET_CLOSE)


class PriceCache:
    def __init__(self):
        self._data: dict[str, Quote] = {}

    def get(self, ticker: str) -> Optional[Quote]:
        return self._data.get(ticker.upper())

    def set(self, ticker: str, quote: Quote):
        self._data[ticker.upper()] = quote

    def all_tickers(self) -> list[str]:
        return list(self._data.keys())

    def remove(self, ticker: str):
        self._data.pop(ticker.upper(), None)


def _fetch_quotes_sync(tickers: list[str]) -> dict[str, Quote]:
    if not tickers:
        return {}
    results: dict[str, Quote] = {}
    for ticker in tickers:
        try:
            t = yf.Ticker(ticker)
            info = t.fast_info
            raw_price = info.last_price or info.previous_close
            if not raw_price or math.isnan(raw_price):
                log.warning("No price data for %s — likely invalid ticker", ticker)
                continue
            price = float(raw_price)
            prev_close = float(info.previous_close or price)
            change_pct = round((price - prev_close) / prev_close * 100, 2) if prev_close else 0.0
            results[ticker.upper()] = Quote(
                ticker=ticker.upper(),
                price=price,
                change_pct=change_pct,
                day_high=float(info.day_high or price),
                day_low=float(info.day_low or price),
                week52_high=float(info.year_high or price),
                week52_low=float(info.year_low or price),
                volume=int(info.last_volume or 0),
                avg_volume=int(info.three_month_average_volume or 0),
                market_cap=float(info.market_cap) if info.market_cap else None,
            )
        except Exception as exc:
            log.warning("Failed to fetch %s: %s", ticker, exc)
    return results


FETCH_TIMEOUT = 15


async def fetch_quotes(tickers: list[str]) -> dict[str, Quote]:
    loop = asyncio.get_running_loop()
    try:
        return await asyncio.wait_for(
            loop.run_in_executor(None, partial(_fetch_quotes_sync, tickers)),
            timeout=FETCH_TIMEOUT * max(len(tickers), 1),
        )
    except asyncio.TimeoutError:
        log.warning("fetch_quotes timed out for %s", tickers)
        return {}


async def fetch_one(ticker: str) -> Optional[Quote]:
    loop = asyncio.get_running_loop()
    try:
        results = await asyncio.wait_for(
            loop.run_in_executor(None, partial(_fetch_quotes_sync, [ticker])),
            timeout=FETCH_TIMEOUT,
        )
        return results.get(ticker.upper())
    except asyncio.TimeoutError:
        log.warning("fetch_one timed out for %s", ticker)
        return None


def is_market_open() -> bool:
    now_et = datetime.now(ET).time()
    weekday = datetime.now(ET).weekday()
    return weekday < 5 and MARKET_OPEN <= now_et <= MARKET_CLOSE

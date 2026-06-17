import asyncio
import logging
import re
import aiohttp
from services.market import Quote

log = logging.getLogger("stonks.ai")

PROMPT_TEMPLATE = """\
You are a professional stock analyst. Analyze the data below and provide a concise 3-4 sentence \
analysis followed by a clear signal.

Ticker: {ticker}
Current Price: ${price:,.2f} ({change_pct:+.2f}% today)
52-Week Range: ${low52:,.2f} – ${high52:,.2f} (currently at {pct_of_range:.1f}% of range)
30-Day Trend: {trend}
Volume: {volume:,} ({volume_vs_avg:+.1f}% vs 3-month average)
Market Cap: {market_cap}
P/E Ratio: {pe}
Sector: {sector}

Recent News Headlines:
{headlines}

Respond with your analysis followed by exactly this format on separate lines:
Signal: BUY
Confidence: High

Valid signals: BUY, HOLD, SELL
Valid confidence levels: High, Medium, Low
"""


def _build_prompt(quote: Quote, extras: dict, news: list[str]) -> str:
    market_cap = f"${quote.market_cap / 1e9:.2f}B" if quote.market_cap else "N/A"
    headlines = "\n".join(f"- {h}" for h in news) if news else "- No recent headlines available"
    return PROMPT_TEMPLATE.format(
        ticker=quote.ticker,
        price=quote.price,
        change_pct=quote.change_pct,
        low52=quote.week52_low,
        high52=quote.week52_high,
        pct_of_range=quote.pct_of_52w_range,
        trend=extras.get("trend", "N/A"),
        volume=quote.volume,
        volume_vs_avg=quote.volume_vs_avg_pct,
        market_cap=market_cap,
        pe=extras.get("pe", "N/A"),
        sector=extras.get("sector", "N/A"),
        headlines=headlines,
    )


def _parse_signal(text: str) -> tuple[str, str]:
    signal = "HOLD"
    confidence = "Low"
    for line in text.splitlines():
        lower = line.lower().strip()
        if lower.startswith("signal:"):
            val = line.split(":", 1)[1].strip().upper()
            if val in ("BUY", "HOLD", "SELL"):
                signal = val
        elif lower.startswith("confidence:"):
            val = line.split(":", 1)[1].strip().title()
            if val in ("High", "Medium", "Low"):
                confidence = val
    return signal, confidence


async def analyze(quote: Quote, extras: dict, news: list[str], base_url: str, model: str) -> dict:
    prompt = _build_prompt(quote, extras, news)
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.3},
    }
    log.info("Sending prompt to %s for %s:\n%s", model, quote.ticker, prompt)
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(f"{base_url}/api/generate", json=payload, timeout=aiohttp.ClientTimeout(total=120)) as resp:
                resp.raise_for_status()
                data = await resp.json()
                response_text = data.get("response", "")
    except Exception as exc:
        log.error("Ollama request failed: %s", exc)
        raise
    log.info("DeepSeek response for %s:\n%s", quote.ticker, response_text)

    # Strip DeepSeek-R1 chain-of-thought blocks before parsing
    response_text = re.sub(r"<think>.*?</think>", "", response_text, flags=re.DOTALL).strip()

    signal, confidence = _parse_signal(response_text)
    analysis_body = response_text
    for marker in ("Signal:", "Confidence:"):
        idx = analysis_body.find(marker)
        if idx != -1:
            analysis_body = analysis_body[:idx].strip()

    return {
        "signal": signal,
        "confidence": confidence,
        "analysis": analysis_body,
        "raw": response_text,
    }

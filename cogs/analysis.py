import asyncio
import logging
from datetime import datetime, timezone, timedelta
from functools import partial

import discord
import yfinance as yf
from discord import app_commands
from discord.ext import commands

from bot import stonks_only
from services.market import fetch_one
from services import ai
import config

log = logging.getLogger("stonks.analysis")

SIGNAL_COLORS = {
    "BUY": discord.Color.green(),
    "HOLD": discord.Color.yellow(),
    "SELL": discord.Color.red(),
}
SIGNAL_EMOJI = {"BUY": "🟢", "HOLD": "🟡", "SELL": "🔴"}

ET = timezone(timedelta(hours=-5))


def _fetch_extras_sync(ticker: str) -> dict:
    t = yf.Ticker(ticker)
    try:
        info = t.info or {}
    except Exception:
        info = {}
    try:
        news_items = t.news or []
        headlines = [
            item.get("content", {}).get("title") or item.get("title", "")
            for item in news_items[:8]
            if item.get("content", {}).get("title") or item.get("title")
        ]
    except Exception:
        headlines = []
    try:
        hist = t.history(period="30d")
        if len(hist) >= 2:
            start = float(hist["Close"].iloc[0])
            end = float(hist["Close"].iloc[-1])
            trend = f"{(end - start) / start * 100:+.2f}% over 30 days"
        else:
            trend = "N/A"
    except Exception:
        trend = "N/A"
    return {
        "pe": info.get("trailingPE", "N/A"),
        "sector": info.get("sector", "N/A"),
        "trend": trend,
        "headlines": headlines,
    }


class AnalysisCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="analyze", description="AI-powered BUY / HOLD / SELL analysis for a stock")
    @app_commands.describe(ticker="Stock ticker, e.g. AAPL")
    @stonks_only()
    async def analyze(self, interaction: discord.Interaction, ticker: str):
        ticker = ticker.upper().strip()
        await interaction.response.defer()

        quote = self.bot.price_cache.get(ticker) or await fetch_one(ticker)
        if not quote:
            await interaction.followup.send(f"Could not find data for **{ticker}**.")
            return
        self.bot.price_cache.set(ticker, quote)

        await interaction.followup.send(
            f"Analyzing **{ticker}** with `{config.OLLAMA_MODEL}`... this may take up to 60 seconds."
        )

        loop = asyncio.get_running_loop()
        try:
            extras = await asyncio.wait_for(
                loop.run_in_executor(None, partial(_fetch_extras_sync, ticker)),
                timeout=20,
            )
        except asyncio.TimeoutError:
            log.warning("Extras fetch timed out for %s — proceeding without news/history", ticker)
            extras = {"pe": "N/A", "sector": "N/A", "trend": "N/A", "headlines": []}

        try:
            result = await ai.analyze(
                quote=quote,
                extras=extras,
                news=extras["headlines"],
                base_url=config.OLLAMA_BASE_URL,
                model=config.OLLAMA_MODEL,
            )
        except Exception as exc:
            log.error("Analysis failed for %s: %s", ticker, exc)
            await interaction.followup.send(
                f"AI analysis failed for **{ticker}**. Is Ollama running? (`{config.OLLAMA_BASE_URL}`)"
            )
            return

        signal = result["signal"]
        confidence = result["confidence"]
        emoji = SIGNAL_EMOJI.get(signal, "⚪")
        color = SIGNAL_COLORS.get(signal, discord.Color.greyple())

        now_et = datetime.now(ET).strftime("%H:%M ET")
        embed = discord.Embed(
            title=f"${ticker} Analysis",
            description=result["analysis"],
            color=color,
        )
        embed.add_field(name="Signal", value=f"**{emoji} {signal}**", inline=True)
        embed.add_field(name="Confidence", value=confidence, inline=True)
        embed.add_field(name="Price", value=f"${quote.price:,.2f} ({quote.change_pct:+.2f}%)", inline=True)
        embed.set_footer(text=f"Data as of {now_et} · {config.OLLAMA_MODEL}")

        await interaction.followup.send(embed=embed)


async def setup(bot):
    await bot.add_cog(AnalysisCog(bot))

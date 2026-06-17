import logging
import discord
from discord import app_commands
from discord.ext import commands
from bot import stonks_only
from services.market import fetch_one, is_market_open

log = logging.getLogger("stonks.prices")


def _price_embed(quote) -> discord.Embed:
    sign = "+" if quote.change_pct >= 0 else ""
    color = discord.Color.green() if quote.change_pct >= 0 else discord.Color.red()
    closed_note = "  *(market closed — last close)*" if quote.market_closed else ""

    embed = discord.Embed(
        title=f"${quote.ticker}",
        color=color,
    )
    embed.add_field(name="Price", value=f"**${quote.price:,.2f}**{closed_note}", inline=True)
    embed.add_field(name="Change", value=f"{sign}{quote.change_pct:.2f}%", inline=True)
    embed.add_field(name="​", value="​", inline=True)
    embed.add_field(name="Day High", value=f"${quote.day_high:,.2f}", inline=True)
    embed.add_field(name="Day Low", value=f"${quote.day_low:,.2f}", inline=True)
    embed.add_field(name="​", value="​", inline=True)
    embed.add_field(name="52W High", value=f"${quote.week52_high:,.2f}", inline=True)
    embed.add_field(name="52W Low", value=f"${quote.week52_low:,.2f}", inline=True)
    embed.add_field(name="52W Position", value=f"{quote.pct_of_52w_range:.1f}%", inline=True)
    vol_vs = f"{quote.volume_vs_avg_pct:+.1f}% vs avg" if quote.avg_volume else "N/A"
    embed.add_field(name="Volume", value=f"{quote.volume:,}  ({vol_vs})", inline=False)
    if quote.market_cap:
        embed.set_footer(text=f"Mkt Cap: ${quote.market_cap / 1e9:.2f}B")
    return embed


class PricesCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="price", description="Get the current price for a stock ticker")
    @app_commands.describe(ticker="Stock ticker symbol, e.g. AAPL")
    @stonks_only()
    async def price(self, interaction: discord.Interaction, ticker: str):
        ticker = ticker.upper().strip()
        await interaction.response.defer()

        cached = self.bot.price_cache.get(ticker) is not None
        quote = self.bot.price_cache.get(ticker)
        if not quote:
            quote = await fetch_one(ticker)
            if not quote:
                log.warning("/price %s by %s — not found", ticker, interaction.user)
                await interaction.followup.send(f"**{ticker}** not found. Check the symbol and try again.")
                return
            self.bot.price_cache.set(ticker, quote)

        log.info("/price %s by %s — $%.2f (%s)", ticker, interaction.user, quote.price, "cached" if cached else "fetched")
        await interaction.followup.send(embed=_price_embed(quote))


async def setup(bot):
    await bot.add_cog(PricesCog(bot))

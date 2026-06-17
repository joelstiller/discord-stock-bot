import logging
import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime, timezone, UTC

from bot import stonks_only
from services import db
from services.market import fetch_one

log = logging.getLogger("stonks.trades")


def _pnl(side: str, entry: float, current: float, shares: float | None, notional: float | None) -> float:
    if side == "long":
        return (current - entry) * (shares or 0)
    else:
        qty = (notional or 0) / entry
        return (entry - current) * qty


def _size_str(side: str, shares: float | None, notional: float | None, entry: float) -> str:
    if side == "long":
        return f"{shares:,.2f} sh"
    return f"${(notional or 0):,.0f} notional"


def _since(entry_time: str) -> str:
    try:
        dt = datetime.fromisoformat(entry_time)
        delta = datetime.now(UTC) - dt.replace(tzinfo=UTC)
        if delta.days:
            return f"{delta.days}d"
        hours = delta.seconds // 3600
        return f"{hours}h" if hours else "<1h"
    except Exception:
        return "?"


class TradesCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="long", description="Open a theoretical long position")
    @app_commands.describe(
        ticker="Stock ticker, e.g. AAPL",
        shares="Number of shares",
        price="Entry price (defaults to current market price)",
    )
    @stonks_only()
    async def long(self, interaction: discord.Interaction, ticker: str, shares: float, price: float | None = None):
        ticker = ticker.upper().strip()
        if shares <= 0:
            await interaction.response.send_message("Shares must be greater than zero.", ephemeral=True)
            return
        await interaction.response.defer()

        if price is None:
            quote = self.bot.price_cache.get(ticker) or await fetch_one(ticker)
            if not quote:
                await interaction.followup.send(f"Could not fetch price for **{ticker}**.")
                return
            price = quote.price
            if quote:
                self.bot.price_cache.set(ticker, quote)

        num = await db.fetchone(
            "SELECT COALESCE(MAX(user_trade_num), 0) + 1 AS n FROM trades WHERE user_id = ?",
            (str(interaction.user.id),),
        )
        trade_num = num["n"]

        await db.execute(
            """INSERT INTO trades (user_trade_num, user_id, guild_id, ticker, side, shares, entry_price)
               VALUES (?, ?, ?, ?, 'long', ?, ?)""",
            (trade_num, str(interaction.user.id), str(interaction.guild_id), ticker, shares, price),
        )

        embed = discord.Embed(
            title=f"Long opened — {ticker}",
            color=discord.Color.green(),
        )
        embed.add_field(name="Trade #", value=str(trade_num), inline=True)
        embed.add_field(name="Shares", value=f"{shares:,.2f}", inline=True)
        embed.add_field(name="Entry", value=f"${price:,.2f}", inline=True)
        embed.add_field(name="Total Cost", value=f"${shares * price:,.2f}", inline=True)
        log.info("/long #%d %s %.2f sh @ $%.2f by %s", trade_num, ticker, shares, price, interaction.user)
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="short", description="Open a theoretical short position")
    @app_commands.describe(
        ticker="Stock ticker, e.g. AAPL",
        notional="Dollar amount to short, e.g. 100000",
        price="Entry price (defaults to current market price)",
    )
    @stonks_only()
    async def short(self, interaction: discord.Interaction, ticker: str, notional: float, price: float | None = None):
        ticker = ticker.upper().strip()
        if notional <= 0:
            await interaction.response.send_message("Notional must be greater than zero.", ephemeral=True)
            return
        await interaction.response.defer()

        if price is None:
            quote = self.bot.price_cache.get(ticker) or await fetch_one(ticker)
            if not quote:
                await interaction.followup.send(f"Could not fetch price for **{ticker}**.")
                return
            price = quote.price
            if quote:
                self.bot.price_cache.set(ticker, quote)

        num = await db.fetchone(
            "SELECT COALESCE(MAX(user_trade_num), 0) + 1 AS n FROM trades WHERE user_id = ?",
            (str(interaction.user.id),),
        )
        trade_num = num["n"]

        await db.execute(
            """INSERT INTO trades (user_trade_num, user_id, guild_id, ticker, side, notional, entry_price)
               VALUES (?, ?, ?, ?, 'short', ?, ?)""",
            (trade_num, str(interaction.user.id), str(interaction.guild_id), ticker, notional, price),
        )

        embed = discord.Embed(
            title=f"Short opened — {ticker}",
            color=discord.Color.red(),
        )
        embed.add_field(name="Trade #", value=str(trade_num), inline=True)
        embed.add_field(name="Notional", value=f"${notional:,.0f}", inline=True)
        embed.add_field(name="Entry", value=f"${price:,.2f}", inline=True)
        shares_eq = notional / price
        embed.add_field(name="Shares Equiv.", value=f"{shares_eq:,.2f}", inline=True)
        log.info("/short #%d %s $%.0f notional @ $%.2f by %s", trade_num, ticker, notional, price, interaction.user)
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="trades", description="List your theoretical positions with live P&L")
    @app_commands.describe(filter="Show open positions only (default) or all")
    @app_commands.choices(filter=[
        app_commands.Choice(name="open", value="open"),
        app_commands.Choice(name="all", value="all"),
    ])
    @stonks_only()
    async def trades(self, interaction: discord.Interaction, filter: str = "open"):
        await interaction.response.defer()

        where = "WHERE user_id = ? AND closed = 0" if filter == "open" else "WHERE user_id = ?"
        rows = await db.fetchall(
            f"SELECT * FROM trades {where} ORDER BY user_trade_num",
            (str(interaction.user.id),),
        )

        if not rows:
            await interaction.followup.send("You have no trades yet. Use `/long` or `/short` to open one.")
            return

        tickers = list({r["ticker"] for r in rows if not r["closed"]})
        prices: dict[str, float] = {}
        for t in tickers:
            q = self.bot.price_cache.get(t) or await fetch_one(t)
            if q:
                prices[t] = q.price
                self.bot.price_cache.set(t, q)

        lines = []
        total_pnl = 0.0
        for r in rows:
            ticker = r["ticker"]
            entry = r["entry_price"]
            side = r["side"]
            current = r["exit_price"] if r["closed"] else prices.get(ticker, entry)
            pnl = _pnl(side, entry, current, r["shares"], r["notional"])
            total_pnl += pnl
            sign = "+" if pnl >= 0 else ""
            status = "CLOSED" if r["closed"] else _since(r["entry_time"])
            size = _size_str(side, r["shares"], r["notional"], entry)
            lines.append(
                f"`#{r['user_trade_num']}` **{ticker}** {side.upper()}  {size}  "
                f"@ ${entry:,.2f} → ${current:,.2f}  **{sign}${pnl:,.2f}**  *{status}*"
            )

        total_sign = "+" if total_pnl >= 0 else ""
        description = "\n".join(lines)
        if len(description) > 4000:
            description = description[:4000] + "\n*…truncated — use `/trades open` to see open positions only*"

        embed = discord.Embed(
            title=f"{interaction.user.display_name}'s Trades ({filter})",
            description=description,
            color=discord.Color.green() if total_pnl >= 0 else discord.Color.red(),
        )
        embed.set_footer(text=f"Total P&L: {total_sign}${total_pnl:,.2f}")
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="close", description="Close one of your theoretical positions")
    @app_commands.describe(
        trade_id="Your trade number (shown in /trades)",
        price="Exit price (defaults to current market price)",
    )
    @stonks_only()
    async def close(self, interaction: discord.Interaction, trade_id: int, price: float | None = None):
        await interaction.response.defer()

        row = await db.fetchone(
            "SELECT * FROM trades WHERE user_id = ? AND user_trade_num = ?",
            (str(interaction.user.id), trade_id),
        )
        if not row:
            await interaction.followup.send(f"Trade #{trade_id} not found.")
            return
        if row["closed"]:
            await interaction.followup.send(f"Trade #{trade_id} is already closed.")
            return

        if price is None:
            ticker = row["ticker"]
            quote = self.bot.price_cache.get(ticker) or await fetch_one(ticker)
            if not quote:
                await interaction.followup.send(f"Could not fetch current price for **{ticker}**.")
                return
            price = quote.price
            self.bot.price_cache.set(ticker, quote)

        await db.execute(
            "UPDATE trades SET closed = 1, exit_price = ?, exit_time = datetime('now') WHERE id = ?",
            (price, row["id"]),
        )

        pnl = _pnl(row["side"], row["entry_price"], price, row["shares"], row["notional"])
        sign = "+" if pnl >= 0 else ""
        color = discord.Color.green() if pnl >= 0 else discord.Color.red()

        embed = discord.Embed(
            title=f"Trade #{trade_id} closed — {row['ticker']}",
            color=color,
        )
        embed.add_field(name="Side", value=row["side"].upper(), inline=True)
        embed.add_field(name="Entry", value=f"${row['entry_price']:,.2f}", inline=True)
        embed.add_field(name="Exit", value=f"${price:,.2f}", inline=True)
        embed.add_field(name="P&L", value=f"**{sign}${pnl:,.2f}**", inline=False)
        log.info("/close #%d %s @ $%.2f P&L %s$%.2f by %s", trade_id, row["ticker"], price, sign, abs(pnl), interaction.user)
        await interaction.followup.send(embed=embed)


async def setup(bot):
    await bot.add_cog(TradesCog(bot))

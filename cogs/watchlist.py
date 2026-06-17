import asyncio
import logging
import discord
from discord import app_commands
from discord.ext import commands, tasks

from bot import stonks_only
from services import db
from services.market import fetch_quotes, fetch_one, is_market_open
import config

log = logging.getLogger("stonks.watchlist")


def _direction_from_price(current: float, target: float) -> str:
    return "above" if target > current else "below"


def _gap_pct(current: float, target: float, direction: str) -> str:
    gap = (target - current) / current * 100
    return f"{gap:+.2f}%"


class WatchlistCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.poll_loop.start()

    def cog_unload(self):
        self.poll_loop.cancel()

    # ------------------------------------------------------------------ #
    # Commands
    # ------------------------------------------------------------------ #

    @app_commands.command(name="watch", description="Set a price alert for a stock")
    @app_commands.describe(
        ticker="Stock ticker, e.g. AAPL",
        target="Target price to alert at",
        direction="Alert when price goes above or below target (auto-detected if omitted)",
    )
    @app_commands.choices(direction=[
        app_commands.Choice(name="above", value="above"),
        app_commands.Choice(name="below", value="below"),
    ])
    @stonks_only()
    async def watch(
        self,
        interaction: discord.Interaction,
        ticker: str,
        target: float,
        direction: str | None = None,
    ):
        ticker = ticker.upper().strip()
        await interaction.response.defer()

        quote = self.bot.price_cache.get(ticker) or await fetch_one(ticker)
        if not quote:
            await interaction.followup.send(f"Could not find data for **{ticker}**.")
            return
        self.bot.price_cache.set(ticker, quote)

        if direction is None:
            direction = _direction_from_price(quote.price, target)

        existing = await db.fetchone(
            "SELECT id FROM watchlist WHERE user_id = ? AND ticker = ? AND triggered = 0",
            (str(interaction.user.id), ticker),
        )
        if existing:
            await db.execute(
                "UPDATE watchlist SET target = ?, direction = ? WHERE id = ?",
                (target, direction, existing["id"]),
            )
            action = "updated"
        else:
            await db.execute(
                """INSERT INTO watchlist (user_id, guild_id, ticker, target, direction)
                   VALUES (?, ?, ?, ?, ?)""",
                (str(interaction.user.id), str(interaction.guild_id), ticker, target, direction),
            )
            action = "added"

        gap = _gap_pct(quote.price, target, direction)
        embed = discord.Embed(
            title=f"Watch {action} — {ticker}",
            color=discord.Color.blurple(),
        )
        embed.add_field(name="Current Price", value=f"${quote.price:,.2f}", inline=True)
        embed.add_field(name="Target", value=f"${target:,.2f} ({direction})", inline=True)
        embed.add_field(name="Gap", value=gap, inline=True)
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="unwatch", description="Remove a price alert")
    @app_commands.describe(ticker="Stock ticker to stop watching")
    @stonks_only()
    async def unwatch(self, interaction: discord.Interaction, ticker: str):
        ticker = ticker.upper().strip()
        row = await db.fetchone(
            "SELECT id FROM watchlist WHERE user_id = ? AND ticker = ? AND triggered = 0",
            (str(interaction.user.id), ticker),
        )
        if not row:
            await interaction.response.send_message(f"No active watch found for **{ticker}**.", ephemeral=True)
            return
        await db.execute("DELETE FROM watchlist WHERE id = ?", (row["id"],))
        await interaction.response.send_message(f"Removed watch for **{ticker}**.", ephemeral=True)

    @app_commands.command(name="watchlist", description="Show your active price alerts")
    @stonks_only()
    async def watchlist(self, interaction: discord.Interaction):
        await self._show_watchlist(interaction, interaction.user)

    @app_commands.command(name="view", description="View another user's watchlist")
    @app_commands.describe(user="The user whose watchlist you want to see")
    @stonks_only()
    async def view(self, interaction: discord.Interaction, user: discord.Member):
        await self._show_watchlist(interaction, user)

    async def _show_watchlist(self, interaction: discord.Interaction, user: discord.Member | discord.User):
        await interaction.response.defer()
        rows = await db.fetchall(
            "SELECT * FROM watchlist WHERE user_id = ? AND triggered = 0 ORDER BY ticker",
            (str(user.id),),
        )
        if not rows:
            await interaction.followup.send(f"**{user.display_name}** has no active watches.")
            return

        tickers = list({r["ticker"] for r in rows})
        missing = [t for t in tickers if not self.bot.price_cache.get(t)]
        if missing:
            fresh = await fetch_quotes(missing)
            for t, q in fresh.items():
                self.bot.price_cache.set(t, q)

        lines = []
        for r in rows:
            ticker = r["ticker"]
            quote = self.bot.price_cache.get(ticker)
            current_str = f"${quote.price:,.2f}" if quote else "N/A"
            gap_str = _gap_pct(quote.price, r["target"], r["direction"]) if quote else "N/A"
            lines.append(
                f"**{ticker}** — target ${r['target']:,.2f} ({r['direction']})  "
                f"current {current_str}  gap {gap_str}"
            )

        embed = discord.Embed(
            title=f"{user.display_name}'s Watchlist",
            description="\n".join(lines),
            color=discord.Color.blurple(),
        )
        await interaction.followup.send(embed=embed)

    # ------------------------------------------------------------------ #
    # Background poller
    # ------------------------------------------------------------------ #

    @tasks.loop(seconds=config.POLL_INTERVAL_SECONDS)
    async def poll_loop(self):
        if not is_market_open():
            return
        if not self.bot.stonks_channel:
            return

        # Build unified active ticker set: watchlist + open trades
        watch_rows = await db.fetchall("SELECT DISTINCT ticker FROM watchlist WHERE triggered = 0")
        trade_rows = await db.fetchall("SELECT DISTINCT ticker FROM trades WHERE closed = 0")
        tickers = list({r["ticker"] for r in watch_rows} | {r["ticker"] for r in trade_rows})

        if not tickers:
            return

        quotes = await fetch_quotes(tickers)
        for ticker, quote in quotes.items():
            self.bot.price_cache.set(ticker, quote)

        # Check alert conditions
        active_watches = await db.fetchall("SELECT * FROM watchlist WHERE triggered = 0")
        for row in active_watches:
            ticker = row["ticker"]
            quote = quotes.get(ticker)
            if not quote:
                continue

            triggered = (
                (row["direction"] == "above" and quote.price >= row["target"]) or
                (row["direction"] == "below" and quote.price <= row["target"])
            )
            if not triggered:
                continue

            user = self.bot.get_user(int(row["user_id"]))
            mention = user.mention if user else f"<@{row['user_id']}>"
            sign = "+" if quote.change_pct >= 0 else ""

            embed = discord.Embed(
                title=f"Price Alert — {ticker}",
                color=discord.Color.green() if row["direction"] == "above" else discord.Color.red(),
            )
            embed.add_field(name="Current Price", value=f"${quote.price:,.2f}", inline=True)
            embed.add_field(name="Target", value=f"${row['target']:,.2f} ({row['direction']})", inline=True)
            embed.add_field(name="Day Change", value=f"{sign}{quote.change_pct:.2f}%", inline=True)
            embed.set_footer(text=f"Alert triggered for {mention}")

            try:
                await self.bot.stonks_channel.send(content=mention, embed=embed)
            except Exception as exc:
                log.error("Failed to send alert for %s user %s: %s", ticker, row["user_id"], exc)
                continue  # don't mark triggered — will retry next poll

            await db.execute("UPDATE watchlist SET triggered = 1 WHERE id = ?", (row["id"],))
            log.info("Alert fired: %s @ $%.2f for user %s", ticker, quote.price, row["user_id"])

    @poll_loop.error
    async def poll_loop_error(self, exc: Exception):
        log.error("Poll loop crashed: %s", exc, exc_info=exc)

    @poll_loop.before_loop
    async def before_poll(self):
        await self.bot.wait_until_ready()


async def setup(bot):
    await bot.add_cog(WatchlistCog(bot))

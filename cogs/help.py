import discord
from discord import app_commands
from discord.ext import commands


HELP_TEXT = """
**PRICES**
`/price <ticker>` — Current price, change %, high/low, volume

**WATCHLIST**
`/watch <ticker> <target> [above|below]` — Add a price alert
`/unwatch <ticker>` — Remove an alert
`/watchlist` — Show your active watches
`/view <@user>` — See another user's watchlist

**TRADES**
`/long <ticker> <shares> [price]` — Open a theoretical long position
`/short <ticker> <notional> [price]` — Open a theoretical short position
`/trades [open|all]` — List your positions with live P&L
`/close <trade_id> [price]` — Close a position

**ANALYSIS**
`/analyze <ticker>` — AI-powered BUY / HOLD / SELL signal via DeepSeek
"""


class HelpCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="help", description="Show all available bot commands")
    async def help(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="Stonks Bot Commands",
            description=HELP_TEXT,
            color=discord.Color.blurple(),
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(HelpCog(bot))

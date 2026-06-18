import asyncio
import logging
import pathlib
from logging.handlers import TimedRotatingFileHandler
import discord
from discord.ext import commands
import config
from services.db import init_db
from services.market import PriceCache

LOG_DIR = pathlib.Path(__file__).parent / "logs"
LOG_DIR.mkdir(exist_ok=True)

_fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")

_file_handler = TimedRotatingFileHandler(
    LOG_DIR / "stonks.log",
    when="midnight",
    backupCount=30,
    encoding="utf-8",
)
_file_handler.setFormatter(_fmt)

_console_handler = logging.StreamHandler()
_console_handler.setFormatter(_fmt)

logging.basicConfig(level=logging.INFO, handlers=[_file_handler, _console_handler])
log = logging.getLogger("stonks")

COGS = [
    "cogs.prices",
    "cogs.trades",
    "cogs.watchlist",
    "cogs.analysis",
    "cogs.help",
]

intents = discord.Intents.default()
intents.message_content = False


class StonksBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)
        self.price_cache = PriceCache()
        self.stonks_channel: discord.TextChannel | None = None

    async def setup_hook(self):
        await init_db()
        for cog in COGS:
            await self.load_extension(cog)
            log.info("Loaded cog: %s", cog)
        await self.tree.sync()
        log.info("Cogs loaded, global commands synced")

    async def on_ready(self):
        log.info("Logged in as %s (id=%s)", self.user, self.user.id)
        for guild in self.guilds:
            ch = discord.utils.get(guild.text_channels, name=config.STONKS_CHANNEL_NAME)
            if ch:
                self.stonks_channel = ch
                log.info("Found #%s in guild '%s'", config.STONKS_CHANNEL_NAME, guild.name)

            # Guild sync is instant vs global sync which can take up to an hour
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
            log.info("Slash commands synced to guild '%s'", guild.name)

        if not self.stonks_channel:
            log.warning("Could not find channel #%s", config.STONKS_CHANNEL_NAME)


def stonks_only():
    """Slash command check: only allow commands in #stonks."""
    async def predicate(interaction: discord.Interaction) -> bool:
        bot: StonksBot = interaction.client
        if bot.stonks_channel is None:
            await interaction.response.send_message(
                f"Bot is not configured — could not find channel **#{config.STONKS_CHANNEL_NAME}**.",
                ephemeral=True,
            )
            return False
        if interaction.channel_id != bot.stonks_channel.id:
            await interaction.response.send_message(
                f"Please use commands in <#{bot.stonks_channel.id}>.",
                ephemeral=True,
            )
            return False
        return True
    return discord.app_commands.check(predicate)


async def main():
    bot = StonksBot()
    async with bot:
        await bot.start(config.DISCORD_TOKEN)


if __name__ == "__main__":
    asyncio.run(main())

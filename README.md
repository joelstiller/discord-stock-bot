# Discord Stock Bot

A Discord bot for tracking theoretical stock trades, setting price alerts, and getting AI-powered BUY/HOLD/SELL signals — all inside a single `#stonks` channel.

## Features

- **`/price`** — Live quote with day change, high/low, volume, and 52-week range
- **`/long` / `/short`** — Open theoretical positions (by shares or dollar notional)
- **`/trades`** — View open positions with live P&L
- **`/close`** — Close a position at current or custom price
- **`/watch`** — Set a price alert; bot pings you in `#stonks` when it triggers
- **`/watchlist` / `/view`** — See your own or another user's active watches
- **`/analyze`** — AI-powered analysis with a BUY / HOLD / SELL signal via DeepSeek-R1
- **`/help`** — List all commands

## Requirements

- Python 3.11+
- [Ollama](https://ollama.com) running locally with `deepseek-r1:32b` pulled
- A Discord bot token ([create one here](https://discord.com/developers/applications))
- A Discord server with a channel named `#stonks`

## Setup

**1. Clone and create a virtual environment**
```bash
git clone https://github.com/joelstiller/discord-stock-bot.git
cd discord-stock-bot
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

**2. Configure environment**
```bash
cp .env.example .env
```
Edit `.env` and fill in your Discord token:
```
DISCORD_TOKEN=your_token_here
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=deepseek-r1:32b
STONKS_CHANNEL_NAME=stonks
POLL_INTERVAL_SECONDS=60
```

**3. Pull the AI model**
```bash
ollama pull deepseek-r1:32b
```

**4. Run the bot**
```bash
.venv/bin/python bot.py
```

## Production (systemd)

A service file is included. Install it as a user service:

```bash
cp discord-stock-bot.service ~/.config/systemd/user/
# Edit the WorkingDirectory and ExecStart paths if needed
systemctl --user daemon-reload
systemctl --user enable --now discord-stock-bot
loginctl enable-linger $USER   # keep running after logout
```

## Discord App Setup

1. Go to [discord.com/developers/applications](https://discord.com/developers/applications) → **New Application**
2. Under **Bot**, click **Reset Token** and copy it into `.env`
3. Under **OAuth2 → URL Generator**, select scopes: `bot` + `applications.commands`
4. Select permissions: **Send Messages**, **Embed Links**
5. Open the generated URL in your browser and add the bot to your server

## Running Tests

```bash
.venv/bin/pytest tests/ -v
```

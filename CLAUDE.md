# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Run all tests
.venv/bin/pytest tests/ -v

# Run a single test file
.venv/bin/pytest tests/test_ai.py -v

# Run a single test
.venv/bin/pytest tests/test_ai.py::TestParseSignal::test_buy -v

# Start the bot directly (dev)
.venv/bin/python bot.py

# Manage the production service
systemctl --user start|stop|restart|status discord-stock-bot
journalctl --user -u discord-stock-bot -f

# Manage Ollama (system service, requires sudo)
sudo systemctl start|stop|restart|status ollama
```

## Architecture

The bot is a discord.py app with slash commands only (no prefix commands). All commands are restricted to a single channel (`#stonks`) enforced by the `stonks_only()` check in `bot.py`.

**Request flow:**
1. Slash command → cog in `cogs/` → reads from `bot.price_cache` (in-memory) first
2. On cache miss → `services/market.py` fetches from yfinance in a thread executor with a 15s timeout
3. Background poller (`WatchlistCog.poll_loop`) runs every 60s during US market hours only (Mon–Fri 09:30–16:00 ET), batches all active watchlist + open trade tickers into a single `yf.download()` call, and refreshes the cache

**Key design points:**
- `PriceCache` is a plain dict on the `StonksBot` instance — all cogs access it via `self.bot.price_cache`
- yfinance rejects external sessions (newer versions) — do not pass `session=` to `yf.Ticker()` or `yf.download()`
- `FastInfo` attribute names: use `year_high`/`year_low` (not `fifty_two_week_high/low`), `last_volume` (not `shares`)
- Trade IDs (`user_trade_num`) are per-user sequential — assigned at insert via `SELECT MAX(...) + 1 WHERE user_id = ?`
- Alert send order matters: send the Discord message first, then mark `triggered=1` in DB — if the send fails, the alert retries next poll
- DeepSeek-R1 wraps reasoning in `<think>...</think>` blocks — these are stripped in `services/ai.py` before parsing the signal

**Services:**
- `services/db.py` — thin async wrappers over a single `aiosqlite` connection initialised at startup via `init_db()`
- `services/market.py` — `PriceCache` class + `fetch_one()`/`fetch_quotes()` async wrappers that run yfinance in `run_in_executor`
- `services/ai.py` — builds the prompt, POSTs to Ollama's `/api/generate`, strips think tags, parses `Signal:` / `Confidence:` lines

**Deployment:**
- Bot: `~/.config/systemd/user/discord-stock-bot.service` (user service, linger enabled)
- Ollama: `/etc/systemd/system/ollama.service` (system service)
- Logs rotate daily into `logs/stonks.log`, kept 30 days
- Model: `deepseek-r1:32b` at Q4_K_M (~20GB VRAM), configured via `OLLAMA_MODEL` in `.env`

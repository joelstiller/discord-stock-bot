CREATE TABLE IF NOT EXISTS watchlist (
    id          INTEGER PRIMARY KEY,
    user_id     TEXT NOT NULL,
    guild_id    TEXT NOT NULL,
    ticker      TEXT NOT NULL,
    target      REAL,
    direction   TEXT CHECK(direction IN ('above','below')),
    triggered   INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS trades (
    id              INTEGER PRIMARY KEY,
    user_trade_num  INTEGER NOT NULL,
    user_id         TEXT NOT NULL,
    guild_id        TEXT NOT NULL,
    ticker          TEXT NOT NULL,
    side            TEXT NOT NULL CHECK(side IN ('long','short')),
    shares          REAL,
    notional        REAL,
    entry_price     REAL NOT NULL,
    entry_time      TEXT NOT NULL DEFAULT (datetime('now')),
    exit_price      REAL,
    exit_time       TEXT,
    closed          INTEGER NOT NULL DEFAULT 0,
    UNIQUE(user_id, user_trade_num)
);

import aiosqlite
import pathlib

DB_PATH = pathlib.Path(__file__).parent.parent / "bot.db"
SCHEMA_PATH = pathlib.Path(__file__).parent.parent / "schema.sql"

_db: aiosqlite.Connection | None = None


async def init_db():
    global _db
    _db = await aiosqlite.connect(DB_PATH)
    _db.row_factory = aiosqlite.Row
    await _db.execute("PRAGMA journal_mode=WAL")
    schema = SCHEMA_PATH.read_text()
    await _db.executescript(schema)
    await _db.commit()
    await _migrate(_db)


async def _migrate(conn: aiosqlite.Connection):
    # Make watchlist.target and .direction nullable (SQLite requires table recreation)
    async with conn.execute("PRAGMA table_info(watchlist)") as cur:
        cols = {row["name"]: row for row in await cur.fetchall()}
    if cols.get("target") and cols["target"]["notnull"]:
        await conn.executescript("""
            ALTER TABLE watchlist RENAME TO watchlist_old;
            CREATE TABLE watchlist (
                id          INTEGER PRIMARY KEY,
                user_id     TEXT NOT NULL,
                guild_id    TEXT NOT NULL,
                ticker      TEXT NOT NULL,
                target      REAL,
                direction   TEXT CHECK(direction IN ('above','below')),
                triggered   INTEGER NOT NULL DEFAULT 0,
                created_at  TEXT NOT NULL DEFAULT (datetime('now'))
            );
            INSERT INTO watchlist SELECT * FROM watchlist_old;
            DROP TABLE watchlist_old;
        """)
        await conn.commit()


def get_db() -> aiosqlite.Connection:
    assert _db is not None, "DB not initialised — call init_db() first"
    return _db


async def fetchall(sql: str, params: tuple = ()) -> list[aiosqlite.Row]:
    async with get_db().execute(sql, params) as cur:
        return await cur.fetchall()


async def fetchone(sql: str, params: tuple = ()) -> aiosqlite.Row | None:
    async with get_db().execute(sql, params) as cur:
        return await cur.fetchone()


async def execute(sql: str, params: tuple = ()) -> int:
    """Run a write statement, commit, and return lastrowid."""
    async with get_db().execute(sql, params) as cur:
        await get_db().commit()
        return cur.lastrowid

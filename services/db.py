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

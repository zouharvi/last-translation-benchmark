import asyncio

from last_translation_benchmark.db import _open_db


async def _migrate_table(db, table):
    async with db.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table,),
    ) as cur:
        row = await cur.fetchone()
    if row is None:
        raise RuntimeError(f"{table.capitalize()} table not found.")

    if "AUTOINCREMENT" in row[0].upper():
        return

    new_table = f"{table}_new"
    await db.execute(
        f"CREATE TABLE {new_table} "
        "(id INTEGER PRIMARY KEY AUTOINCREMENT, data TEXT NOT NULL)"
    )
    await db.execute(
        f"INSERT INTO {new_table} (id, data) SELECT id, data FROM {table}"
    )
    await db.execute(f"DROP TABLE {table}")
    await db.execute(f"ALTER TABLE {new_table} RENAME TO {table}")


async def migrate():
    async with _open_db() as db:
        await db.execute("BEGIN EXCLUSIVE")
        try:
            await _migrate_table(db, "users")
            await _migrate_table(db, "submissions")
            await db.commit()
        except Exception:
            await db.rollback()
            raise


if __name__ == "__main__":
    asyncio.run(migrate())

import json
import os
import secrets

import aiosqlite

from .utils import CONTRIBUTOR_QUOTA_DEFAULT, DB_PATH


def _open_db():
    db_dir = os.path.dirname(DB_PATH)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)
    return aiosqlite.connect(DB_PATH)


_TABLES = {"users", "submissions"}


async def _next_id(table: str) -> int:
    if table not in _TABLES:
        raise ValueError(f"Invalid table: {table}")
    async with _open_db() as db:
        async with db.execute(f"SELECT MAX(id) FROM {table}") as cur:  # noqa: S608
            row = await cur.fetchone()
            return (row[0] or 0) + 1


# --- Users ---


async def get_users() -> list[dict]:
    async with _open_db() as db:
        async with db.execute("SELECT data FROM users") as cur:
            return [json.loads(r[0]) for r in await cur.fetchall()]


async def get_user_by_username(username: str) -> dict | None:
    users = await get_users()
    return next((u for u in users if u["username"] == username), None)


async def get_user_by_id(uid: int) -> dict | None:
    async with _open_db() as db:
        async with db.execute("SELECT data FROM users WHERE id = ?", (uid,)) as cur:
            row = await cur.fetchone()
            return json.loads(row[0]) if row else None


async def save_user(user: dict) -> None:
    async with _open_db() as db:
        await db.execute(
            "INSERT OR REPLACE INTO users (id, data) VALUES (?, ?)",
            (user["id"], json.dumps(user)),
        )
        await db.commit()


async def delete_user(uid: int) -> None:
    async with _open_db() as db:
        await db.execute("DELETE FROM users WHERE id = ?", (uid,))
        await db.commit()


async def next_user_id() -> int:
    return await _next_id("users")


# --- Submissions ---


async def get_submissions(user_id: int | None = None) -> list[dict]:
    async with _open_db() as db:
        if user_id is not None:
            async with db.execute(
                "SELECT data FROM submissions WHERE json_extract(data, '$.user_id') = ?",
                (user_id,),
            ) as cur:
                return [json.loads(r[0]) for r in await cur.fetchall()]
        async with db.execute("SELECT data FROM submissions") as cur:
            return [json.loads(r[0]) for r in await cur.fetchall()]


async def get_submission_by_id(sid: int) -> dict | None:
    async with _open_db() as db:
        async with db.execute(
            "SELECT data FROM submissions WHERE id = ?", (sid,)
        ) as cur:
            row = await cur.fetchone()
            return json.loads(row[0]) if row else None


async def save_submission(submission: dict) -> None:
    async with _open_db() as db:
        await db.execute(
            "INSERT OR REPLACE INTO submissions (id, data) VALUES (?, ?)",
            (submission["id"], json.dumps(submission)),
        )
        await db.commit()


async def next_submission_id() -> int:
    return await _next_id("submissions")


# --- Init ---


async def init_db() -> None:
    async with _open_db() as db:
        await db.execute(
            "CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, data TEXT NOT NULL)"
        )
        await db.execute(
            "CREATE TABLE IF NOT EXISTS submissions (id INTEGER PRIMARY KEY, data TEXT NOT NULL)"
        )
        await db.commit()

        async with db.execute("SELECT COUNT(*) FROM users") as cur:
            count = (await cur.fetchone())[0]

        if count == 0:
            default_users = [
                ("admin", ["admin", "reviewer"]),
                ("r1", ["reviewer"]),
                ("c1", ["contributor"]),
                ("c2", ["contributor"]),
            ]
            for uid, (username, roles) in enumerate(default_users, start=1):
                user = {
                    "id": uid,
                    "username": username,
                    "magic_token": secrets.token_urlsafe(24),
                    "roles": roles,
                    "quota": CONTRIBUTOR_QUOTA_DEFAULT,
                    "quota_used": 0,
                }
                await db.execute(
                    "INSERT INTO users (id, data) VALUES (?, ?)",
                    (uid, json.dumps(user)),
                )
            await db.commit()

        async with db.execute("SELECT data FROM users") as cur:
            users = [json.loads(r[0]) for r in await cur.fetchall()]

        if not any("admin" in u.get("roles", []) for u in users):
            uid = max((u["id"] for u in users), default=0) + 1
            user = {
                "id": uid,
                "username": "admin",
                "magic_token": secrets.token_urlsafe(24),
                "roles": ["admin", "reviewer"],
                "quota": CONTRIBUTOR_QUOTA_DEFAULT,
                "quota_used": 0,
            }
            await db.execute(
                "INSERT INTO users (id, data) VALUES (?, ?)",
                (uid, json.dumps(user)),
            )
            await db.commit()

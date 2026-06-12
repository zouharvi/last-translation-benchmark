import hashlib
import json
import os
import secrets
from functools import wraps

import aiosqlite

from .utils import CONTRIBUTOR_QUOTA_DEFAULT, DB_CACHE_PATH, DB_PATH


def _open_db():
    db_dir = os.path.dirname(DB_PATH)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)
    return aiosqlite.connect(DB_PATH)


def _open_cache_db():
    db_dir = os.path.dirname(DB_CACHE_PATH)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)
    return aiosqlite.connect(DB_CACHE_PATH)


_TABLES = {"users", "submissions"}







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


async def create_user(user: dict) -> int:
    async with _open_db() as db:
        await db.execute("BEGIN EXCLUSIVE")
        async with db.execute("SELECT MAX(id) FROM users") as cur:
            row = await cur.fetchone()
            if row is None:
                raise RuntimeError("Failed to fetch max user ID.")
            new_id = (row[0] or 0) + 1
            
        user["id"] = new_id
        await db.execute(
            "INSERT INTO users (id, data) VALUES (?, ?)",
            (new_id, json.dumps(user)),
        )
        await db.commit()
        return new_id


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


async def delete_submission(sid: int) -> None:
    async with _open_db() as db:
        await db.execute("DELETE FROM submissions WHERE id = ?", (sid,))
        await db.commit()



async def create_submission(submission: dict) -> int:
    async with _open_db() as db:
        await db.execute("BEGIN EXCLUSIVE")
        async with db.execute("SELECT MAX(id) FROM submissions") as cur:
            row = await cur.fetchone()
            if row is None:
                raise RuntimeError("Failed to fetch max submission ID.")
            new_id = (row[0] or 0) + 1
            
        submission["id"] = new_id
        await db.execute(
            "INSERT INTO submissions (id, data) VALUES (?, ?)",
            (new_id, json.dumps(submission)),
        )
        await db.commit()
        return new_id


# --- Init ---


async def init_db() -> None:
    async with _open_cache_db() as cache_db:
        await cache_db.execute(
            "CREATE TABLE IF NOT EXISTS api_cache (query_hash TEXT PRIMARY KEY, response_text TEXT NOT NULL)"
        )
        await cache_db.commit()

    async with _open_db() as db:
        await db.execute(
            "CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, data TEXT NOT NULL)"
        )
        await db.execute(
            "CREATE TABLE IF NOT EXISTS submissions (id INTEGER PRIMARY KEY, data TEXT NOT NULL)"
        )
        await db.commit()

        async with db.execute("SELECT COUNT(*) FROM users") as cur:
            row = await cur.fetchone()
            if row is None:
                raise RuntimeError("Failed to fetch user count.")
            count = row[0]

        if count == 0:
            default_users = [
                ("admin", ["admin", "reviewer", "contributor"]),
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
                    "name": username.capitalize(),
                    "affiliation": "",
                    "email": "",
                    "review_langs": [],
                    "credit_consent": True,
                    "notification_consent": True,
                    "notifications": [],
                    "last_active": "",
                }
                await db.execute(
                    "INSERT INTO users (id, data) VALUES (?, ?)",
                    (uid, json.dumps(user)),
                )
            await db.commit()


def sqlite_cache(discard_none: bool = False):
    """
    A decorator that caches the output of an async function in the SQLite database.
    It expects the function to be async.
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Include function name in the payload
            payload_dict = {
                "func": func.__name__,
                "args": args,
                "kwargs": kwargs
            }
            # json.dumps with sort_keys=True ensures deterministic hashing
            payload_str = json.dumps(payload_dict, sort_keys=True)
            query_hash = hashlib.sha256(payload_str.encode('utf-8')).hexdigest()
            
            async with _open_cache_db() as db:
                async with db.execute(
                    "SELECT response_text FROM api_cache WHERE query_hash = ?", 
                    (query_hash,)
                ) as cur:
                    cached_result = await cur.fetchone()
                
                if cached_result:
                    # Cache hit
                    return json.loads(cached_result[0])
            
            # Cache miss: call the actual async function
            actual_response = await func(*args, **kwargs)
            
            if discard_none and actual_response is None:
                return actual_response

            async with _open_cache_db() as db:
                # Use INSERT OR REPLACE in case multiple identical queries run concurrently
                await db.execute(
                    "INSERT OR REPLACE INTO api_cache (query_hash, response_text) VALUES (?, ?)", 
                    (query_hash, json.dumps(actual_response))
                )
                await db.commit()
                
            return actual_response
            
        return wrapper
    return decorator
import asyncio
import hashlib
import json
import os
import secrets
import time
from functools import wraps

import aiosqlite

from .utils import CONTRIBUTOR_QUOTA_DEFAULT, DB_CACHE_PATH, DB_PATH


def _open_db():
    db_dir = os.path.dirname(DB_PATH)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)
    return aiosqlite.connect(DB_PATH, timeout=15.0)


def _open_cache_db():
    db_dir = os.path.dirname(DB_CACHE_PATH)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)
    return aiosqlite.connect(DB_CACHE_PATH, timeout=15.0)


_TABLES = {"users", "submissions", "leaderboard"}
PUBLIC_CACHE_TTL_SECONDS = 10 * 60
CACHE_EVICTION_INTERVAL_SECONDS = 60
PUBLIC_CONTRIBUTORS_CACHE = "public_contributors"
PUBLIC_LEADERBOARD_CACHE = "public_leaderboard_results_v2"







# --- Users ---


async def get_users() -> list[dict]:
    async with _open_db() as db, db.execute("SELECT data FROM users") as cur:
        return [json.loads(r[0]) for r in await cur.fetchall()]


async def get_user_by_username(username: str) -> dict | None:
    users = await get_users()
    return next((u for u in users if u["username"] == username), None)


async def get_user_by_id(uid: int) -> dict | None:
    async with _open_db() as db, db.execute("SELECT data FROM users WHERE id = ?", (uid,)) as cur:
        row = await cur.fetchone()
        return json.loads(row[0]) if row else None


async def save_user(user: dict) -> None:
    async with _open_db() as db:
        await db.execute(
            "INSERT OR REPLACE INTO users (id, data) VALUES (?, ?)",
            (user["id"], json.dumps(user)),
        )
        await db.commit()
    await invalidate_cache(PUBLIC_CONTRIBUTORS_CACHE)


async def delete_user(uid: int) -> None:
    async with _open_db() as db:
        await db.execute("DELETE FROM users WHERE id = ?", (uid,))
        await db.commit()
    await invalidate_cache(PUBLIC_CONTRIBUTORS_CACHE)


async def create_user(user: dict) -> int:
    async with _open_db() as db:
        await db.execute("BEGIN EXCLUSIVE")
        async with db.execute(
            "INSERT INTO users (data) VALUES ('{}')"
        ) as cur:
            new_id = cur.lastrowid
        if new_id is None:
            raise RuntimeError("Failed to create user.")

        user["id"] = new_id
        await db.execute(
            "UPDATE users SET data = ? WHERE id = ?",
            (json.dumps(user), new_id),
        )
        await db.commit()
        await invalidate_cache(PUBLIC_CONTRIBUTORS_CACHE)
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
    async with _open_db() as db, db.execute(
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
    await invalidate_cache(PUBLIC_CONTRIBUTORS_CACHE)


async def delete_submission(sid: int) -> None:
    async with _open_db() as db:
        await db.execute("DELETE FROM submissions WHERE id = ?", (sid,))
        await db.commit()
    await invalidate_cache(PUBLIC_CONTRIBUTORS_CACHE)



async def create_submission(submission: dict) -> int:
    async with _open_db() as db:
        await db.execute("BEGIN EXCLUSIVE")
        async with db.execute(
            "INSERT INTO submissions (data) VALUES ('{}')"
        ) as cur:
            new_id = cur.lastrowid
        if new_id is None:
            raise RuntimeError("Failed to create submission.")

        submission["id"] = new_id
        await db.execute(
            "UPDATE submissions SET data = ? WHERE id = ?",
            (json.dumps(submission), new_id),
        )
        await db.commit()
        await invalidate_cache(PUBLIC_CONTRIBUTORS_CACHE)
        return new_id


async def save_sent_email(to_email: str, subject: str, body: str, date: str) -> None:
    async with _open_db() as db:
        await db.execute(
            "INSERT INTO sent_emails (to_email, subject, body, date) VALUES (?, ?, ?, ?)",
            (to_email, subject, body, date)
        )
        await db.commit()


async def get_latest_sent_email_date(to_email: str, subject: str) -> str | None:
    async with _open_db() as db, db.execute(
        "SELECT MAX(date) FROM sent_emails WHERE to_email = ? AND subject = ?",
        (to_email, subject),
    ) as cursor:
        row = await cursor.fetchone()
        return row[0] if row and row[0] else None


# --- Leaderboard ---

async def create_leaderboard_entry(submissions: list, info: dict) -> int:
    async with _open_db() as db:
        await db.execute("BEGIN EXCLUSIVE")
        cur = await db.execute(
            "INSERT INTO leaderboard (submissions, info) VALUES (?, ?)",
            (json.dumps(submissions), json.dumps(info))
        )
        new_id = cur.lastrowid
        await db.commit()
        assert new_id is not None, "Failed to save the leaderboard entry."
        await invalidate_cache(PUBLIC_LEADERBOARD_CACHE)
        return new_id


async def get_leaderboard_entry(uid: int) -> dict | None:
    async with _open_db() as db, db.execute("SELECT id, submissions, info, status, visibility FROM leaderboard WHERE id = ?", (uid,)) as cur:
        r = await cur.fetchone()
        if not r:
            return None
        return {
            "id": r[0],
            "submissions": json.loads(r[1]),
            "info": json.loads(r[2]),
            "status": r[3],
            "visibility": r[4],
        }

async def get_leaderboard_entries(status: str | None = None, visibility: str | None = None) -> list[dict]:
    query = "SELECT id, submissions, info, status, visibility FROM leaderboard WHERE 1=1"
    params = []
    if status is not None:
        query += " AND status = ?"
        params.append(status)
    if visibility is not None:
        query += " AND visibility = ?"
        params.append(visibility)
        
    async with _open_db() as db, db.execute(query, params) as cur:
        rows = []
        for r in await cur.fetchall():
            rows.append({
                "id": r[0],
                "submissions": json.loads(r[1]),
                "info": json.loads(r[2]),
                "status": r[3],
                "visibility": r[4],
            })
        return rows


async def update_leaderboard_entry(uid: int, status: str, visibility: str) -> None:
    async with _open_db() as db:
        await db.execute(
            "UPDATE leaderboard SET status = ?, visibility = ? WHERE id = ?",
            (status, visibility, uid)
        )
        await db.commit()
    await invalidate_cache(PUBLIC_LEADERBOARD_CACHE)

async def delete_leaderboard_entry(uid: int) -> None:
    async with _open_db() as db:
        await db.execute("DELETE FROM leaderboard WHERE id = ?", (uid,))
        await db.commit()
    await invalidate_cache(PUBLIC_LEADERBOARD_CACHE)

async def update_leaderboard_info(uid: int, info: dict) -> None:
    async with _open_db() as db:
        await db.execute(
            "UPDATE leaderboard SET info = ? WHERE id = ?",
            (json.dumps(info), uid)
        )
        await db.commit()
    await invalidate_cache(PUBLIC_LEADERBOARD_CACHE)


# --- Init ---

async def init_db() -> None:
    async with _open_cache_db() as cache_db:
        await cache_db.execute("PRAGMA journal_mode=WAL;")
        await cache_db.execute("PRAGMA busy_timeout=15000;")
        await _ensure_cache_schema(cache_db)
        await cache_db.commit()

    async with _open_db() as db:
        await db.execute("PRAGMA journal_mode=WAL;")
        await db.execute("PRAGMA busy_timeout=15000;")
        await db.execute(
            "CREATE TABLE IF NOT EXISTS users "
            "(id INTEGER PRIMARY KEY AUTOINCREMENT, data TEXT NOT NULL)"
        )
        await db.execute(
            "CREATE TABLE IF NOT EXISTS submissions "
            "(id INTEGER PRIMARY KEY AUTOINCREMENT, data TEXT NOT NULL)"
        )
        await db.execute(
            "CREATE TABLE IF NOT EXISTS sent_emails (to_email TEXT NOT NULL, subject TEXT NOT NULL, body TEXT NOT NULL, date TEXT NOT NULL)"
        )
        await db.execute(
            "CREATE TABLE IF NOT EXISTS leaderboard (id INTEGER PRIMARY KEY AUTOINCREMENT, submissions TEXT NOT NULL, info TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pending', visibility TEXT NOT NULL DEFAULT 'hidden')"
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


async def _ensure_cache_schema(cache_db) -> None:
    await cache_db.execute(
        "CREATE TABLE IF NOT EXISTS api_cache ("
        "query_hash TEXT PRIMARY KEY, response_text TEXT NOT NULL, "
        "expires_at REAL NOT NULL DEFAULT 0, namespace TEXT NOT NULL DEFAULT ''"
        ")"
    )
    async with cache_db.execute("PRAGMA table_info(api_cache)") as cur:
        columns = {row[1] for row in await cur.fetchall()}
    if "expires_at" not in columns:
        await cache_db.execute(
            "ALTER TABLE api_cache ADD COLUMN expires_at REAL NOT NULL DEFAULT 0"
        )
    if "namespace" not in columns:
        await cache_db.execute(
            "ALTER TABLE api_cache ADD COLUMN namespace TEXT NOT NULL DEFAULT ''"
        )


async def evict_expired_cache() -> int:
    async with _open_cache_db() as db:
        await _ensure_cache_schema(db)
        cursor = await db.execute(
            "DELETE FROM api_cache WHERE expires_at > 0 AND expires_at <= ?",
            (time.time(),),
        )
        await db.commit()
        return cursor.rowcount


async def invalidate_cache(*namespaces: str) -> None:
    if not namespaces:
        return
    placeholders = ", ".join("?" for _ in namespaces)
    try:
        async with _open_cache_db() as db:
            await _ensure_cache_schema(db)
            await db.execute(
                f"DELETE FROM api_cache WHERE namespace IN ({placeholders})",
                namespaces,
            )
            await db.commit()
    except (OSError, aiosqlite.Error):
        pass


async def schedule_cache_eviction() -> None:
    while True:
        try:
            await evict_expired_cache()
            await asyncio.sleep(CACHE_EVICTION_INTERVAL_SECONDS)
        except asyncio.CancelledError:
            raise
        except (OSError, RuntimeError, aiosqlite.Error):
            await asyncio.sleep(CACHE_EVICTION_INTERVAL_SECONDS)


def sqlite_cache(discard_none: bool = False, ttl_seconds: float | None = None, namespace: str | None = None):
    """
    A decorator that caches the output of an async function in the SQLite database.
    It expects the function to be async.
    """
    def decorator(func):
        cache_namespace = namespace or func.__name__

        @wraps(func)
        async def wrapper(*args, **kwargs):
            cache = kwargs.get('cache', True)
            # Exclude cache from hash calculation
            hash_kwargs = {k: v for k, v in kwargs.items() if k != 'cache'}
            # Include function name in the payload
            payload_dict = {
                "func": func.__name__,
                "args": args,
                "kwargs": hash_kwargs
            }
            # json.dumps with sort_keys=True ensures deterministic hashing
            payload_str = json.dumps(payload_dict, sort_keys=True)
            query_hash = hashlib.sha256(payload_str.encode('utf-8')).hexdigest()
            
            if cache:
                try:
                    async with _open_cache_db() as db:
                        await _ensure_cache_schema(db)
                        async with db.execute(
                            "SELECT response_text, expires_at FROM api_cache WHERE query_hash = ?",
                            (query_hash,)
                        ) as cur:
                            cached_result = await cur.fetchone()

                        is_fresh = cached_result and (
                            ttl_seconds is None or cached_result[1] > time.time()
                        )
                        if is_fresh:
                            # Cache hit
                            return json.loads(cached_result[0])
                        if cached_result:
                            await db.execute(
                                "DELETE FROM api_cache WHERE query_hash = ?", (query_hash,)
                            )
                            await db.commit()
                except (OSError, aiosqlite.Error, json.JSONDecodeError):
                    pass
            
            # Cache miss or cache override: call the actual async function
            actual_response = await func(*args, **kwargs)
            
            if discard_none and actual_response is None:
                return actual_response

            try:
                async with _open_cache_db() as db:
                    await _ensure_cache_schema(db)
                    # Use INSERT OR REPLACE in case multiple identical queries run concurrently
                    await db.execute(
                        "INSERT OR REPLACE INTO api_cache "
                        "(query_hash, response_text, expires_at, namespace) VALUES (?, ?, ?, ?)",
                        (
                            query_hash,
                            json.dumps(actual_response),
                            time.time() + ttl_seconds if ttl_seconds is not None else 0,
                            cache_namespace,
                        )
                    )
                    await db.commit()
            except (OSError, aiosqlite.Error):
                pass
                
            return actual_response
            
        return wrapper
    return decorator

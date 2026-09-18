import asyncio

from last_translation_benchmark import db


def test_sqlite_cache_expires_and_can_be_invalidated(tmp_path, monkeypatch):
    cache_path = tmp_path / "cache.sqlite"
    monkeypatch.setattr(db, "DB_CACHE_PATH", str(cache_path))
    clock = [1000.0]
    monkeypatch.setattr(db.time, "time", lambda: clock[0])
    calls = 0

    @db.sqlite_cache(ttl_seconds=10, namespace="test_public")
    async def calculate(value: str) -> dict:
        nonlocal calls
        calls += 1
        return {"value": value, "calls": calls}

    async def scenario() -> None:
        assert await calculate("same") == {"value": "same", "calls": 1}
        assert await calculate("same") == {"value": "same", "calls": 1}

        clock[0] = 1011.0
        assert await calculate("same") == {"value": "same", "calls": 2}

        await db.invalidate_cache("test_public")
        assert await calculate("same") == {"value": "same", "calls": 3}

        clock[0] = 1022.0
        assert await db.evict_expired_cache() == 1
        assert await calculate("same") == {"value": "same", "calls": 4}

    asyncio.run(scenario())


def test_init_db_migrates_existing_cache_table(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "database.sqlite"))
    monkeypatch.setattr(db, "DB_CACHE_PATH", str(tmp_path / "cache.sqlite"))

    async def scenario() -> None:
        async with db._open_cache_db() as cache_db:
            await cache_db.execute(
                "CREATE TABLE api_cache (query_hash TEXT PRIMARY KEY, response_text TEXT NOT NULL)"
            )
            await cache_db.commit()

        await db.init_db()

        async with db._open_cache_db() as cache_db, cache_db.execute(
            "PRAGMA table_info(api_cache)"
        ) as cur:
            columns = {row[1] for row in await cur.fetchall()}
        assert {"expires_at", "namespace"}.issubset(columns)

    asyncio.run(scenario())


def test_ttl_cache_does_not_reuse_legacy_entry(tmp_path, monkeypatch):
    cache_path = tmp_path / "cache.sqlite"
    monkeypatch.setattr(db, "DB_CACHE_PATH", str(cache_path))
    calls = 0

    async def scenario() -> None:
        @db.sqlite_cache(ttl_seconds=10, namespace="test_public")
        async def calculate(value: str) -> dict:
            nonlocal calls
            calls += 1
            return {"value": value, "calls": calls}

        async with db._open_cache_db() as cache_db:
            await cache_db.execute(
                "CREATE TABLE api_cache (query_hash TEXT PRIMARY KEY, response_text TEXT NOT NULL)"
            )
            await cache_db.commit()

        payload = {"func": "calculate", "args": ["same"], "kwargs": {}}
        query_hash = db.hashlib.sha256(
            db.json.dumps(payload, sort_keys=True).encode("utf-8")
        ).hexdigest()
        async with db._open_cache_db() as cache_db:
            await cache_db.execute(
                "INSERT INTO api_cache (query_hash, response_text) VALUES (?, ?)",
                (query_hash, '{"value":"legacy","calls":0}'),
            )
            await cache_db.commit()

        assert await calculate("same") == {"value": "same", "calls": 1}

    asyncio.run(scenario())


def test_cache_storage_failure_falls_back_to_computation(monkeypatch):
    monkeypatch.setattr(
        db, "_open_cache_db", lambda: (_ for _ in ()).throw(OSError("cache unavailable"))
    )
    calls = 0

    @db.sqlite_cache(ttl_seconds=10, namespace="test_public")
    async def calculate() -> str:
        nonlocal calls
        calls += 1
        return "fresh"

    async def scenario() -> None:
        assert await calculate() == "fresh"
        assert calls == 1

    asyncio.run(scenario())


def test_cache_without_ttl_remains_persistent(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_CACHE_PATH", str(tmp_path / "cache.sqlite"))
    clock = [1000.0]
    monkeypatch.setattr(db.time, "time", lambda: clock[0])
    calls = 0

    @db.sqlite_cache(namespace="test_legacy")
    async def calculate() -> int:
        nonlocal calls
        calls += 1
        return calls

    async def scenario() -> None:
        assert await calculate() == 1
        clock[0] = 100000.0
        assert await calculate() == 1
        assert calls == 1

    asyncio.run(scenario())

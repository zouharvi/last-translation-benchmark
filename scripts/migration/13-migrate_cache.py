import os
import asyncio
import aiosqlite

from last_translation_benchmark.utils import DB_PATH, DB_CACHE_PATH

async def migrate():
    print(f"Migrating from DB_PATH: {DB_PATH} to DB_CACHE_PATH: {DB_CACHE_PATH}")
    
    if not os.path.exists(DB_PATH):
        print(f"Original database does not exist at {DB_PATH}. Exiting.")
        return

    # Ensure DB_CACHE_PATH directory exists
    cache_db_dir = os.path.dirname(DB_CACHE_PATH)
    if cache_db_dir:
        os.makedirs(cache_db_dir, exist_ok=True)

    async with aiosqlite.connect(DB_PATH) as db:
        # Check if api_cache table exists in the main DB
        async with db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='api_cache'") as cur:
            if not await cur.fetchone():
                print("Table 'api_cache' does not exist in the original database. Migration might have already been run.")
                return
        
        print("Extracting cache data...")
        async with db.execute("SELECT query_hash, response_text FROM api_cache") as cur:
            rows = await cur.fetchall()

        print(f"Found {len(rows)} cached entries.") # type: ignore
        
        async with aiosqlite.connect(DB_CACHE_PATH) as cache_db:
            print("Creating api_cache table in the new database...")
            await cache_db.execute(
                "CREATE TABLE IF NOT EXISTS api_cache (query_hash TEXT PRIMARY KEY, response_text TEXT NOT NULL)"
            )
            
            print("Inserting data into the new database...")
            # Use executemany for faster inserts
            await cache_db.executemany(
                "INSERT OR IGNORE INTO api_cache (query_hash, response_text) VALUES (?, ?)",
                rows
            )
            await cache_db.commit()

        print("Deleting api_cache table from the original database...")
        await db.execute("DROP TABLE api_cache")
        await db.commit()
        
        print("Vacuuming the original database to free up space...")
        await db.execute("VACUUM")
        
    print("Migration complete!")

if __name__ == "__main__":
    asyncio.run(migrate())

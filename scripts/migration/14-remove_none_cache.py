import asyncio

from last_translation_benchmark.db import _open_cache_db

async def main():
    print("Connecting to the cache database...")
    async with _open_cache_db() as db:
        # Check how many 'None' (stored as 'null' in JSON) responses there are
        async with db.execute("SELECT COUNT(*) FROM api_cache WHERE response_text = 'null'") as cur:
            row = await cur.fetchone()
            count = row[0] if row else 0
            print(f"Found {count} cached entries with 'None'/'null' response.")
        
        if count > 0:
            # Delete the null responses
            await db.execute("DELETE FROM api_cache WHERE response_text = 'null'")
            await db.commit()
            print(f"Successfully deleted {count} entries from the cache.")
        else:
            print("No action needed. No null entries found.")

if __name__ == "__main__":
    asyncio.run(main())

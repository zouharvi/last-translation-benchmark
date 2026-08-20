import asyncio

from last_translation_benchmark.db import _open_cache_db


async def check_cache():
    async with _open_cache_db() as db:
        try:
            async with db.execute("SELECT query_hash, response_text FROM api_cache") as cursor:
                rows = await cursor.fetchall()
                
            count = 0
            for row in rows:
                query_hash, response_text = row
                if response_text and response_text.count("our ") > 1_000:
                    await db.execute(
                        "UPDATE api_cache SET response_text = ? WHERE query_hash = ?",
                        ('"teapot"', query_hash)
                    )
                    count += 1
                    
            if count > 0:
                await db.commit()
                
            print(f"Replaced {count} entries with 'our ' repeated more than 1_000 times with '\"teapot\"'.")
        except Exception as e:
            print(f"Error accessing api_cache: {e}")

if __name__ == "__main__":
    asyncio.run(check_cache())

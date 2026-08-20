import asyncio
import json

from last_translation_benchmark.db import _open_db


async def migrate():
    async with _open_db() as db:
        await db.execute("BEGIN EXCLUSIVE")
        try:
            async with db.execute("SELECT id, data FROM submissions") as cur:
                rows = await cur.fetchall()

            migrated_count = 0
            for sid, data_str in rows:
                data = json.loads(data_str)
                updated = False
                
                if "translations" in data:
                    for t in data["translations"]:
                        if t.get("model") == "Google":
                            t["model"] = "Google Translate"
                            updated = True
                
                if updated:
                    await db.execute(
                        "UPDATE submissions SET data = ? WHERE id = ?",
                        (json.dumps(data), sid)
                    )
                    migrated_count += 1
            
            await db.commit()
            print(f"Successfully migrated {migrated_count} submissions.")
        except Exception as e:
            await db.rollback()
            print(f"Error migrating: {e}")

if __name__ == "__main__":
    asyncio.run(migrate())

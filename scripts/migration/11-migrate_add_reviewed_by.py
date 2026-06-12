import asyncio

from last_translation_benchmark.db import get_submissions, save_submission

async def migrate():
    submissions = await get_submissions()
    print(f"Migrating {len(submissions)} submissions...")
    
    for s in submissions:
        if "reviewed_by" not in s:
            s["reviewed_by"] = None
            await save_submission(s)
            
    print("Migration complete.")

if __name__ == "__main__":
    asyncio.run(migrate())

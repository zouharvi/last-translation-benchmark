import asyncio

from last_translation_benchmark.db import get_submissions, save_submission, init_db

async def migrate():
    await init_db()
    submissions = await get_submissions()
    
    migrated_count = 0
    for sub in submissions:
        changed = False
        if "comments" in sub:
            for comment in sub["comments"]:
                if "timestamp" in comment:
                    comment["created_at"] = comment.pop("timestamp")
                    changed = True
        
        if changed:
            await save_submission(sub)
            migrated_count += 1
            
    print(f"Migrated timestamps for {migrated_count} submissions.")

if __name__ == "__main__":
    asyncio.run(migrate())

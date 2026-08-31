import asyncio
from datetime import datetime, UTC

from last_translation_benchmark.db import get_submissions, init_db, save_submission


async def migrate():
    await init_db()
    submissions = await get_submissions()
    
    now_str = datetime.now(UTC).astimezone().strftime("%Y-%m-%d %H:%M")
    
    count = 0
    for sub in submissions:
        if sub.get("status") == "accept":
            comments = sub.setdefault("comments", [])
            
            has_accept = any("ACCEPT" == c.get("text", "").strip() for c in comments)
            
            if not has_accept:
                comments.append({
                    "author": sub.get("reviewed_by") or "System",
                    "text": "ACCEPT",
                    "created_at": now_str
                })
                await save_submission(sub)
                count += 1
                
    print(f"Added ACCEPT comment to {count} submissions.")


if __name__ == "__main__":
    asyncio.run(migrate())

import asyncio
import sys
import os

# Add parent directory to path to import server.db
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from server.db import get_submissions, save_submission

async def migrate_comments():
    print("Fetching submissions...")
    submissions = await get_submissions()
    
    updated_count = 0
    for sub in submissions:
        updated = False
        
        if "comments" not in sub:
            sub["comments"] = []
            
        # Move reviewer_comment to comments
        rev_comment = sub.pop("reviewer_comment", None)
        if rev_comment:
            updated = True
            # Check if this comment is already in the list
            already_exists = any(c.get("text") == rev_comment and c.get("author") in ("Reviewer", "You") for c in sub["comments"])
            if not already_exists:
                sub["comments"].append({
                    "author": "Reviewer",
                    "text": rev_comment,
                    "timestamp": sub.get("created_at", "")
                })
        
        # Remove role from comments
        for c in sub["comments"]:
            if "role" in c:
                del c["role"]
                updated = True
                
        if updated:
            await save_submission(sub)
            updated_count += 1
            
    print(f"Migration completed. Updated {updated_count} submissions.")

if __name__ == "__main__":
    asyncio.run(migrate_comments())

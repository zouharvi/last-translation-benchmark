import asyncio
import sys
import os

# Add parent directory to path to import server.db
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from server.db import get_submissions, save_submission

async def migrate_point_model():
    print("Fetching submissions...")
    submissions = await get_submissions()
    
    updated_count = 0
    for sub in submissions:
        updated = False
        
        # 1. Migrate "points" to "status"
        if "points" in sub:
            points = sub.pop("points")
            if points == 1:
                sub["status"] = "accept"
            elif points == 0:
                sub["status"] = "reject"
            else:
                sub["status"] = "pending"
            updated = True
        elif "status" not in sub:
            sub["status"] = "pending"
            updated = True
            
        # 2. Rename "api" to "model" in translations
        if "translations" in sub and isinstance(sub["translations"], list):
            for t in sub["translations"]:
                if "api" in t:
                    t["model"] = t.pop("api")
                    updated = True
                    
        if updated:
            await save_submission(sub)
            updated_count += 1
            
    print(f"Migration completed. Updated {updated_count} submissions.")

if __name__ == "__main__":
    asyncio.run(migrate_point_model())

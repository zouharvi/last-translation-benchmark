import argparse
import asyncio

from last_translation_benchmark.db import get_users, get_submissions, save_user, save_submission, init_db

async def migrate(old_username: str, new_username: str):
    await init_db()
    users = await get_users()
    submissions = await get_submissions()
    
    # Update users
    users_updated = 0
    for u in users:
        if u.get("username") == old_username:
            u["username"] = new_username
            await save_user(u)
            users_updated += 1
            
    print(f"Updated {users_updated} user(s).")
    
    # Update submissions
    subs_updated = 0
    for sub in submissions:
        changed = False
        if sub.get("username") == old_username:
            sub["username"] = new_username
            changed = True
        
        if sub.get("reviewed_by") == old_username:
            sub["reviewed_by"] = new_username
            changed = True
            
        if "comments" in sub:
            for comment in sub["comments"]:
                if comment.get("author") == old_username:
                    comment["author"] = new_username
                    changed = True
                    
        if changed:
            await save_submission(sub)
            subs_updated += 1
            
    print(f"Updated {subs_updated} submission(s).")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Migrate username in all db entries")
    parser.add_argument("old_username", help="The old username to replace")
    parser.add_argument("new_username", help="The new username")
    args = parser.parse_args()
    
    asyncio.run(migrate(args.old_username, args.new_username))

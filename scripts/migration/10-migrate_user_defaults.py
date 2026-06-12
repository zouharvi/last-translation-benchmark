import asyncio

from last_translation_benchmark.db import get_users, save_user

async def migrate():
    users = await get_users()
    print(f"Migrating {len(users)} users...")
    
    for u in users:
        modified = False
        
        # Rename notification-consent if exists
        if "notification-consent" in u:
            u["notification_consent"] = u.pop("notification-consent")
            modified = True
            
        # Ensure all required fields exist
        defaults = {
            "name": u["username"].capitalize() if "username" in u else "",
            "affiliation": "",
            "email": "",
            "credit_consent": True,
            "notification_consent": True,
            "notifications": [],
            "review_langs": [],
            "last_active": ""
        }
        
        for k, v in defaults.items():
            if k not in u:
                u[k] = v
                modified = True
                
        if modified:
            await save_user(u)
            
    print("Migration complete.")

if __name__ == "__main__":
    asyncio.run(migrate())

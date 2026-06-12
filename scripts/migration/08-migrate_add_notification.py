import os
import argparse
import asyncio

from last_translation_benchmark.db import get_users, get_submissions, save_user, init_db
from last_translation_benchmark.utils import send_email

async def migrate():
    await init_db()
    users = await get_users()
    submissions = await get_submissions()
    
    # Create a user lookup map
    users_by_id = {u["id"]: u for u in users}
    
    # 04h logic: Ensure notification fields exist
    fields_updated = 0
    for u in users:
        changed = False
        if "notifications" not in u:
            u["notifications"] = []
            changed = True
        if "notification_consent" not in u:
            u["notification_consent"] = True
            changed = True
        if changed:
            fields_updated += 1
            
    if fields_updated > 0:
        print(f"Added notification fields to {fields_updated} users.")
        
    count = 0
    # add past notifications for accepted/returned submissions
    for sub in submissions:
        status = sub["status"]
        if status in ("accept", "return"):
            user_id = sub["user_id"]
            if user_id not in users_by_id:
                continue
            author = users_by_id[user_id]
            
            prefix = (sub["source_text"] or "")[:70].replace("\n", " ")
            if not prefix and sub["source_media"]:
                prefix = "Media submission"
                
            content = f"#{sub['id']}: {prefix}..." if len(sub["source_text"] or "") > 70 else f"#{sub['id']}: {prefix}"
            
            # Check if this notification already exists
            existing = any(n["content"] == content and n["type"] in ("accepted", "returned") for n in author["notifications"])
            if existing:
                continue
                
            author["notifications"].append({
                "created": sub["created_at"],
                "type": "accepted" if status == "accept" else "returned",
                "status": "unread",
                "content": content
            })
            count += 1
            
    # Save modified users
    for user in users_by_id.values():
        await save_user(user)
        
    print(f"Migrated {count} past notifications for accepted/returned submissions.")
    return users_by_id.values()

async def send_notifications(users, target_users=None):
    # TODO: HOST_PUBLIC is not set in this script
    host_url = (os.getenv("HOST_PUBLIC") or "").rstrip('/')
    
    count = 0

    for u in users:
        # If specific users are requested, skip if this user is not in the list
        if target_users is not None and u["username"] not in target_users:
            continue
            
        if not u["notification_consent"]:
            continue
            
        unread = [n for n in u["notifications"] if n["status"] == "unread"]
        if not unread:
            continue
            
        accepted = [n for n in unread if n["type"] == "accepted"]
        returned = [n for n in unread if n["type"] in ("returned", "commented")]

        email_body = f"Hello {u['name']},\n\nYou have {len(unread)} unread notifications regarding your submissions on the Last Translation Benchmark:\n\n"
        
        if accepted:
            email_body += "Accepted submissions:\n"
            for n in accepted:
                email_body += f"- {n['type']} ({n['created']}) {n['content']}\n"
            email_body += "\n"
            
        if returned:
            email_body += "Returned/commented submissions, please update and resubmit:\n"
            for n in returned:
                email_body += f"- {n['type']} ({n['created']}) {n['content']}\n"
            email_body += "\n"
        
        email_body += f"View them here: {host_url}\n"
        email_body += f"\nBest regards, the LTB Team"
        
        print(f"Sending email to {u.get('email', '')} ({u['username']})...")
        
        if await send_email(
            to_email=u.get("email", ""),
            subject="Last Translation Benchmark - Notifications",
            body=email_body,
            user_obj=u
        ):
            for n in unread:
                n["status"] = "emailed"
            await save_user(u)
            count += 1
        else:
            print(f"Failed to send email to {u.get('email', '')}")
            
    print(f"Sent {count} notification emails.")

async def main():
    parser = argparse.ArgumentParser(description="Add notifications fields, migrate past notifications, and send emails.")
    parser.add_argument("--users", nargs="*", default=None, help="List of usernames to send emails to. If omitted, sends to everyone.")
    args = parser.parse_args()
    
    if args.users:
        print(f"Targeting specific users for emails: {args.users}")
        
    users = await migrate()
    await send_notifications(users, args.users)

if __name__ == "__main__":
    asyncio.run(main())

import asyncio
import os
import urllib.parse

from last_translation_benchmark.db import _open_db, get_submissions, get_users
from last_translation_benchmark.utils import send_email

os.environ["HOST_PUBLIC"] = "https://last-translation-benchmark.vilda.net"

SUBJECT = "Last Translation Benchmark - Contribute"
BODY_TEMPLATE = """Dear {name},

We noticed you have registered for the Last Translation Benchmark project but haven't made any submissions yet. 
So far we have collected 3000+ submissions across many languages. The project will soon be going public, and we would love if you could be on the paper!

You can login and contribute using the following link:

{login_link}

Let us know if you have any questions.
Best, the LTB team
"""



async def has_sent_subject(email: str, subject: str) -> bool:
    async with _open_db() as db, db.execute(
        "SELECT 1 FROM sent_emails WHERE to_email = ? AND subject = ?",
        (email, subject)
    ) as cur:
        return await cur.fetchone() is not None

async def main():
    print("Fetching users and submissions...")
    users = await get_users()
    submissions = await get_submissions()
    
    # Track which users have submissions
    active_user_ids = {sub.get("user_id") for sub in submissions}
    
    for user in users:
        uid = user.get("id")
        email = user.get("email")
        name = user.get("name")
        username = user.get("username")
        login_link =f"https://last-translation-benchmark.vilda.net/?user={urllib.parse.quote(str(username))}&token={user.get('magic_token')}"
        
        # User must have an email
        if not email:
            continue
            
        # Check if user has no submissions
        if uid in active_user_ids:
            continue
            
        # Check notification consent
        if not user["notification_consent"]:
            continue
            
        # Check if email already sent
        already_sent = await has_sent_subject(email, SUBJECT)
        if already_sent:
            continue

        while True:
            ans = input(f"\nSend to {name} <{email}>? (y/n): ").strip().lower()
            if ans in ('y', 'n'):
                break
            
        if ans == 'y':
            body = BODY_TEMPLATE.format(name=name, login_link=login_link)
            # send_email automatically adds to the sent_emails database
            success = await send_email(email, SUBJECT, body, user_obj=user)
            if success:
                print("Email sent successfully.")
            else:
                print("Failed to send email.")
        else:
            print("Skipped.")

if __name__ == "__main__":
    asyncio.run(main())

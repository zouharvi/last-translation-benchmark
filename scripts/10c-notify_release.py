import asyncio
import os
import time

from last_translation_benchmark.db import _open_db, get_users
from last_translation_benchmark.utils import send_email

os.environ["HOST_PUBLIC"] = "https://last-translation-benchmark.vilda.net"

SUBJECT = "Last Translation Benchmark - Paper and Data Release!"
BODY_TEMPLATE = """Dear {name},

We are thrilled to announce that the Last Translation Benchmark (LTB) paper and dataset have now been officially released!
We couldn't have built this benchmark without our amazing contributors. You can read the paper here: {paper_link}

If you did not make it to the author list, don't worry. We'll continue accepting submisions for future re-releases.

Thank you for your support and contributions,
The LTB Team
"""

async def has_sent_subject(email: str, subject: str) -> bool:
    async with _open_db() as db, db.execute(
        "SELECT 1 FROM sent_emails WHERE to_email = ? AND subject = ?",
        (email, subject)
    ) as cur:
        return await cur.fetchone() is not None

async def main():
    print("Fetching users...")
    users = await get_users()
        
    for user in users:
        email = user.get("email")
        name = user.get("name")
                
        # User must have an email
        if not email:
            continue
            
        # Check notification consent
        if not user["notification_consent"]:
            continue
            
        # Check if email already sent
        already_sent = await has_sent_subject(email, SUBJECT)
        if already_sent:
            print(f"Email already sent to {email}. Skipping.")
            continue

        while True:
            ans = input(f"\nSend to {name} <{email}>? (y/n/a for all): ").strip().lower()
            if ans in ('y', 'n', 'a'):
                break
            
        if ans in ('y', 'a'):
            body = BODY_TEMPLATE.format(name=name, paper_link="TODO TODO")
            # send_email automatically adds to the sent_emails database
            success = await send_email(email, SUBJECT, body, user_obj=user)
            if success:
                print(f"Email sent successfully to {email}.")
            else:
                print(f"Failed to send email to {email}.")
        else:
            print("Skipped.")

        # Sleep for 5 seconds between emails to avoid overwhelming the email server
        time.sleep(5)

if __name__ == "__main__":
    asyncio.run(main())

import asyncio
import datetime
import os
import urllib.parse

from last_translation_benchmark.db import _open_db, get_submissions, get_users
from last_translation_benchmark.utils import send_email

os.environ["HOST_PUBLIC"] = "https://last-translation-benchmark.vilda.net"

SUBJECT = "Last Translation Benchmark - Action Required: Returned Submissions"
BODY_TEMPLATE = """Dear {name},

We noticed that you have made submissions to the Last Translation Benchmark project, but currently they have been returned for revisions. 
Please review the feedback left by our reviewers, update your submissions, and submit them again!

You can login and review your returned submissions using the following link:

{login_link}

Let us know if you have any questions.
Best, the LTB team
"""

def _permissive_strptime(date_str: str) -> datetime.datetime:
    for f in ["%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"]:
        try:
            return datetime.datetime.strptime(date_str, f)
        except ValueError:
            continue
    raise ValueError(f"Unable to parse date string: {date_str}")

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
    
    # Group submissions by user_id
    user_submissions = {}
    for sub in submissions:
        uid = sub.get("user_id")
        if uid not in user_submissions:
            user_submissions[uid] = []
        user_submissions[uid].append(sub)
    
    for user in users:
        uid = user.get("id")
        email = user.get("email")
        name = user.get("name")
        username = user.get("username")
        login_link = f"https://last-translation-benchmark.vilda.net/?user={urllib.parse.quote(str(username))}&token={user.get('magic_token')}"
        
        # User must have an email
        if not email:
            continue
            
        subs = user_submissions.get(uid, [])
        # Only consider returned submissions
        subs = [s for s in subs if s.get("status") == "return"]
        # Only consider submissions with last activity being more than 7 days
        subs = [s for s in subs if (datetime.datetime.now() - _permissive_strptime(s.get("created_at"))).days > 7]

        # They must have at least one submission
        if not subs:
            continue
            
        # Check notification consent
        if not user.get("notification_consent", True):
            continue
            
        # Check if email already sent
        already_sent = await has_sent_subject(email, SUBJECT)
        if already_sent:
            continue

        while True:
            ans = input(f"\nSend to {name} <{email}> ({len(subs)} submissions)? (y/n): ").strip().lower()
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

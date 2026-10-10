import asyncio
import datetime
import os
import urllib.parse

from last_translation_benchmark.db import _open_db, get_submissions, get_users
from last_translation_benchmark.utils import permissive_strptime, send_email

os.environ["HOST_PUBLIC"] = "https://last-translation-benchmark.vilda.net"

SUBJECT = "Last Translation Benchmark - Revise Submissions?"
BODY_TEMPLATE = """Dear {name},

We noticed that you have made submissions to the Last Translation Benchmark that have been returned for revisions. 
Please review the feedback left by our reviewers, update your submissions, and {submit_again_text}

{ex_text}

You can login and review your returned submissions using the following link:

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
    
    # Group submissions by user_id
    user_submissions = {}
    for sub in submissions:
        uid = sub["user_id"]
        if uid not in user_submissions:
            user_submissions[uid] = []
        user_submissions[uid].append(sub)
    
    for user in users:
        uid = user["id"]
        email = user["email"]
        name = user["name"]
        username = user["username"]
        login_link = f"https://last-translation-benchmark.vilda.net/?user={urllib.parse.quote(str(username))}&token={user['magic_token']}"
        
        # User must have an email
        if not email:
            continue
            
        all_subs = user_submissions.get(uid, [])
        if not all_subs:
            continue

        returned_subs = [s for s in all_subs if s["status"] == "return"]
        
        if not (len(returned_subs) >= 5 or len(returned_subs) == len(all_subs)):
            continue
            
        # Only consider submissions with last activity being more than 7 days
        subs_to_remind = [s for s in returned_subs if (datetime.datetime.now(tz=datetime.UTC) - permissive_strptime(s["created_at"])).days > 7]

        # They must have at least one submission
        if not subs_to_remind:
            continue
            
        import random
        ex_lines = [
            f"- #{f['id']} {f['source_lang']} -> {f['target_lang']}: {f['source_text'][:50].replace('\n', ' ')}{'...' if len(f['source_text']) > 50 else ''}"
            for f in subs_to_remind
        ]
        ex_lines_i = random.sample(range(len(ex_lines)), min(len(ex_lines), 10))
        ex_lines_i.sort()
        ex_lines = [ex_lines[i] for i in ex_lines_i]
        ex_text = "\n".join(ex_lines)
        if len(subs_to_remind) > 10:
            ex_text += f"\n...and {len(subs_to_remind) - 10} more submissions."
            
        # Check notification consent
        if not user["notification_consent"]:
            continue
            
        # Check if email already sent
        already_sent = await has_sent_subject(email, SUBJECT)
        if already_sent:
            continue

        accepted_subs = [s for s in all_subs if s["status"] == "accept"]
        if len(accepted_subs) < 10:
            submit_again_text = "submit them again (10 accepted submissions are required for contributors)."
        else:
            submit_again_text = "submit them again."

        print(f"Sending to {name} <{email}> ({len(subs_to_remind)} submissions)...")
        body = BODY_TEMPLATE.format(name=name, login_link=login_link, ex_text=ex_text, submit_again_text=submit_again_text)
        # send_email automatically adds to the sent_emails database
        success = await send_email(email, SUBJECT, body, user_obj=user)
        if success:
            print("Email sent successfully.")
        else:
            print("Failed to send email.")
            
        delay = random.uniform(10.0, 15.0)
        await asyncio.sleep(delay)

if __name__ == "__main__":
    asyncio.run(main())

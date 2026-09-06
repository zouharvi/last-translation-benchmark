import asyncio
from datetime import datetime, timedelta
from last_translation_benchmark.db import get_users, get_submissions, get_latest_sent_email_date

REVIEW_REMINDER_SUBJECT = "Last Translation Benchmark - Review Request"

async def main():
    users = await get_users()
    submissions = await get_submissions()

    naive_two_weeks_ago = datetime.now() - timedelta(days=14)

    for user in users:
        if "reviewer" not in user["roles"]:
            continue

        if not user["notification_consent"]:
            continue

        username = user["username"]
        
        accepted_subs = [sub for sub in submissions if sub["user_id"] == user["id"] and sub["status"] == "accept"]
        if len(accepted_subs) < 10:
            continue

        
        latest_email_date_str = await get_latest_sent_email_date(user["email"], REVIEW_REMINDER_SUBJECT)
        if latest_email_date_str:
            latest_email_date = datetime.fromisoformat(latest_email_date_str).replace(tzinfo=None)
            if latest_email_date >= naive_two_weeks_ago:
                continue

        reviewed_subs = [sub for sub in submissions if sub["reviewed_by"] == username]

        if len(reviewed_subs) < 2:
            continue
        
        last_review_date = datetime.min
        for sub in reviewed_subs:
            for comment in sub["comments"]:
                if comment["author"] == username and comment["text"] in ("ACCEPT", "RETURN"):
                    dt = datetime.strptime(comment["created_at"], "%Y-%m-%d %H:%M")
                    if dt > last_review_date:
                        last_review_date = dt

        if last_review_date != datetime.min and last_review_date < naive_two_weeks_ago:
            print(f"{user['name']} ({username})")

if __name__ == "__main__":
    asyncio.run(main())

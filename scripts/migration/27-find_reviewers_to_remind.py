import argparse
import asyncio
from datetime import datetime, timedelta

from last_translation_benchmark.db import (
    get_latest_sent_email_date,
    get_submissions,
    get_users,
)

REVIEW_REMINDER_SUBJECT = "Last Translation Benchmark - Review Request"

async def main(args):
    users = await get_users()
    submissions = await get_submissions()

    reminded_limit = datetime.now() - timedelta(days=args.reminded)

    for user in users:
        if "reviewer" not in user["roles"]:
            continue

        if not user["notification_consent"]:
            continue

        username = user["username"]
        
        accepted_subs = [sub for sub in submissions if sub["user_id"] == user["id"] and sub["status"] == "accept"]
        # FILTER: accepted at least 5 accepted submissions
        if len(accepted_subs) < 5:
            continue

        coverage = [lang.lower() for lang in user["review_langs"]]
            
        potential_subs = 0
        for sub in submissions:
            if sub["status"] == "pending" and sub["user_id"] != user["id"]:
                x = sub["source_lang"].lower()
                y = sub["target_lang"].lower()
                x_match = any(lang in x or x in lang for lang in coverage)
                y_match = any(lang in y or y in lang for lang in coverage)
                if x_match or y_match:
                    potential_subs += 1

        # FILTER: has enough potential submissions to review
        if potential_subs < args.potential:
            continue
        
        latest_email_date_str = await get_latest_sent_email_date(user["email"], REVIEW_REMINDER_SUBJECT)
        if latest_email_date_str:
            latest_email_date = datetime.fromisoformat(latest_email_date_str).replace(tzinfo=None)
            if latest_email_date >= reminded_limit:
                continue

        reviewed_subs = [sub for sub in submissions if sub["reviewed_by"] == username]

        # FILTER: has reviewed in the past
        if len(reviewed_subs) < args.reviewed:
            continue
        
        last_review_date = datetime.min
        for sub in reviewed_subs:
            for comment in sub["comments"]:
                if comment["author"] == username and comment["text"] in ("ACCEPT", "RETURN"):
                    dt = datetime.strptime(comment["created_at"], "%Y-%m-%d %H:%M")
                    last_review_date = max(last_review_date, dt)

        if last_review_date < reminded_limit:
            print(f"{user['name']:<30} | Accepted: {len(accepted_subs):<3} | Reviewed: {len(reviewed_subs):<3} | Potential: {potential_subs:<3}")

if __name__ == "__main__":
    args = argparse.ArgumentParser()
    args.add_argument("--reviewed", type=int, default=1, help="Person reviewed at least this many examples")
    args.add_argument("--reminded", type=int, default=14, help="Person was reminded at least this many days ago")
    args.add_argument("--potential", type=int, default=20, help="At least this many items they could review")
    args = args.parse_args()
    asyncio.run(main(args))

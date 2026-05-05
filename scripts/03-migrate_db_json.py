#!/usr/bin/env python3
import sqlite3
import json
import os
import argparse
import secrets

args = argparse.ArgumentParser(
    description="Migrate old submissions from db.json into sqlite database."
)
args.add_argument("--json", help="Path to the old db.json file", default="data/db.json")
args.add_argument("--db", help="Path to the .sqlite file", default="data/db.sqlite")
args = args.parse_args()

try:
    if not os.path.exists(args.json):
        print(f"File {args.json} not found.")
        exit(1)

    with open(args.json, "r") as f:
        old_db = json.load(f)

    conn = sqlite3.connect(args.db)
    cur = conn.cursor()

    # 1. Create or get user `ghost-from-the-past`
    cur.execute("SELECT data FROM users")
    users = [json.loads(row[0]) for row in cur.fetchall()]

    ghost_user = None
    for u in users:
        if u.get("username") == "ghost-from-the-past":
            ghost_user = u
            break

    if not ghost_user:
        ghost_id = max((u["id"] for u in users), default=0) + 1
        ghost_user = {
            "id": ghost_id,
            "username": "ghost-from-the-past",
            "magic_token": secrets.token_urlsafe(24),
            "roles": ["contributor"],
            "quota": 0,
            "quota_used": 0,
            "name": "Ghost from the Past",
        }
        cur.execute(
            "INSERT INTO users (id, data) VALUES (?, ?)",
            (ghost_id, json.dumps(ghost_user)),
        )
    else:
        ghost_id = ghost_user["id"]

    # 2. Put all submissions from db.json under this new user
    cur.execute("SELECT id FROM submissions")
    existing_sub_ids = [row[0] for row in cur.fetchall()]
    next_sub_id = max(existing_sub_ids, default=0) + 1

    submissions = old_db.get("submissions", [])
    inserted = 0
    for sub in submissions:
        # Assign to ghost user
        sub["user_id"] = ghost_id
        sub["username"] = "ghost-from-the-past"

        # We should give it a new ID to avoid collisions with the current database
        sub["id"] = next_sub_id

        cur.execute(
            "INSERT INTO submissions (id, data) VALUES (?, ?)",
            (next_sub_id, json.dumps(sub)),
        )
        next_sub_id += 1
        inserted += 1

    conn.commit()
    print(
        f"Migrated {inserted} submissions from {args.json} to {args.db} under user 'ghost-from-the-past'."
    )
    conn.close()

except Exception as e:
    print(f"Error: {e}")

#!/usr/bin/env python3
import sqlite3
import json
import os
import argparse

args = argparse.ArgumentParser(description="Extract authors from sqlite database.")
args.add_argument("--db", help="Path to the .sqlite file", default="data/db.sqlite")
args.add_argument(
    "--output", default="scripts/data/authors_dataset.json", help="Output path"
)
args.add_argument(
    "--min-points",
    type=int,
    default=10,
    help="Minimum points for author inclusion (default: 1)",
)
args = args.parse_args()

os.makedirs(os.path.dirname(args.output), exist_ok=True)

try:
    conn = sqlite3.connect(args.db)
    cur = conn.cursor()

    # Get all users
    cur.execute("SELECT data FROM users")
    users = [json.loads(row[0]) for row in cur.fetchall()]

    # Get all confirmed submissions to calculate points
    cur.execute("SELECT data FROM submissions")
    confirmed_submissions = [
        json.loads(row[0])
        for row in cur.fetchall()
        if json.loads(row[0]).get("status") == "accept"
    ]

    user_points = {}
    for s in confirmed_submissions:
        uid = s.get("user_id")
        user_points[uid] = user_points.get(uid, 0) + 1

    # Filter authors who have enough points and gave credit consent
    authors = []
    for u in users:
        pts = user_points.get(u["id"], 0)
        if pts >= args.min_points and u.get("credit_consent"):
            authors.append(
                {
                    "name": u.get("name") or u["username"],
                    "affiliation": u.get("affiliation", ""),
                    "points": pts,
                }
            )

    # Sort authors by points (desc) then name
    authors.sort(key=lambda x: (-x["points"], x["name"].lower()))

    # Clean export format
    authors_export = [
        {"name": a["name"], "affiliation": a["affiliation"]} for a in authors
    ]

    with open(args.output, "w") as f:
        json.dump(authors_export, f, indent=2, ensure_ascii=False)
    print(f"Exported {len(authors_export)} authors to {args.output}")

    conn.close()
except Exception as e:
    print(f"Error: {e}")

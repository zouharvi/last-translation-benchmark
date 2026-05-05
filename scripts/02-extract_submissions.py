#!/usr/bin/env python3
import sqlite3
import json
import os
import argparse


args = argparse.ArgumentParser(
    description="Extract confirmed submissions from sqlite database."
)
args.add_argument("--db", help="Path to the .sqlite file", default="data/db.sqlite")
args.add_argument("--output", default="scripts/data/data.json", help="Output path")
args = args.parse_args()

os.makedirs(os.path.dirname(args.output), exist_ok=True)

conn = sqlite3.connect(args.db)
cur = conn.cursor()

# Get all confirmed submissions (points == 1)
cur.execute("SELECT data FROM submissions")
confirmed_submissions = [
    json.loads(row[0])
    for row in cur.fetchall()
    if json.loads(row[0]).get("points") == 1
]

with open(args.output, "w") as f:
    json.dump(confirmed_submissions, f, indent=2, ensure_ascii=False)
print(f"Exported {len(confirmed_submissions)} confirmed submissions to {args.output}")

conn.close()

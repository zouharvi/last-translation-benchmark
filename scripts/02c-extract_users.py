#!/usr/bin/env python3
import sqlite3
import json
import os
import argparse


args = argparse.ArgumentParser(
    description="Extract all users from sqlite database."
)
args.add_argument("--db", help="Path to the .sqlite file", default="data/db.sqlite")
args.add_argument("--output", default="../users.json", help="Output path")
args = args.parse_args()

os.makedirs(os.path.dirname(args.output), exist_ok=True)

conn = sqlite3.connect(args.db)
cur = conn.cursor()

cur.execute("SELECT data FROM users")
users = [
    json.loads(row[0])
    for row in cur.fetchall()
]

with open(args.output, "w") as f:
    json.dump(users, f, indent=2, ensure_ascii=False)
print(f"Exported {len(users)} users to {args.output}")

conn.close()

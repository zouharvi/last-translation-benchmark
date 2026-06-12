#!/usr/bin/env python3
import sqlite3
import json
import os
import argparse


args = argparse.ArgumentParser(
    description="Extract confirmed submissions from sqlite database."
)
args.add_argument("--db", help="Path to the .sqlite file", default="data/db.sqlite")
args.add_argument("--output", default="../submissions.json", help="Output path")
args = args.parse_args()

os.makedirs(os.path.dirname(args.output), exist_ok=True)

conn = sqlite3.connect(args.db)
cur = conn.cursor()

cur.execute("SELECT data FROM submissions")
submissions = [
    json.loads(row[0])
    for row in cur.fetchall()
]

with open(args.output, "w") as f:
    json.dump(submissions, f, indent=2, ensure_ascii=False)
print(f"Exported {len(submissions)} submissions to {args.output}")

conn.close()

import sqlite3
import json
import os

# Assuming script is in scripts/migration/, DB_PATH is ../../data/db.sqlite
DB_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "data", "db.sqlite")

if not os.path.exists(DB_PATH):
    print("No database found at", DB_PATH)
    exit(0)

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

try:
    cursor.execute("SELECT id, data FROM submissions")
    rows = cursor.fetchall()
except Exception as e:
    print("No submissions table:", e)
    exit(0)

updated_count = 0
for row_id, data_str in rows:
    data = json.loads(data_str)
    changed = False
    
    rule_count = len(data.get("verification_rules", []))
    
    for t in data.get("translations", []):
        # We only update if it is strictly a boolean
        if isinstance(t.get("verified"), bool):
            val = t["verified"]
            t["verified"] = [val] * rule_count
            changed = True
            
    if changed:
        cursor.execute("UPDATE submissions SET data = ? WHERE id = ?", (json.dumps(data), row_id))
        updated_count += 1

conn.commit()
conn.close()

print(f"Successfully updated {updated_count} submissions.")

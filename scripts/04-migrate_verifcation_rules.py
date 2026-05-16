import asyncio
import sys
from pathlib import Path

# Add server to path so we can import db
sys.path.append(str(Path(__file__).parent.parent))

from server.db import get_submissions, save_submission

async def migrate():
    submissions = await get_submissions()
    for sub in submissions:
        rules = sub.get("verification_rules", [])
        changed = False
        new_rules = []
        for r in rules:
            if "type" in r:
                t = r["type"]
                v = r.get("value", "")
                if t == "contains":
                    new_rules.append({"value": f'Translation has to contain exactly "{v}".'})
                elif t == "not_contains":
                    new_rules.append({"value": f'Translation can\'t contain exactly "{v}".'})
                else:
                    new_rules.append({"value": v})
                changed = True
            else:
                new_rules.append(r)
        
        if changed:
            sub["verification_rules"] = new_rules
            await save_submission(sub)
            print(f"Migrated submission {sub['id']}")

if __name__ == "__main__":
    asyncio.run(migrate())

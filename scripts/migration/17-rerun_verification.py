import asyncio
import json

from tqdm import tqdm

from last_translation_benchmark.db import _open_db
from last_translation_benchmark.services import verify_llm


async def get_matching_submissions():
    try:
        async with _open_db() as db:
            async with db.execute("SELECT id, data FROM submissions") as cursor:
                rows = await cursor.fetchall()
    except Exception as e:
        print("No submissions table:", e)
        return []

    # Commit c7ee6b4 "Resolve #131: multiple checkmarks..." introduced storing verification results separatedly.
    COMMIT_TIME = "2026-06-05 11:46:32"
    matching = []

    for row_id, data_str in rows:
        data = json.loads(data_str)
        
        if data["status"] != "accept":
            continue
        
        rules = data["verification_rules"]
        if len(rules) > 1:
            created_at = data["created_at"]
            if created_at < COMMIT_TIME:
                all_uniform = True
                for t in data["translations"]:
                    verified = t["verified"]
                    if not (all(verified) or not any(verified)):
                        all_uniform = False
                        break
                
                if all_uniform:
                    matching.append((row_id, data))

    return matching

VERIFICATION_MODEL = "google/gemini-3.1-pro-preview"

async def process_submissions(submissions):
    total_calls = sum(len(data["translations"]) * len(data["verification_rules"]) for _, data in submissions)
    if total_calls == 0:
        print("No verification calls to make.")
        return

    pbar = tqdm(total=total_calls, desc="Rerunning verification")

    for row_id, data in submissions:
        data["verification_model"] = VERIFICATION_MODEL
        source_text = data["source_text"]
        
        # Going with strict dictionary indexing:
        source_media = data.get("source_media", None)
        # Ensure it's present in the data for future reference
        data["source_media"] = source_media
        
        rules = data["verification_rules"]
        
        for t in data["translations"]:
            translation_text = t["translation"]
            
            new_verified = []
            for rule in rules:
                rule_val = rule["value"]
                try:
                    result = await verify_llm(
                        source_text=source_text,
                        translation=translation_text,
                        rule=rule_val,
                        model=VERIFICATION_MODEL,
                        source_media=source_media
                    )
                except Exception as e:
                    print(f"\nError verifying ID {row_id} with rule '{rule_val}': {e}")
                    # In case of exception, we fall back to False so we don't break the list length
                    result = False
                
                new_verified.append(result)
                pbar.update(1)
            
            t["verified"] = new_verified
        
        # Open a brief connection with a timeout to update this row safely
        # without holding a lock during the LLM calls
        async with _open_db() as db:
            await db.execute("UPDATE submissions SET data = ? WHERE id = ?", (json.dumps(data), row_id))
            await db.commit()

    pbar.close()

async def main():
    subs = await get_matching_submissions()
    print(f"Found {len(subs)} submissions to re-verify.")
    if subs:
        await process_submissions(subs)

if __name__ == "__main__":
    asyncio.run(main())

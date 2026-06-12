import asyncio

from last_translation_benchmark.db import get_submissions, save_submission

async def migrate_add_human():
    print("Fetching submissions...")
    submissions = await get_submissions()
    
    updated_count = 0
    for sub in submissions:
        translations = sub.get("translations", [])
        
        has_human = any(t.get("model") == "human" for t in translations)
        if has_human:
            continue
            
        print(f"\n--- Submission ID: {sub.get('id')} ---")
        print(f"Source text: {sub.get('source_text')}")
        
        passing_translations = [t for t in translations if t.get("verified") is True]
        
        if not passing_translations:
            print("WARNING: No human translation AND no passing machine translations.")
            continue
            
        print("Passing translations:")
        for i, t in enumerate(passing_translations, start=1):
            print(f"[{i}] ({t.get('model')}): {t.get('translation')}")
            
        while True:
            choice = input(f"Choose a translation to use as 'human' (1-{len(passing_translations)}) or 's' to skip: ")
            if choice.lower() == 's':
                print("Skipped.")
                break
                
            try:
                idx = int(choice) - 1
                if 0 <= idx < len(passing_translations):
                    chosen = passing_translations[idx]
                    # Add new translation entry
                    new_human = {
                        "model": "human",
                        "translation": chosen["translation"],
                        "verified": chosen.get("verified")
                    }
                    translations.append(new_human)
                    await save_submission(sub)
                    updated_count += 1
                    print(f"Added human translation!")
                    break
                else:
                    print("Invalid index.")
            except ValueError:
                print("Invalid input.")

    print(f"\nMigration completed. Updated {updated_count} submissions.")

if __name__ == "__main__":
    asyncio.run(migrate_add_human())

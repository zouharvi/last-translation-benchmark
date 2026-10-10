import asyncio
import re

from last_translation_benchmark.db import get_submissions, save_submission

def format_language(lang: str) -> str:
    lang = lang.strip()
    if not lang:
        return lang
    
    # Capitalize first letter
    lang = lang[0].upper() + lang[1:]
    
    # Add space before parentheses
    lang = re.sub(r'([^\s])\(', r'\1 (', lang)
    
    return lang

async def main():
    submissions = await get_submissions()
    
    for sub in submissions:
        src = sub.get("source_lang", "")
        tgt = sub.get("target_lang", "")
        
        new_src = format_language(src)
        new_tgt = format_language(tgt)
        
        if src != new_src or tgt != new_tgt:
            print(f"Submission {sub['id']} ({sub['status']}):")
            if src != new_src:
                print(f"  Source: '{src}' -> '{new_src}'")
            if tgt != new_tgt:
                print(f"  Target: '{tgt}' -> '{new_tgt}'")

            ans = input("Fix this? (y/N): ")
            if ans.lower() == 'y':
                sub["source_lang"] = new_src
                sub["target_lang"] = new_tgt
                
                old_status = sub["status"]
                if old_status == "return":
                    sub["status"] = "pending"
                
                await save_submission(sub)
                print(f"Saved submission {sub['id']} (status: {old_status} -> {sub['status']})")
            print()
    print("Done.")

if __name__ == "__main__":
    asyncio.run(main())

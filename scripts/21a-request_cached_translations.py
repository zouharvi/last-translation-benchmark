# %%

import json
import os

os.chdir(os.path.dirname(os.path.abspath(__file__))+"/..")

with open("data/submissions.json", "r") as f:
    data_submissions = json.load(f)

data_translations = {}

for submission in data_submissions:
    if submission["source_media"] is not None or submission["source_instructions"] is not None:
        continue

    key = f"{submission['source_lang']}_#_{submission['target_lang']}_#_{submission['source_text']}"
    data_translations[key] = {"OMT-NLLB": None, "OMT-LLaMA": None}

with open("computed/translations_cache_request.json", "w") as f:
    json.dump(data_translations, f, indent=2, ensure_ascii=False)

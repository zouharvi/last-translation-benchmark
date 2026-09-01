# %%

import collections
import json
import os

os.chdir(os.path.dirname(os.path.abspath(__file__))+"/..")

from last_translation_benchmark.utils import save_compact_json

with open("data/submissions.json", "r") as f:
    data_submissions = json.load(f)

with open("computed/translations_cache.json", "r") as f:
    data_translations = collections.defaultdict(dict)
    data_translations.update(json.load(f))

for submission in data_submissions:
    if submission["source_media"] is not None or submission["source_instructions"] is not None:
        continue

    key = f"{submission['source_lang']}_#_{submission['target_lang']}_#_{submission['source_text']}"
    for mt_obj in submission["translations"]:
        cache_obj = data_translations.get(key, {})
        for model, translation in cache_obj.items():
            # translation is invalid
            if translation is None:
                continue

            # already exists in the submissions file
            if any(mt_obj["model"] == model for mt_obj in submission["translations"]):
                continue

            print("Adding", model)
            submission["translations"].append({
                "model": model,
                "translation": translation,
            })

save_compact_json(data_submissions, "data/submissions.json")
# %%

import collections
import json
import os

os.chdir(os.path.dirname(os.path.abspath(__file__))+"/..")

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

with open("data/submissions.json", "w") as f:
    json.dump(data_submissions, f, indent=2, ensure_ascii=False)

# %%

# # temporary cleanup
# import json
# import os
# os.chdir(os.path.dirname(os.path.abspath(__file__))+"/..")
# with open("data/submissions.json", "r") as f:
#     data_submissions = json.load(f)
# # remove models with "SKIP: "
# for submission in data_submissions:
#     submission["translations"] = [x for x in submission["translations"] if not x["model"].startswith("SKIP: ")]
# with open("data/submissions.json", "w") as f:
#     json.dump(data_submissions, f, indent=2, ensure_ascii=False)
# %%

# # temporary hack
# import os
# os.chdir(os.path.dirname(os.path.abspath(__file__))+"/..")
# import json
# with open("computed/translations_cache.json", "r") as f:
#     data_translations = json.load(f)
# data_translations = {
#     key: {model: mt_obj["translation"] for model, mt_obj in mt_objs.items()}
#     for key, mt_objs in data_translations.items()
# }
# with open("computed/translations_cache.json", "w") as f:
#     json.dump(data_translations, f, indent=2, ensure_ascii=False)
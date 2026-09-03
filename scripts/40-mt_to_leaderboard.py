import json
import os

os.chdir(os.path.dirname(os.path.abspath(__file__)) + "/..")

for model in [
    "Gemini 3.5 Flash Lite",
    "Gemini 3.1 Pro",
    "Google Translate",
    "Qwen 3.7 Plus",
    "Gemma 4",
    "GPT-5.4 Mini",
    "GPT-5.6 Sol",
    "human",
]:
    with open("data/v1.json", "r") as f:
        data = json.load(f)

    out = []
    for s in data:
        if "LTBv1-eval" not in s["tags"]:
            continue
        for t in s["translations"]:
            if t["model"] == model:
                t_val = t["translation"]
                break
        else:
            # default to empty string if no translation found for this model
            t_val = ""
        out.append({"id": s["id"], "translation": t_val})

    os.makedirs("computed/submissions/", exist_ok=True)
    with open(f"computed/submissions/{model}.json", "w") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)

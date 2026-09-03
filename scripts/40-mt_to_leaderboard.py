import json
import os

os.chdir(os.path.dirname(os.path.abspath(__file__)) + "/..")

WHITELIST_MT = [
    "human",
    "Gemma 4",
    "Gemini 2.5 Flash",
    "Llama 4 Maverick", 
    "GPT-5.4 Mini",
    "GPT-5.6 Sol",
    "GPT-5.6 Luna",
    "GPT-5.6 Terra",
    "Claude Haiku 4.5",
    "Claude Sonnet 4.5",
    "Command A", 
    "Command A+",
    "Qwen 3.7 Plus",
    "Gemini 3.1 Pro",
    "Gemini 3.5 Flash Lite",
    "Qwen 3.7 Flash",
    "gpt-oss-20b",
    "Kimi K3",
    "Google Translate",
    "Lara",
    "Nemotron 3 Ultra",
    "Deepseek V4 Pro",
    "TranslateGemma",
    "Tower+",
    "GemmaX2-28-9B",
    "HY-MT2",
    "Seed-X-PPO-7B",
    "NLLB 3.3B",
    "Command A Translate",
    "TinyAya Global",
]

for model in WHITELIST_MT:
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

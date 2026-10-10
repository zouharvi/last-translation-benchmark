import argparse
import asyncio
import json
import os
import urllib.parse

import tqdm
import utils

os.chdir(os.path.dirname(__file__)+"/..")

from last_translation_benchmark.utils import get_config, save_compact_json

COOKIES = {
    "ltb_user": urllib.parse.quote(get_config("LTB_API_USER")),
    "ltb_token": urllib.parse.quote(get_config("LTB_API_TOKEN"))
}

async def main():
    args = argparse.ArgumentParser()
    args.add_argument("--model", type=str, default="cohere/north-small-translate-09-2026")
    args = args.parse_args()

    model_path = args.model.replace("/", "_")

    with open("data/v1.json", "r") as f:
        data = json.load(f)
    data = [x for x in data if "LTBv1-eval" in x["tags"]]


    os.makedirs("computed/submissions", exist_ok=True)
    if os.path.exists(f"computed/submissions/{model_path}.json"):
        with open(f"computed/submissions/{model_path}.json", "r") as f:
            data_existing = {
                item["id"]: item["translation"] for item in json.load(f)
            }
    else:
        data_existing = {}

    data_new = []
    for item in tqdm.tqdm(data):
        if item["id"] in data_existing and data_existing[item["id"]] != "":
            translation = data_existing[item["id"]]
        else:
            prompt = f"Translate the following text from {item['source_lang']} to {item['target_lang']}. Output only the translation and nothing else:\n{item["source_text"]}"
            payload = {
                "model": args.model,
                "prompt": prompt,
                "cache": True,
            }

            try:
                response = await utils.request_post_with_backoff(url=get_config("LTB_API_URL"), json=payload, cookies=COOKIES)
                if response.status_code == 200:
                    translation = response.json()
                else:
                    print(f"  Error {response.status_code}: {response.text}")
                    translation = ""
            except Exception as e:
                print(f"  Request failed: {e}")
                translation = ""
            
        data_new.append({
            "id": item["id"],
            "translation": translation
        })

        save_compact_json(data_new, f"computed/submissions/{model_path}.json")

if __name__ == "__main__":
    asyncio.run(main())
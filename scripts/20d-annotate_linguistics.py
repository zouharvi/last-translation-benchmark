# %%

import argparse
import asyncio
import json
import os
import random
import urllib.parse

import frozendict
import tqdm
import utils

os.chdir(os.path.dirname(os.path.abspath(__file__)) + "/..")

from last_translation_benchmark.utils import (
    get_config,
    is_doomlooped_entropy,
    save_compact_json,
)

MODEL = "google/gemini-3.1-pro-preview"
PROMPT_FILE = "data/linguistics_prompt.txt"
DATA_FILE = "data/submissions.json"

COOKIES = {
    "ltb_user": urllib.parse.quote(get_config("LTB_API_USER")),
    "ltb_token": urllib.parse.quote(get_config("LTB_API_TOKEN"))
}

args = argparse.ArgumentParser()
args.add_argument("--chunks", type=int, default=20)
args.add_argument("--no-cache", action="store_true")
args = args.parse_args()
CHUNK_SIZE = args.chunks
CACHE = not args.no_cache

async def annotate(model, prompt, sub):
    if "linguistics" in sub:
        return False

    # deduplicate and hide identity
    translations = list({
        frozendict.frozendict({
            "translation": mt_obj["translation"],
            "verified": tuple(mt_obj["verified_extra"]["Gemini 3.1 Pro"]),
        })
        for mt_obj in sub["translations"]
        if (
            not mt_obj["model"].startswith("SKIP: ")
            and not is_doomlooped_entropy(mt_obj["translation"])
            and len(mt_obj["translation"]) < 10000
            and "verified_extra" in mt_obj and "Gemini 3.1 Pro" in mt_obj["verified_extra"]
        )
    })
    if len(translations) < 5:
        translations = list({
            frozendict.frozendict({
                "translation": mt_obj["translation"],
                "verified": tuple(mt_obj["verified"]),
            })
            for mt_obj in sub["translations"]
            if (
                not mt_obj["model"].startswith("SKIP: ")
                and not is_doomlooped_entropy(mt_obj["translation"])
                and len(mt_obj["translation"]) < 10000
                and "verified" in mt_obj
            )
        })
    while sum(len(mt_obj["translation"]) for mt_obj in translations) > 20000:
        translations = random.Random(0).sample(translations, len(translations) - 1)

    translations.sort(key=lambda x: sum(x["verified"]), reverse=True)
    if len(translations) < 2:
        print(f"Not enough unique translations for line {sub['id']}: {len(translations)}")
        return False

    payload_example = {
        "source_text": sub["source_text"],
        "translations": translations,
        "verification_rules": sub["verification_rules"],
        "source_lang": sub["source_lang"],
        "target_lang": sub["target_lang"],
    }
    if sub["source_instructions"] is not None:
        payload_example["source_instructions"] = sub["source_instructions"]
    
    payload = {
        "model": model,
        "prompt": (
            prompt
            + "\n\n-----\n\n"
            + json.dumps(payload_example, ensure_ascii=False, indent=2)
        ),
        "cache": CACHE,
    }

    if sub.get("source_media") is not None:
        payload["source_media"] = sub["source_media"]

    response = None
    try:
        response = await utils.request_post_with_backoff(url=get_config("LTB_API_URL"), json=payload, cookies=COOKIES)
        response.raise_for_status()
        res_text = response.json().strip("`").removeprefix("json").strip().strip("`")
        result = json.loads(res_text)
        assert isinstance(result, dict)
        assert "main_tags" in result and isinstance(result["main_tags"], list)
        assert "parallel_tags_1" in result and isinstance(result["parallel_tags_1"], list)
        assert "parallel_tags_2" in result and isinstance(result["parallel_tags_2"], list)
        assert "observations" in result and isinstance(result["observations"], str)
        sub["linguistics"] = result
        return True
    except Exception as e:
        print(e)
        if response is not None:
            print(f"Error in response: {response.status_code} - {response.text}") # type: ignore
        return False

async def main():
    with open(PROMPT_FILE, "r") as f:
        prompt = f.read()

    with open(DATA_FILE, "r") as f:
        submissions = json.load(f)

    submissions_accepted = [sub for sub in submissions if sub["status"] == "accept" and utils.submission_is_before_2026_09_01(sub)]

    print(f"Loaded {len(submissions)} submissions\n")

    cost_input, cost_output = utils.model_price_per_token(MODEL)
    tokens = utils.estimate_tokens(prompt) * 2500
    print(f"Annotating with {MODEL} costs ${cost_input*tokens + cost_output*tokens:.2f}")

    pbar = tqdm.tqdm(
        submissions_accepted,
        bar_format="{desc}{bar}[{percentage:3.0f}%, {elapsed}<{remaining}]",
        ascii="  ",
    )

    for chunk_i in range(0, len(submissions_accepted), CHUNK_SIZE):
        sub_chunk = submissions_accepted[chunk_i:chunk_i+CHUNK_SIZE]
        pbar.set_description(f"Processing #{sub_chunk[0]["id"]}--#{sub_chunk[-1]["id"]}")

        sub_changed = any(await asyncio.gather(*[annotate(MODEL, prompt, sub) for sub in sub_chunk]))

        if sub_changed:
            # re-save *everything* after each chunk
            save_compact_json(submissions, DATA_FILE)
        
        pbar.update(CHUNK_SIZE)


    # save finally
    save_compact_json(submissions, DATA_FILE)

if __name__ == "__main__":
    asyncio.run(main())
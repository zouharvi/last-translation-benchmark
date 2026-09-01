import argparse
import asyncio
import collections
import json
import os
import re
import urllib.parse

import tqdm
import utils

os.chdir(os.path.dirname(os.path.abspath(__file__))+"/..")

from last_translation_benchmark.utils import get_config, save_compact_json

PROMPT = """
Given this text from {source_lang} to {target_lang}, generate {verification_rules_count} verification rules that can be used to check the quality of translations.
The rule(s) should be concise, clear, and specific. Avoid vague or generic rules. Each rule should be a single sentence and should be evaluatable as true or false given a translation.
An example of rules:
```json
[
    "The word for 'paper' should be 'Artikel' or English loanword 'Paper' but not 'Papier'.",
    "In this context, '撒娇' should be equivalent to acting cute and adorable, instead of having any flirtatious or sexual sense.",
    "The translations for both the slaps should be different, but close enough lexically."
]
```

Output the rules in JSON format as above.
"""

MODELS = [
    {"name": "Gemma 4", "model": "google/gemma-4-31b-it", "support_image": True, "support_audio": False, "support_video": True},
    {"name": "Gemini 3.5 Flash Lite", "model": "google/gemini-3.5-flash-lite","support_image": True, "support_audio": True, "support_video": True},
    {"name": "GPT-5.4 Mini", "model": "openai/gpt-5.4-mini", "support_image": True, "support_audio": False, "support_video": False},
]
DATA_FILE = "data/submissions.json"

args = argparse.ArgumentParser()
args.add_argument("--chunks", type=int, default=50)
args.add_argument("--no-cache", action="store_true")
args = args.parse_args()
CHUNK_SIZE = args.chunks
CACHE = not args.no_cache

COOKIES = {
    "ltb_user": urllib.parse.quote(get_config("LTB_API_USER")),
    "ltb_token": urllib.parse.quote(get_config("LTB_API_TOKEN"))
}

def get_prompt(sub):
    text = sub["source_text"]
    src_lang = sub["source_lang"]
    tgt_lang = sub["target_lang"]
    source_media = sub["source_media"]
    source_instructions = sub["source_instructions"]

    prompt = PROMPT.format(
        source_lang=src_lang,
        target_lang=tgt_lang,
        verification_rules_count=len(sub["verification_rules"])
    )

    if source_instructions:
        prompt += f'\nAdditional instructions for this translation which can be taken into consideration are: "{source_instructions}"'

    if source_media:
        mime = source_media.split(",")[0]
        has_audio = "audio" in mime
        has_video = "video" in mime
        context_type = "audio" if has_audio else ("video" if has_video else "image")

        if text:
            prompt += f"\nThe input is accompanied by {context_type}. The input is:\n\n{text}"
        else:
            prompt += f"\nThe input is {context_type} (attached)."
    else:
        prompt += f"\nThe input is:\n\n{text}"

    return prompt


async def main():
    with open(DATA_FILE, "r") as f:
        submissions = json.load(f)

    submissions_accepted = [sub for sub in submissions if sub["status"] == "accept"]
    prompts = [get_prompt(sub) for sub in submissions_accepted]
    text_count = utils.estimate_tokens(" ".join(prompts))
    for model in MODELS:
        price_input, price_output = utils.model_price_per_token(model["model"])
        print(f"Cost for {model['model']:<40} ${price_input * text_count + price_output * text_count:.4f}")

    pbar = tqdm.tqdm(
        submissions_accepted,
        bar_format="{desc}{bar}[{percentage:3.0f}%, {elapsed}<{remaining}]",
        ascii="  ",
    )
    pbar_desc = ""
    pbar_tasks = set()

    def update_pbar():
        model_agg = collections.defaultdict(list)
        for model_mt, task in pbar_tasks:
            model_agg[model_mt].append(task)
        model_agg = list(model_agg.items())
        model_agg.sort(key=lambda x: len(x[1]), reverse=True)
        pbar.set_description(f"{pbar_desc} with {', '.join(f'{model} ({len(tasks)})' for model, tasks in model_agg)}")

    async def process_sub(sub) -> bool:
        if "verification_rules_synthetic" not in sub:
            sub["verification_rules_synthetic"] = {}

        async def _process_model(model):
            if model["name"] in sub["verification_rules_synthetic"]:
                return False
            payload = {
                "model": model["model"],
                "prompt": get_prompt(sub),
                "cache": CACHE,
            }
            if sub["source_media"]:
                payload["source_media"] = sub["source_media"]
                
                mime = sub["source_media"].split(",")[0]
                has_audio = "audio" in mime
                has_video = "video" in mime
                has_image = not has_audio and not has_video
                if (
                    (has_audio and not model["support_audio"]) or
                    (has_video and not model["support_video"]) or
                    (has_image and not model["support_image"])
                ):
                    return False

            try:
                pbar_tasks.add((model["model"], sub["id"]))
                update_pbar()
                response = await utils.request_post_with_backoff(url=get_config("LTB_API_URL"), json=payload, cookies=COOKIES)
                if response.status_code == 200:
                    if "```" in response.json():
                        text = response.json().split("```")[1].removeprefix("json").strip().strip("`")
                    else:
                        text = response.json().strip("`").removeprefix("json").strip().strip("`")
                    text = re.sub(r'([^\\])\\([abcdefl])', r'\1\\\\\2', text)
                    # replace trailing comma
                    text = re.sub(r',\s*([\]}])', r'\1', text)
                    rules_synthetic = json.loads(text)

                    if not isinstance(rules_synthetic, list) or not all(isinstance(rule, str) for rule in rules_synthetic):
                        raise ValueError(f"Invalid response format: {rules_synthetic}")

                    rules_synthetic = rules_synthetic[:len(sub["verification_rules"])]
                    sub["verification_rules_synthetic"][model["name"]] = rules_synthetic
                    return True
                else:
                    print(f"  Error {response.status_code}: {response.text}")
                    return False
            except Exception as e:
                print(f"  Request failed #{sub['id']} {model['name']}: {e}")
                if "response" in locals():
                    print(f"  Response: {response.status_code} - {response.text}") # type: ignore
                return False
            finally:
                pbar_tasks.discard((model["model"], sub["id"]))
                update_pbar()

        return any(await asyncio.gather(*[_process_model(model) for model in MODELS]))


    # chunk to multiple submissions at a time to avoid overloading the API
    for chunk_i in range(0, len(submissions_accepted), CHUNK_SIZE):
        # we're modifying accepted submissions but they point to the same object
        # this helps keep chunks similarly full
        sub_chunk = submissions_accepted[chunk_i:chunk_i+CHUNK_SIZE]

        pbar_desc = f"Processing #{sub_chunk[0]["id"]}--#{sub_chunk[-1]["id"]}"
        update_pbar()
        sub_changed = any(await asyncio.gather(*[process_sub(sub) for sub in sub_chunk]))
        if sub_changed:
            # save on each finalized changed submission
            save_compact_json(submissions, DATA_FILE)

        pbar.update(CHUNK_SIZE)

    # save finally
    save_compact_json(submissions, DATA_FILE)


if __name__ == "__main__":
    asyncio.run(main())

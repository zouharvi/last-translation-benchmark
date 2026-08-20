import asyncio
import collections
import json
import os
import random
import urllib.parse

import tqdm
import utils

os.chdir(os.path.dirname(os.path.abspath(__file__))+"/..")

from last_translation_benchmark.utils import get_config

MODELS = [
    {"name": "Gemma 4", "model": "google/gemma-4-31b-it", "support_image": True, "support_audio": False, "support_video": True},
    {"name": "Llama 4 Maverick", "model": "meta-llama/llama-4-maverick", "support_image": True, "support_audio": False, "support_video": False},
    {"name": "GPT-5.4 Mini", "model": "openai/gpt-5.4-mini", "support_image": True, "support_audio": False, "support_video": False},
    {"name": "Claude Haiku 4.5", "model": "anthropic/claude-haiku-4.5", "support_image": True, "support_audio": False, "support_video": False},
    {"name": "Claude Sonnet 4.5", "model": "anthropic/claude-sonnet-4.5", "support_image": True, "support_audio": False, "support_video": False},
    {"name": "Command A", "model": "cohere/command-a", "support_image": False, "support_audio": False, "support_video": False},
    # hit monthly quota?
    #{"name": "Command A+", "model": "cohere/command-a-plus-05-2026", "support_image": True, "support_audio": False, "support_video": False},
    {"name": "TinyAya Global", "model": "cohere/tiny-aya-global", "support_image": False, "support_audio": False, "support_video": False},
    {"name": "GPT-5.6 Terra", "model": "openai/gpt-5.6-terra", "support_image": True, "support_audio": False, "support_video": False},
    {"name": "GPT-5.6 Luna", "model": "openai/gpt-5.6-luna", "support_image": True, "support_audio": False, "support_video": False},
    {"name": "GPT-5.6 Sol", "model": "openai/gpt-5.6-sol", "support_image": True, "support_audio": False, "support_video": False},
    {"name": "Qwen 3.7 Plus", "model": "qwen/qwen3.7-plus", "support_image": True, "support_audio": False, "support_video": False},
    {"name": "Qwen 3.7 Flash", "model": "qwen/qwen3.7-flash", "support_image": True, "support_audio": False, "support_video": True},
    {"name": "Gemini 3.5 Flash Lite", "model": "google/gemini-3.5-flash-lite", "support_image": True, "support_audio": True, "support_video": True},
    {"name": "Gemini 3.1 Pro", "model": "google/gemini-3.1-pro-preview", "support_image": True, "support_audio": True, "support_video": True},
    {"name": "gpt-oss-20b", "model": "openai/gpt-oss-20b", "support_image": False, "support_audio": False, "support_video": False},
    {"name": "Kimi K3", "model": "moonshotai/kimi-k3", "support_image": True, "support_audio": False, "support_video": False},
    {"name": "Nemotron 3 Ultra", "model": "nvidia/nemotron-3-ultra-550b-a55b", "support_image": False, "support_audio": False, "support_video": False},
    {"name": "Deepseek V4 Pro", "model": "deepseek/deepseek-v4-pro", "support_image": False, "support_audio": False, "support_video": False},
    
    # special instructions privilege
    {"name": "Gemma 4", "model": "google/gemma-4-31b-it", "privilege": "ALL", "support_image": True, "support_audio": False, "support_video": True},
    {"name": "Gemini 3.5 Flash Lite", "model": "google/gemini-3.5-flash-lite", "privilege": "ALL", "support_image": True, "support_audio": True, "support_video": True},
    {"name": "GPT-5.4 Mini", "model": "openai/gpt-5.4-mini", "privilege": "ALL", "support_image": True, "support_audio": False, "support_video": False},
]
DATA_FILE = "data/submissions.json"
CHUNK_SIZE = 20

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

    if not source_media:
        prompt = f"Translate the following text from {src_lang} to {tgt_lang}. Output only the translation and nothing else:\n{text}"
    else:
        mime = source_media.split(",")[0]
        has_audio = "audio" in mime
        has_video = "video" in mime
        context_type = "audio" if has_audio else ("video" if has_video else "image")

        if text:
            prompt = (
                f"Translate the following text from {src_lang} to {tgt_lang}. "
                f"Use the provided {context_type} as additional context. "
                f"Output only the translation and nothing else:\n{text}"
            )
        else:
            prompt = f"Translate the provide {context_type} from {src_lang} to {tgt_lang}. Output only the textual translation and nothing else."
            
    if source_instructions:
        prompt += f'\nAdditional instructions for this translation are: "{source_instructions}"'
        
    return prompt


async def main():
    with open(DATA_FILE, "r") as f:
        submissions = json.load(f)

    prompts = [get_prompt(sub) for sub in submissions if sub["status"] == "accept"]
    text_count = utils.estimate_tokens(" ".join(prompts))
    print(f"Avg tokens for translation: {text_count/len(prompts):.1f}")
    for model in MODELS:
        price_input, price_output = utils.model_price_per_token(model["model"])

        if "privilege" in model:
            model["name"] = f"PRIVILEGE-{model["privilege"]}: {model["name"]}"

        print(f"Cost for {model['model']:<40} ${price_input * text_count + price_output * text_count:.4f}")

    #input("Do you wish to continue? (Ctrl+C to cancel)")

    pbar = tqdm.tqdm(
        submissions,
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
        # skip submissions which are not accepted
        if sub["status"] != "accept":
            return False

        sub_changed = False
        if "translations" not in sub:
            sub["translations"] = []

        async def _process_model_translate(model):
            # skip if this model has already provided a translation
            if any(t["model"] == model["name"] for t in sub["translations"]):
                return False

            if sub["source_media"]:
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

            prompt = get_prompt(sub)
            if "privilege" in model:
                verification_rules = []
                if model["privilege"] == "ONE":
                    verification_rules.append(random.Random(sub["id"]).choice(sub["verification_rules"])["value"])
                elif model["privilege"] == "ALL":
                    verification_rules.extend([rule["value"] for rule in sub["verification_rules"]])

                prompt += "\nYour translation will be checked by the following rules, so make sure to follow them: " + "; ".join(verification_rules)
            payload = {
                "model": model["model"],
                "prompt": prompt,
            }
            if sub["source_media"]:
                payload["source_media"] = sub["source_media"]

            try:
                pbar_tasks.add((model["name"], sub["id"]))
                update_pbar()
                response = await utils.request_post_with_backoff(url=get_config("LTB_API_URL"), json=payload, cookies=COOKIES)
                if response.status_code == 200:
                    translation = response.json()
                    new_t = {
                        "model": model["name"],
                        "translation": translation,
                    }
                    sub["translations"].append(new_t)
                    return True
                else:
                    print(f"  Error {response.status_code}: {response.text}")
                    return False
            except Exception as e:
                print(f"  Request failed: {e}")
                return False
            finally:
                pbar_tasks.discard((model["name"], sub["id"]))
                update_pbar()

        tasks = await asyncio.gather(*[_process_model_translate(model) for model in MODELS])
        sub_changed = sub_changed or any(tasks)

        return sub_changed

    submissions_accepted = [sub for sub in submissions if sub["status"] == "accept"]
    # chunk to multiple submissions at a time to avoid overloading the API
    for chunk_i in range(0, len(submissions_accepted), CHUNK_SIZE):
        # we're modifying accepted submissions but they point to the same object
        # this helps keep chunks similarly full
        sub_chunk = submissions_accepted[chunk_i:chunk_i+CHUNK_SIZE]

        pbar_desc = f"Translating #{sub_chunk[0]["id"]}--#{sub_chunk[-1]["id"]}"
        update_pbar()
        sub_changed = any(await asyncio.gather(*[process_sub(sub) for sub in sub_chunk]))
        if sub_changed:
            # save on each finalized changed submission
            with open(DATA_FILE, "w") as f:
                json.dump(submissions, f, indent=2, ensure_ascii=False)

        pbar.update(CHUNK_SIZE)

    # save finally
    with open(DATA_FILE, "w") as f:
        json.dump(submissions, f, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    asyncio.run(main())

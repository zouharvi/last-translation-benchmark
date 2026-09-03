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

from last_translation_benchmark.utils import (
    get_config,
    get_prompt_judge,
    get_prompt_verify,
    save_compact_json,
)

MODELS_VERIFIERS = [
    {"name": "Qwen 3.7 Flash", "model": "qwen/qwen3.7-flash", "support_privilege": False, "support_audio": False, "support_video": False},
    {"name": "Qwen 3.7 Plus", "model": "qwen/qwen3.7-plus", "support_privilege": False, "support_audio": False, "support_video": False},
    {"name": "Gemma 4", "model": "google/gemma-4-31b-it", "support_privilege": False, "support_audio": False, "support_video": True},
    {"name": "Gemini 3.1 Pro", "model": "google/gemini-3.1-pro-preview", "support_privilege": True, "support_audio": True, "support_video": True},
    {"name": "Gemini 3.5 Flash Lite", "model": "google/gemini-3.5-flash-lite", "support_privilege": False, "support_audio": True, "support_video": True},
    {"name": "GPT-5.4 Mini", "model": "openai/gpt-5.4-mini", "support_privilege": False, "support_audio": False, "support_video": False},
]
DATA_FILE = "data/submissions.json"

COOKIES = {
    "ltb_user": urllib.parse.quote(get_config("LTB_API_USER")),
    "ltb_token": urllib.parse.quote(get_config("LTB_API_TOKEN"))
}

args = argparse.ArgumentParser()
args.add_argument("--chunks", type=int, default=2)
args.add_argument("--no-cache", action="store_true")
args = args.parse_args()
CHUNK_SIZE = args.chunks
CACHE = not args.no_cache


async def main():
    with open(DATA_FILE, "r") as f:
        submissions = json.load(f)

    # Estimate tokens
    prompts_verifier = []
    prompts_judge = []
    submissions_accepted = [sub for sub in submissions if sub["status"] == "accept" and utils.submission_is_before_2026_09_01(sub)]
    for sub in submissions_accepted:
        for mt_obj in sub["translations"]:
            for rule in sub["verification_rules"]:
                prompts_verifier.append(get_prompt_verify(sub["source_text"], mt_obj["translation"], rule, sub["source_media"]))
            prompts_judge.append(get_prompt_judge(sub["source_text"], mt_obj["translation"], sub["source_media"]))

    text_count_verifier = utils.estimate_tokens(" ".join(prompts_verifier))
    text_count_judge = utils.estimate_tokens(" ".join(prompts_judge))
    print(f"Avg tokens for verifier prompt: {text_count_verifier/len(prompts_verifier):.1f}")
    print(f"Avg tokens for judge prompt: {text_count_judge/len(prompts_judge):.1f}")
    print(f"Total tokens (verifier): {text_count_verifier}")
    for model in MODELS_VERIFIERS:
        price_input, price_output = utils.model_price_per_token(model["model"])
        print(f"Cost for {model['model']:<40} ${price_input * text_count_verifier + price_output * text_count_verifier * 3:.4f}")
    print(f"Total tokens (judge): {text_count_judge}")
    for model in MODELS_VERIFIERS:
        price_input, price_output = utils.model_price_per_token(model["model"])
        print(f"Cost for {model['model']:<40} ${price_input * text_count_judge + price_output * text_count_judge * 3:.4f}")

    #input("Do you wish to continue? (Ctrl+C to cancel)")

    pbar = tqdm.tqdm(
        submissions_accepted,
        bar_format="{desc}{bar}[{percentage:3.0f}%, {elapsed}<{remaining}]",
        ascii="  ",
    )
    pbar_desc = ""
    pbar_tasks = set()

    def update_pbar():
        model_agg = collections.defaultdict(list)
        for sub_id, model_mt, model_llm, task in pbar_tasks:
            model_agg[model_llm].append(task)
        model_agg = list(model_agg.items())
        model_agg.sort(key=lambda x: len(x[1]), reverse=True)
        pbar.set_description(f"{pbar_desc} with {', '.join(f'{model} ({len(tasks)})' for model, tasks in model_agg)}")

    async def process_sub(sub) -> bool:
        if not sub["source_text"] and sub["source_media"]:
            source_text_display = "(attached)"
        else:
            source_text_display = sub["source_text"]

        async def _process_model_all(mt_obj, force_cache=False) -> bool:
            if mt_obj["model"].startswith("SKIP: "):
                return False

            
            sub_changed = False
            # verifier section
            if "verified_extra" not in mt_obj:
                mt_obj["verified_extra"] = {}

            async def _process_model_verifier(model) -> bool:
                # skip if this model has already verified this translation
                if (
                    model["name"] in mt_obj["verified_extra"]
                    and len(mt_obj["verified_extra"][model["name"]]) == len(sub["verification_rules"])
                    and all(r is not None for r in mt_obj["verified_extra"][model["name"]])
                ):
                    return False

                # check support_audio and support_video
                if sub["source_media"]:
                    mime = sub["source_media"].split(",")[0]
                    if "audio" in mime and not model["support_audio"]:
                        return False
                    if "video" in mime and not model["support_video"]:
                        return False

                # verify privileged translations only with one verifier
                if mt_obj["model"].startswith("PRIVILEGE-") and (not model["support_privilege"] or sub["source_media"] is not None or sub["source_instructions"] is not None):
                    return False

                results = []
                for rule_i, rule in enumerate(sub["verification_rules"]):
                    prompt = get_prompt_verify(source_text_display, mt_obj["translation"], rule, sub["source_media"])

                    payload = {
                        "model": model["model"],
                        "prompt": prompt,
                        "cache": force_cache or CACHE,
                    }
                    if sub["source_media"]:
                        payload["source_media"] = sub["source_media"]

                    progress_id = (sub["id"], mt_obj["model"], model['name'], f"§{rule_i}")
                    try:
                        pbar_tasks.add(progress_id)
                        update_pbar()
                        response = await utils.request_post_with_backoff(url=get_config("LTB_API_URL"), json=payload, cookies=COOKIES)
                        if response.status_code == 200:
                            res_text = response.json()
                            if res_text is None:
                                print(f"  Empty LLM response for #{sub['id']}")
                                results.append(None)
                                continue

                            tokens = res_text.strip().lower().strip(" \t\n\r.,!?\"'*").split()
                            text_clean = tokens[-1] if tokens else ""
                            if "pass" in text_clean:
                                results.append(True)
                            elif "fail" in text_clean:
                                results.append(False)
                            elif "pass" in res_text:
                                results.append(True)
                            elif "fail" in res_text:
                                results.append(False)
                            else:
                                print(f"  Invalid LLM response: {res_text}")
                                results.append(None)
                        else:
                            print(f"  Error {response.status_code}: {response.text}")
                            results.append(None)
                    except Exception as e:
                        print(f"  Request failed: {e}")
                        results.append(None)
                    finally:
                        pbar_tasks.discard(progress_id)
                        update_pbar()

                # store the result
                mt_obj["verified_extra"][model["name"]] = results
                return True

            # parallelize multiple LLM verifiers at the same time
            tasks = await asyncio.gather(*[_process_model_verifier(model) for model in MODELS_VERIFIERS])
            sub_changed = sub_changed or any(tasks)

            # judge section
            if "judge_extra" not in mt_obj:
                mt_obj["judge_extra"] = {}

            async def _process_model_judge(model):
                # skip if this model has already verified this translation
                if model["name"] in mt_obj["judge_extra"] and mt_obj["judge_extra"][model["name"]] is not None:
                    return False

                # judge privileged translations only with one judge
                if mt_obj["model"].startswith("PRIVILEGE-") and not model["support_privilege"]:
                    return False

                # check support_audio and support_video
                if sub["source_media"]:
                    mime = sub["source_media"].split(",")[0]
                    if "audio" in mime and not model["support_audio"]:
                        return False
                    if "video" in mime and not model["support_video"]:
                        return False

                prompt = get_prompt_judge(source_text_display, mt_obj["translation"], sub["source_media"])

                payload = {
                    "model": model["model"],
                    "prompt": prompt,
                    "cache": force_cache or CACHE,
                }
                if sub["source_media"]:
                    payload["source_media"] = sub["source_media"]

                progress_id = (sub["id"], mt_obj["model"], model['name'], "j")
                result = None
                try:
                    pbar_tasks.add(progress_id)
                    update_pbar()
                    response = await utils.request_post_with_backoff(url=get_config("LTB_API_URL"), json=payload, cookies=COOKIES)
                    if response.status_code == 200:
                        res_text = response.json()
                        if res_text is None:
                            print(f"  Empty LLM response for #{sub['id']}")
                            result = None
                        else:
                            try:
                                # take only the last word, in case the model outputs extra text
                                tokens = res_text.strip().lower().replace("*", "").strip(" \t\n\r.,!?\"'%").split()
                                text_clean = tokens[-1] if tokens else ""
                                result = int(float(text_clean))
                                if not (0 <= result <= 100):
                                    raise ValueError(f"  Result {result} out of range")
                            except ValueError:
                                result = re.search(r"\*\*\d+\%?\*\*", res_text)
                                if result:
                                    result = result[0].replace("*", "").replace("%", "")
                                    if all(c.isdigit() for c in result):
                                        result = int(result)
                                    else:
                                        print(f"  Invalid LLM response: {res_text}")
                                        result = None
                                else:
                                    print(f"  Invalid LLM response: {res_text}")
                                    result = None
                    else:
                        print(f"  Error {response.status_code}: {response.text}")
                        result = None
                except Exception as e:
                    print(f"  Request failed: {e}")
                    result = None
                finally:
                    pbar_tasks.discard(progress_id)
                    update_pbar()

                mt_obj["judge_extra"][model["name"]] = result
                return True

            # parallelize all LLM judges at the same time
            tasks = await asyncio.gather(*[_process_model_judge(model) for model in MODELS_VERIFIERS])
            sub_changed = sub_changed or any(tasks)
            return sub_changed

        # choose only unique MTs first
        translations_to_mt_i = {}
        for mt_i, mt_obj in enumerate(sub["translations"]):
            if mt_obj["translation"] not in translations_to_mt_i:
                translations_to_mt_i[mt_obj["translation"]] = mt_i

        print(f"#{sub['id']}: We have {len(sub['translations'])} translations, {len(translations_to_mt_i)} unique translations")
        tasks_unique = await asyncio.gather(*[
            _process_model_all(mt_obj)
            for mt_obj_i, mt_obj in enumerate(sub["translations"])
            if mt_obj_i in translations_to_mt_i.values()
        ])

        # TODO: don't rerun for now
        return any(tasks_unique)

        # even if we have cache turned off, we want to enforce it because in the second round
        # we should reuse previous results in all scenarios
        tasks_all = await asyncio.gather(*[_process_model_all(mt_obj, force_cache=True) for mt_obj in sub["translations"]])
        return any(tasks_unique) or any(tasks_all)


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

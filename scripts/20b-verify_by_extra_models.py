import asyncio
import collections
import json
import os
import random
import re
import urllib.parse

import tqdm
import utils

os.chdir(os.path.dirname(os.path.abspath(__file__))+"/..")

from last_translation_benchmark.utils import get_config

MODELS_VERIFIERS = [
    {"name": "Qwen 3.7 Flash", "model": "qwen/qwen3.7-flash"},
    {"name": "Qwen 3.7 Plus", "model": "qwen/qwen3.7-plus"},
    {"name": "Gemma 4", "model": "google/gemma-4-31b-it"},
    {"name": "Gemini 3.1 Pro", "model": "google/gemini-3.1-pro-preview"},
    {"name": "Gemini 3.5 Flash Lite", "model": "google/gemini-3.5-flash-lite"},
    {"name": "GPT-5.4 Mini", "model": "openai/gpt-5.4-mini"},
]
DATA_FILE = "data/submissions.json"

COOKIES = {
    "ltb_user": urllib.parse.quote(get_config("LTB_API_USER")),
    "ltb_token": urllib.parse.quote(get_config("LTB_API_TOKEN"))
}

CACHE = True

def get_prompt_verify(source_text: str, translation: str, rule: str, source_media: str | None) -> str:
    prompt = f"Your goal is to verify whether a translation fulfills a criterion.\n\nCriterion: {rule}\n\nInput: {source_text}\n\nTranslation to verify: {translation}\n\nOutput only pass or fail and nothing else."
    
    if source_media:
        mime = source_media.split(",")[0]
        context_type = "audio" if "audio" in mime else ("video" if "video" in mime else "image")
        prompt += f"\n\nUse the provided {context_type} as additional context."
        
    return prompt

def get_prompt_judge(source_text: str, translation: str, source_media: str | None) -> str:
    prompt = f"Your goal is to evaluate the quality of a translation. Translation quality is evaluated as follows:\n\n85-100% (Very Good): Complete meaning transfer; perfectly natural; no or minimal proofreading.\n65-80% (Good): Near complete transfer, minor inaccuracies; mostly natural, minor awkwardness; needs light proofreading.\n45-60% (Acceptable): Main ideas conveyed, noticeable inaccuracies or omissions; uneven naturalness, awkward phrasing; usable only after substantial revision.\n25-40% (Borderline): Partial transfer; frequent misinterpretation or omission confusing the message; often unnatural; requires major rewrite.\n0-20% (Not acceptable): Violation of meaning; large portions mistranslated, missing, or incoherent; unusable without complete retranslation.\n\nInput: {source_text}\n\nTranslation to evaluate: {translation}\n\nOutput a single number between 0 and 100, representing the quality of the translation, and nothing else."

    if source_media:
        mime = source_media.split(",")[0]
        context_type = "audio" if "audio" in mime else ("video" if "video" in mime else "image")
        prompt += f"\n\nUse the provided {context_type} as additional context."

    return prompt

async def main():
    with open(DATA_FILE, "r") as f:
        submissions = json.load(f)

    # Estimate tokens
    prompts_verifier = []
    prompts_judge = []
    for sub in submissions:
        if sub["status"] != "accept":
            continue

        if not sub["source_text"] and sub["source_media"]:
            source_text_display = "(attached)"
        else:
            source_text_display = sub["source_text"]

        for mt_obj in sub["translations"]:
            for rule_obj in sub["verification_rules"]:
                prompts_verifier.append(get_prompt_verify(source_text_display, mt_obj["translation"], rule_obj["value"], sub["source_media"]))
            prompts_judge.append(get_prompt_judge(source_text_display, mt_obj["translation"], sub["source_media"]))

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
        submissions,
        bar_format="{desc}{bar}[{percentage:3.0f}%, {elapsed}<{remaining}]",
        ascii="  ",
    )
    pbar_desc = ""
    pbar_tasks = set()

    def update_pbar():
        model_agg = collections.defaultdict(list)
        for model_mt, model_llm, task in pbar_tasks:
            model_agg[model_llm].append(task)
        model_agg = list(model_agg.items())
        model_agg.sort(key=lambda x: len(x[1]), reverse=True)
        pbar.set_description(f"{pbar_desc} with {', '.join(f'{model} ({len(tasks)})' for model, tasks in model_agg)}")

    for sub in pbar:
        if sub["status"] != "accept":
            continue

        # skip items that have source media for now
        if sub["source_media"]:
            continue

        # skip items with more than two validation rules for now
        if len(sub["verification_rules"]) > 2:
            continue
        
        # take 50% of submissions randomly for now
        if 1.0 < random.Random(sub["id"]).random():
            continue

        if not sub["source_text"] and sub["source_media"]:
            source_text_display = "(attached)"
        else:
            source_text_display = sub["source_text"]

        pbar_desc = f"Verifying #{sub['id']}"
        update_pbar()

        async def _process_model_all(mt_obj) -> bool:
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

                results = []
                for rule_i, rule_obj in enumerate(sub["verification_rules"]):
                    prompt = get_prompt_verify(source_text_display, mt_obj["translation"], rule_obj["value"], sub["source_media"])

                    payload = {
                        "model": model["model"],
                        "prompt": prompt,
                        "cache": CACHE,
                    }
                    if sub["source_media"]:
                        payload["source_media"] = sub["source_media"]

                    progress_id = (mt_obj["model"], model['name'], f"§{rule_i}")
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

                            text_clean = res_text.strip().lower().strip(" \t\n\r.,!?\"'*").split()[-1]
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

                prompt = get_prompt_judge(source_text_display, mt_obj["translation"], sub["source_media"])

                payload = {
                    "model": model["model"],
                    "prompt": prompt,
                    "cache": CACHE,
                }
                if sub["source_media"]:
                    payload["source_media"] = sub["source_media"]

                progress_id = (mt_obj["model"], model['name'], "j")
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
                                text_clean = res_text.strip().lower().replace("*", "").strip(" \t\n\r.,!?\"'%").split()[-1]
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

        print(f"We have {len(sub['translations'])} translations, {len(translations_to_mt_i)} unique translations")
        tasks_unique = await asyncio.gather(*[
            _process_model_all(mt_obj)
            for mt_obj_i, mt_obj in enumerate(sub["translations"])
            if mt_obj_i in translations_to_mt_i.values()
        ])
        
        tasks_all = await asyncio.gather(*[_process_model_all(mt_obj) for mt_obj in sub["translations"]])
        sub_changed = any(tasks_unique) or any(tasks_all)

        if sub_changed:
            with open(DATA_FILE, "w") as f:
                json.dump(submissions, f, indent=2, ensure_ascii=False)

    # save finally
    with open(DATA_FILE, "w") as f:
        json.dump(submissions, f, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    asyncio.run(main())

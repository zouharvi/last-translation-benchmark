import argparse
import json
import os
import re
import tomllib
import random
from pathlib import Path
import time
import requests


from llm_transplant_prompts import PROMPTS
from openai import OpenAI
from tqdm import tqdm

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent

DATA_IN = "./submissions_v2.json"
PROVIDER = "openai"
API_URL = "https://last-translation-benchmark.vilda.net/api/"

CONFIGS = {
    "openai": {
        "base_url": None,
        "key_env": "OPENAI_API_KEY",
        "model": "gpt-5.6-terra",
    },
    "openrouter": {
        "base_url": "https://openrouter.ai/api/v1",
        "key_env": "OPENROUTER_API_KEY",
        "model": "~deepseek/deepseek-v4-flash-latest",
    },
}

CFG = CONFIGS[PROVIDER]
MODEL = CFG["model"]


KEYS_PATH = HERE / "keys.toml"
LLM_FIELDS = (
    "source_text",
    "source_lang",
    "target_lang",
    "verification_rules",
    "translations",
    "source_instructions",
)
OPENAI_CLIENT: OpenAI | None = None


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("transplant_side", choices=["source", "target"])
    p.add_argument("transplant_lang")
    p.add_argument("--data-in", type=Path, default=DATA_IN)
    p.add_argument("--data-out", type=Path, default=f"scripts/langtransfer/")
    p.add_argument("--prompt", type=int, default=1)
    p.add_argument("--limit", type=int)
    p.add_argument("--verification-model", choices=["openrouter", "debugging"], default="debugging")
    return p.parse_args()


def load_data(path: Path):
    with path.open() as f:
        return json.load(f)


def load_keys(path: Path):
    with path.open("rb") as f:
        return tomllib.load(f)


def load_keys_to_env(keys: dict) -> None:
    for key, value in keys.items():
        if value is not None:
            os.environ[str(key)] = str(value)


def make_prompt(
    submission: dict,
    transplant_side: str,
    transplant_lang: str,
    prompt_text: str,
) -> str:
    payload = llm_payload(submission)
    return f"""{prompt_text}

Return only the JSON object.

{json.dumps(payload, ensure_ascii=False, indent=2)}
transplant_side={transplant_side}
transplant_lang={transplant_lang}

"""


def llm_payload(submission: dict) -> dict:
    payload = {k: submission.get(k) for k in LLM_FIELDS if k in submission}
    payload["translations"] = [
        t for t in submission.get("translations", []) if t.get("model") == "human"
    ]
    return payload


def call_transplant_llm(client: OpenAI, prompt: str) -> dict:
    resp = client.chat.completions.create(
      model=MODEL,
      messages=[{"role": "user", "content": prompt}],
      response_format={"type": "json_object"},
      seed=0,
  )
    return parse_json(resp.choices[0].message.content)


def parse_json(text: str) -> dict:
    match = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if match:
        text = match.group(1)
    return json.loads(text)


def get_translation_text(entry: dict) -> str | None:
    text = entry.get("translation", entry.get("value"))
    return text if isinstance(text, str) and text.strip() else None

def _cookies(keys: dict) -> dict:
    return {"ltb_user": "Bhavitvya_Api", "ltb_token": keys["LTB_KEY"]}

def translation_passes(entry: dict) -> bool:
    verified = entry.get("verified")
    return isinstance(verified, list) and bool(verified) and all(verified)


def add_pass_flags(submission: dict, k: int = 2) -> dict:
    nonhuman_passes = 0
    human_passes = False

    for entry in submission.get("translations", []):
        passed = translation_passes(entry)
        if entry.get("model") == "human":
            human_passes = passed
        elif passed:
            nonhuman_passes += 1

    submission["passed_atmost_k"] = nonhuman_passes <= k
    submission["human_passes"] = human_passes
    return submission


def openai_client() -> OpenAI:
    global OPENAI_CLIENT
    if OPENAI_CLIENT is None:
        api_key = os.environ.get(CFG["key_env"])
        if not api_key:
            raise ValueError(f"{CFG['key_env']} is missing")
        OPENAI_CLIENT = OpenAI(api_key=api_key, base_url=CFG["base_url"])
    return OPENAI_CLIENT

def fill_translations_via_api(submission: dict, cookies: dict) -> dict:
    payload = {
        "text": submission["source_text"],
        "source_lang": submission["source_lang"],
        "target_lang": submission["target_lang"],
        "source_media": submission.get("source_media"),
        "source_instructions": submission.get("source_instructions"),
    }
    resp = requests.post(API_URL + "translate-submission", json=payload, cookies=cookies)
    if resp.status_code == 429:
        raise RuntimeError("Quota exceeded")
    resp.raise_for_status()
    results = resp.json()["results"]

    translations = []
    for entry in submission.get("translations", []):
        if entry.get("model") == "human":
            text = get_translation_text(entry)
            if text:
                translations.append({"model": "human", "translation": text, "verified": None})

    for r in results:
        if r.get("error"):
            print(f"Translation failed for {r['model']}: {r['error']}")
            continue
        if r.get("translation") is not None:
            translations.append({"model": r["model"], "translation": r["translation"], "verified": None})

    unique = list(dict.fromkeys(t["translation"] for t in translations))

    verify_payload = {
        "source_text": submission["source_text"],
        "translations": unique,
        "verification_rules": [r["value"] for r in submission["verification_rules"]],
        "source_media": submission.get("source_media"),
    }
    vresp = requests.post(API_URL + "verify-submission", json=verify_payload, cookies=cookies)
    if vresp.status_code == 429:
        raise RuntimeError("Quota exceeded")
    vresp.raise_for_status()
    verified_map = dict(zip(unique, vresp.json()["results"]))   # text -> list[bool]

    for t in translations:
        t["verified"] = verified_map[t["translation"]]

    submission["translations"] = translations
    return submission

def transplanted_id(submission: dict, transplant_side: str, transplant_lang: str) -> str:
    return f"{submission['id']}_transplanted_{transplant_side}_{transplant_lang}"

def _normalize_rules(rules):
    """Force verification_rules into a list of {"value": str} dicts.

    The transplant LLM sometimes returns them as bare strings.
    """
    if not isinstance(rules, list):
        return rules
    out = []
    for r in rules:
        if isinstance(r, str):
            out.append({"value": r})
        elif isinstance(r, dict) and "value" in r:
            out.append(r)
        elif isinstance(r, dict):
            # dict without "value" — best-effort: take the first string field
            val = next((v for v in r.values() if isinstance(v, str)), None)
            out.append({"value": val} if val is not None else r)
        else:
            out.append({"value": str(r)})
    return out

def merge_transplant(original: dict, llm_result: dict, transplant_side: str, transplant_lang: str) -> dict:
    merged = {k: v for k, v in original.items() if k not in LLM_FIELDS}
    merged["orig_id"] = original["id"]
    merged["id"] = transplanted_id(original, transplant_side, transplant_lang)

    for key in LLM_FIELDS:
        if key in llm_result:
            merged[key] = llm_result[key]

    merged["source_lang" if transplant_side == "source" else "target_lang"] = transplant_lang
    if "verification_rules" in merged:
        merged["verification_rules"] = _normalize_rules(merged["verification_rules"])
    return merged


def is_valid_submission(submission: dict) -> bool:
    required = [
        "source_text",
        "source_lang",
        "target_lang",
        "verification_rules",
        "translations",
    ]
    if not all(k in submission for k in required):
        return False
    if not isinstance(submission["verification_rules"], list):
        return False
    if not isinstance(submission["translations"], list):
        return False
    return all("value" in r for r in submission["verification_rules"])


def output_path(transplant_side: str, transplant_lang: str, prompt_key: int) -> Path:
    safe_lang = re.sub(r"[^A-Za-z0-9]+", "_", transplant_lang).strip("_").lower()
    return ROOT / "data" / "langtransfer" / "transplanted" / f"langtransfer_p{prompt_key}_{transplant_side}_{safe_lang}.json"


def transplant(
    transplant_side: str,
    transplant_lang: str,
    prompt_key: int = 1,
    limit: int | None = None,
    data_in: Path = DATA_IN,
    out_path: Path | None = None,
) -> list[dict]:
    keys = load_keys(KEYS_PATH)
    load_keys_to_env(keys)
    submissions = load_data(data_in)
    cookies = _cookies(keys)

    if prompt_key not in PROMPTS:
        raise ValueError(f"Unknown prompt key: {prompt_key}")
    if not keys.get(CFG["key_env"]):
        raise ValueError(f"{CFG['key_env']} is missing from {KEYS_PATH}")
    client = openai_client()

    out = []
    for sub in tqdm(submissions):
        if sub.get("source_lang", "").lower().strip() == transplant_lang.lower().strip() or sub.get("target_lang", "").lower().strip() == transplant_lang.lower().strip():
            print(f"Skipping submission with same language for id={sub.get('id')}")
            continue
        if sub.get("source_media"):
            print(f"Skipping submission with source media for id={sub.get('id')}")
            continue

        prompt = make_prompt(sub, transplant_side, transplant_lang, PROMPTS[prompt_key])
        transplanted = merge_transplant(
            sub,
            call_transplant_llm(client, prompt),
            transplant_side,
            transplant_lang,
        )
        time.sleep(random.randint(2, 3))
        try:
            transplanted = fill_translations_via_api(transplanted, cookies)
        except RuntimeError as e:
            print(f"Stopping: {e}")
            break
        except requests.HTTPError as e:
            print(f"Skipping id={sub.get('id')}: {e}")
            continue


        transplanted = add_pass_flags(transplanted)
        if not is_valid_submission(transplanted):
            print(f"Invalid transplanted submission for id={sub.get('id')}")
        out.append(transplanted)
        if limit and len(out) >= limit:
            break

    if out_path is None:
        out_path = output_path(transplant_side, transplant_lang, prompt_key)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
        f.write("\n")
    return out


def main():
    args = parse_args()
    path = Path(args.data_out) / f"{MODEL}_{args.transplant_lang}_{args.transplant_side}.json"


    transplant(
        args.transplant_side,
        args.transplant_lang,
        prompt_key=args.prompt,
        limit=args.limit,
        data_in=args.data_in,
        out_path=path,
    )
    print(path)


if __name__ == "__main__":
    main()

import argparse
import json
import re
import tomllib
from pathlib import Path

from llm_transplant_prompts import PROMPTS
from openai import OpenAI
from tqdm import tqdm

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent

DATA_IN = ROOT / "data" / "langtransfer" / "submissions.json"
MODEL = "gpt-5.4-mini"
KEYS_PATH = HERE / "keys.toml"
LLM_FIELDS = (
    "source_text",
    "source_lang",
    "target_lang",
    "verification_rules",
    "translations",
    "source_instructions",
)


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("transplant_side", choices=["source", "target"])
    p.add_argument("transplant_lang")
    p.add_argument("--prompt", type=int, default=1)
    p.add_argument("--limit", type=int)
    return p.parse_args()


def load_data(path: Path):
    with path.open() as f:
        return json.load(f)


def load_keys(path: Path):
    with path.open("rb") as f:
        return tomllib.load(f)


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
    resp = client.responses.create(
        model=MODEL,
        input=prompt,
    )
    return parse_json(resp.output_text)


def parse_json(text: str) -> dict:
    match = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if match:
        text = match.group(1)
    return json.loads(text)


def fill_translations(submission: dict) -> dict:
    raise NotImplementedError("Not implemented")
    # TODO: call translation APIs and set translations with verified=None.
    return submission


def transplanted_id(submission: dict, transplant_side: str, transplant_lang: str) -> str:
    return f"{submission['id']}_transplanted_{transplant_side}_{transplant_lang}"


def merge_transplant(original: dict, llm_result: dict, transplant_side: str, transplant_lang: str) -> dict:
    merged = {k: v for k, v in original.items() if k not in LLM_FIELDS}
    merged["orig_id"] = original["id"]
    merged["id"] = transplanted_id(original, transplant_side, transplant_lang)

    for key in LLM_FIELDS:
        if key in llm_result:
            merged[key] = llm_result[key]

    merged["source_lang" if transplant_side == "source" else "target_lang"] = transplant_lang
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
    fill_api_translations: bool = False,
) -> list[dict]:
    keys = load_keys(KEYS_PATH)
    submissions = load_data(data_in)

    if prompt_key not in PROMPTS:
        raise ValueError(f"Unknown prompt key: {prompt_key}")
    if not keys.get("OPENAI_API_KEY"):
        raise ValueError(f"OPENAI_API_KEY is missing from {KEYS_PATH}")
    client = OpenAI(api_key=keys["OPENAI_API_KEY"])

    out = []
    for sub in tqdm(submissions):
        if sub.get("source_lang", "").lower().strip() == transplant_lang.lower().strip() or sub.get("target_lang", "").lower().strip() == transplant_lang.lower().strip():
            out.append(sub)
            continue
        if sub.get("source_media"):
            print(f"Skipping submission with source media for id={sub.get('id')}")
            continue


        prompt = make_prompt(
            sub,
            transplant_side,
            transplant_lang,
            PROMPTS[prompt_key],
        )
        transplanted = merge_transplant(
            sub,
            call_transplant_llm(client, prompt),
            transplant_side,
            transplant_lang,
        )
        if fill_api_translations:
            transplanted = fill_translations(transplanted)
        if not is_valid_submission(transplanted):
            print(f"Invalid transplanted submission for id={sub.get('id')}")
        out.append(transplanted)
        if limit and len(out) >= limit:
            break

    if out_path is None:
        out_path = output_path(transplant_side, transplant_lang, prompt_key)
    out_path.parent.mkdir(exist_ok=True)
    with out_path.open("w") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
        f.write("\n")
    return out


def main():
    args = parse_args()
    path = output_path(args.transplant_side, args.transplant_lang, args.prompt)
    transplant(
        args.transplant_side,
        args.transplant_lang,
        prompt_key=args.prompt,
        limit=args.limit,
        out_path=path,
    )
    print(path)


if __name__ == "__main__":
    main()

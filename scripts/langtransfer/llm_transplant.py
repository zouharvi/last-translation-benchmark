import argparse
import asyncio
import inspect
import json
import os
import re
import sys
import tomllib
import types
from pathlib import Path

from llm_transplant_prompts import PROMPTS
from openai import OpenAI
from tqdm import tqdm

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent

DATA_IN = ROOT / "data" / "langtransfer" / "submissions_v2.json"
MODEL = "gpt-5.4-mini"
KEYS_PATH = HERE / "keys.toml"
NON_OPENROUTER_MODELS = {"Lara", "Google Translate"}
LLM_FIELDS = (
    "source_text",
    "source_lang",
    "target_lang",
    "verification_rules",
    "translations",
    "source_instructions",
)
OPENAI_CLIENT: OpenAI | None = None
BACKEND_DB_INITIALIZED = False
BACKEND_VERIFIER = None


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("transplant_side", choices=["source", "target"])
    p.add_argument("transplant_lang")
    p.add_argument("--prompt", type=int, default=1)
    p.add_argument("--limit", type=int)
    p.add_argument("--fill-api-translations", action="store_true")
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


def get_translation_text(entry: dict) -> str | None:
    text = entry.get("translation", entry.get("value"))
    return text if isinstance(text, str) and text.strip() else None


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


def model_supports_request(model_info: dict, source_media: str | None) -> bool:
    if not source_media:
        return model_info["support_textonly"]

    mime = source_media.split(",")[0]
    if "audio" in mime:
        return model_info["support_audio"]
    if "video" in mime:
        return model_info["support_video"]
    return model_info["support_image"]


def make_server_importable() -> None:
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))

    # Avoid executing server/__init__.py, which mounts built frontend files that
    # may not exist in this local script environment.
    if "server" not in sys.modules:
        pkg = types.ModuleType("server")
        pkg.__path__ = [str(ROOT / "server")]
        sys.modules["server"] = pkg


def load_backend_models() -> list[dict]:
    make_server_importable()
    from server.routers import MODEL_LIBRARY

    return MODEL_LIBRARY


def load_selected_models(submissions: list[dict]) -> list[dict]:
    names = {
        t.get("model")
        for s in submissions
        for t in s.get("translations", [])
        if t.get("model")
    }
    allowed = names - NON_OPENROUTER_MODELS - {"human", "perfect"}
    return [
        model_info
        for model_info in load_backend_models()
        if model_info["name"] in allowed
    ]


def load_backend_verifier():
    global BACKEND_VERIFIER
    if BACKEND_VERIFIER is not None:
        return BACKEND_VERIFIER

    make_server_importable()
    from server.services import verify_llm

    BACKEND_VERIFIER = verify_llm
    return BACKEND_VERIFIER


async def init_backend_db() -> None:
    global BACKEND_DB_INITIALIZED
    if BACKEND_DB_INITIALIZED:
        return

    make_server_importable()
    from server.db import init_db

    await init_db()
    BACKEND_DB_INITIALIZED = True


def openai_client() -> OpenAI:
    global OPENAI_CLIENT
    if OPENAI_CLIENT is None:
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise ValueError(f"OPENAI_API_KEY is missing from {KEYS_PATH}")
        OPENAI_CLIENT = OpenAI(api_key=api_key)
    return OPENAI_CLIENT


async def verify_llm_debugging(
    source_text: str, translation: str, rule: str, source_media: str | None = None
) -> bool:
    if source_media:
        raise ValueError("Debugging verification only supports text submissions")
    prompt = f"Your goal is to verify whether a translation fulfills a criterion.\n\nCriterion: {rule}\n\nInput: {source_text}\n\nTranslation to verify: {translation}\n\nOutput only pass or fail and nothing else."
    client = openai_client()
    response = await asyncio.to_thread(
        lambda: client.responses.create(
            model=MODEL,
            input=prompt,
        )
    )
    text_clean = response.output_text.strip().lower().strip(" \t\n\r.,!?\"'*")
    if text_clean == "pass":
        return True
    if text_clean == "fail":
        return False
    raise ValueError(f"Invalid LLM response: {response.output_text}")


async def run_model_translation(model_info: dict, submission: dict) -> dict:
    func = model_info["fn"]
    try:
        kwargs = {
            "text": submission["source_text"],
            "src_lang": submission["source_lang"],
            "tgt_lang": submission["target_lang"],
            "source_media": submission.get("source_media"),
            "source_instructions": submission.get("source_instructions"),
        }
        if inspect.iscoroutinefunction(func):
            translation = await func(**kwargs)
        else:
            translation = await asyncio.to_thread(func, **kwargs)
        return {
            "model": model_info["name"],
            "translation": translation,
            "error": None,
        }
    except Exception as exc:
        if str(exc).startswith("No endpoints found that support"):
            return {"model": model_info["name"], "translation": None, "error": None}
        return {"model": model_info["name"], "translation": None, "error": str(exc)}


async def verify_translation(
    source_text: str,
    translation: str,
    rules: list[dict],
    source_media: str | None,
    verification_model: str,
) -> list[bool]:
    if verification_model == "debugging":
        verify_llm = verify_llm_debugging
    else:
        verify_llm = load_backend_verifier()

    verified = []
    for rule in rules:
        verified.append(
            await verify_llm(source_text, translation, rule["value"], source_media)
        )
    return verified


async def fill_translations_async(
    submission: dict,
    verification_model: str,
    selected_models: list[dict],
) -> dict:
    await init_backend_db()

    source_media = submission.get("source_media")
    tasks = [
        run_model_translation(model_info, submission)
        for model_info in selected_models
        if model_supports_request(model_info, source_media)
    ]
    results = await asyncio.gather(*tasks)

    translations = []
    for entry in submission.get("translations", []):
        if entry.get("model") == "human":
            text = get_translation_text(entry)
            if text:
                translations.append(
                    {"model": "human", "translation": text, "verified": None}
                )

    for result in results:
        if result["error"]:
            print(f"Translation failed for {result['model']}: {result['error']}")
            continue
        if result["translation"] is not None:
            translations.append(
                {
                    "model": result["model"],
                    "translation": result["translation"],
                    "verified": None,
                }
            )

    verification_inputs = [t["translation"] for t in translations]
    unique_inputs = list(dict.fromkeys(verification_inputs))
    verified_unique = await asyncio.gather(
        *[
            verify_translation(
                submission["source_text"],
                translation,
                submission["verification_rules"],
                source_media,
                verification_model,
            )
            for translation in unique_inputs
        ]
    )
    translation_to_verified = dict(zip(unique_inputs, verified_unique))

    for entry in translations:
        entry["verified"] = translation_to_verified[entry["translation"]]

    submission["translations"] = translations
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
    verification_model: str = "openrouter",
) -> list[dict]:
    keys = load_keys(KEYS_PATH)
    load_keys_to_env(keys)
    submissions = load_data(data_in)
    selected_models = load_selected_models(submissions)

    if prompt_key not in PROMPTS:
        raise ValueError(f"Unknown prompt key: {prompt_key}")
    if not keys.get("OPENAI_API_KEY"):
        raise ValueError(f"OPENAI_API_KEY is missing from {KEYS_PATH}")
    client = OpenAI(api_key=keys["OPENAI_API_KEY"])
    loop = asyncio.new_event_loop() if fill_api_translations else None

    try:
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
                if loop is None:
                    raise RuntimeError("Missing event loop for API translations")
                transplanted = loop.run_until_complete(
                    fill_translations_async(
                        transplanted, verification_model, selected_models
                    )
                )
            transplanted = add_pass_flags(transplanted)
            if not is_valid_submission(transplanted):
                print(f"Invalid transplanted submission for id={sub.get('id')}")
            out.append(transplanted)
            if limit and len(out) >= limit:
                break
    finally:
        if loop is not None:
            loop.close()

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
        fill_api_translations=args.fill_api_translations,
        verification_model=args.verification_model,
    )
    print(path)


if __name__ == "__main__":
    main()

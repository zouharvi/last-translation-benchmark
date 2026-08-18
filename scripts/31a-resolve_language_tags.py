# python scripts/31a-resolve_language_tags.py --limit 20
"""Resolve submission language labels with OpenAI file search.

To run pipeline:
- Download the ISO 639-3, ISO 15924, and ISO 3166-1 tables from https://salsa.debian.org/iso-codes-team/iso-codes/-/blob/main/data/. Place in data/language_tags/tables/raw named iso6393.json, iso15924.json, and iso31661.json respectively.
- Put OpenAI API key in config.toml.
- Download submissions.json
- Run the script for the first k languages: python scripts/31a-resolve_language_tags.py --submissions submissions.json --limit 20
- To rerun only on specific entries, remove them from the cache file data/language_tags/model_files/openai_resolution_cache.json and run the script again.
"""

import argparse
import hashlib
import json
import subprocess
import sys
import time
import tomllib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LANGUAGE_TAG_DIR = ROOT / "data" / "language_tags"
TABLE_DIR = LANGUAGE_TAG_DIR / "tables"
RAW_TABLE_DIR = TABLE_DIR / "raw"
SEARCH_DIR = TABLE_DIR / "search"
MODEL_FILES_DIR = TABLE_DIR / "model_files"
STATE_PATH = MODEL_FILES_DIR / "openai_vector_store.json"
RESOLVED_PATH = LANGUAGE_TAG_DIR / "language_to_code.json"
UNRESOLVED_PATH = LANGUAGE_TAG_DIR / "language_to_code_unresolved.json"
CACHE_PATH = MODEL_FILES_DIR / "openai_resolution_cache.json"
CONFIG_PATH = ROOT / "config.toml"
DEFAULT_SUBMISSIONS_PATH = (Path(__file__).parent / "../computed/submissions.json").resolve()
SEARCH_FILES = [
    SEARCH_DIR / "iso6393.txt",
    SEARCH_DIR / "iso15924.txt",
    SEARCH_DIR / "iso31661.txt",
]

SCHEMA = {
    "type": "object",
    "properties": {
        "raw": {"type": "string"},
        "lang_iso6393": {"type": ["string", "null"]},
        "script_iso15924": {"type": ["string", "null"]},
        "region_iso31661": {"type": ["string", "null"]},
        "variant": {"type": ["string", "null"]},
        "resolved": {"type": "boolean"},
        "reason": {"type": ["string", "null"]},
    },
    "required": ["raw", "lang_iso6393", "script_iso15924", "region_iso31661", "variant", "resolved", "reason"],
    "additionalProperties": False,
}

PROMPT = """Resolve this raw language label into the requested schema: {raw_json}

Use file search to consult all three supplied standards as needed:
- lang_iso6393 must be an ISO 639-3 alpha_3 code from the language table.
- script_iso15924 must be an ISO 15924 alpha_4 code from the script table.
- region_iso31661 must be an ISO 3166-1 alpha_2 code from the region table.

Rules:
- Preserve the input exactly in raw.
- Never invent a code.
- Use the most specific lang_iso6393 code available. For example, dialects with their own unambiguous ISO 639-3 code should use it.
- For historical variants, if no specific code is available for that historical variant, set lang_iso6393 to the modern language code and use variant to specify the historical variant.
- Do not assume an unstated region or script for region_iso31661/script_iso15924. Only fill these fields if script or region information is explicitly provided and has a corresponding code. Else, set them to null.
- For a hyperlocal dialect/place not captured exactly by lang_iso6393 or region_iso31661, put the most relevant language in lang_iso6393 and specify the place in variant.
- If a macrolanguage is specified with no further information that is specific enough, set lang_iso6393 to the macrolanguage code and use variant to specify the extra information. Extra information may be place names, dialects, or other details.
- If no language is specified or can be figured out - only writing script, or multiple languages, or not enough information to resolve a language (like "Any language"), set lang_iso6393 to "und".
- Set resolved=false and give a concise reason if the language identity is ambiguous with code und or no defensible language code can be grounded. No reason required is resolved=true.
- Every non-null code must appear verbatim in the corresponding supplied table. Do not invent codes.
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--submissions", type=Path, default=DEFAULT_SUBMISSIONS_PATH)
    parser.add_argument("--model", default="gpt-5.4-mini")
    parser.add_argument("--max-results", type=int, default=20)
    parser.add_argument("--limit", type=int, help="Resolve only the first N labels (for testing).")
    parser.add_argument("--reupload", action="store_true", help="Create a new vector store.")
    parser.add_argument("--restart", action="store_true", help="Ignore cached label resolutions.")
    return parser.parse_args()


def load_openai_key() -> str:
    if not CONFIG_PATH.exists():
        raise FileNotFoundError(f"Key file not found: {CONFIG_PATH}")
    key = tomllib.loads(CONFIG_PATH.read_text(encoding="utf-8")).get("OPENAI")
    if not isinstance(key, str) or not key.strip():
        raise ValueError(f"Set OPENAI in {CONFIG_PATH}")
    return key.strip()


def load_languages(path: Path) -> list[str]:
    submissions = json.loads(path.read_text(encoding="utf-8"))
    labels = {
        value
        for submission in submissions
        for value in (submission.get("source_lang"), submission.get("target_lang"))
        if isinstance(value, str) and value
    }
    return sorted(labels, key=lambda value: (value.casefold(), value))


def ensure_search_files() -> None:
    if all(path.exists() for path in SEARCH_FILES):
        return
    converter = ROOT / "scripts" / "31b-convert_language_tag_tables.py"
    subprocess.run([sys.executable, str(converter)], check=True)


def table_fingerprint() -> str:
    digest = hashlib.sha256()
    for path in SEARCH_FILES:
        digest.update(path.name.encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


def ensure_vector_store(client, reupload: bool) -> str:
    MODEL_FILES_DIR.mkdir(parents=True, exist_ok=True)
    fingerprint = table_fingerprint()
    if not reupload and STATE_PATH.exists():
        state = json.loads(STATE_PATH.read_text(encoding="utf-8"))
        if state.get("fingerprint") == fingerprint and state.get("vector_store_id"):
            print(f"Reusing vector store {state['vector_store_id']}")
            return state["vector_store_id"]

    store = client.vector_stores.create(name="LTB ISO language-tag tables")
    print(f"Created vector store {store.id}")
    for path in SEARCH_FILES:
        with path.open("rb") as source:
            uploaded = client.files.create(file=source, purpose="assistants")
        client.vector_stores.files.create(vector_store_id=store.id, file_id=uploaded.id)
        print(f"Uploaded {path.name} as {uploaded.id}")

    while True:
        files = list(client.vector_stores.files.list(vector_store_id=store.id).data)
        statuses = {item.status for item in files}
        if len(files) == len(SEARCH_FILES) and statuses == {"completed"}:
            break
        failed = [item for item in files if item.status in {"failed", "cancelled"}]
        if failed:
            raise RuntimeError(f"Vector-store ingestion failed: {failed}")
        print(f"Waiting for vector-store ingestion: {sorted(statuses)}")
        time.sleep(2)

    STATE_PATH.write_text(
        json.dumps({"vector_store_id": store.id, "fingerprint": fingerprint}, indent=2) + "\n",
        encoding="utf-8",
    )
    return store.id


def load_valid_codes() -> tuple[set[str], set[str], set[str]]:
    languages = json.loads((RAW_TABLE_DIR / "iso6393.json").read_text(encoding="utf-8"))["639-3"]
    scripts = json.loads((RAW_TABLE_DIR / "iso15924.json").read_text(encoding="utf-8"))["15924"]
    regions = json.loads((RAW_TABLE_DIR / "iso31661.json").read_text(encoding="utf-8"))["3166-1"]
    return (
        {row["alpha_3"] for row in languages},
        {row["alpha_4"] for row in scripts},
        {row["alpha_2"] for row in regions},
    )


def validate(result: dict, raw: str, valid_codes: tuple[set[str], set[str], set[str]]) -> dict:
    if not isinstance(result, dict):
        result = {"resolved": False, "reason": "model output was not a JSON object"}
    errors = []
    if result.get("raw") != raw:
        errors.append("model did not preserve raw label")
    code_fields = ("lang_iso6393", "script_iso15924", "region_iso31661")
    for field, allowed in zip(code_fields, valid_codes, strict=True):
        code = result.get(field)
        if code is not None and code not in allowed:
            errors.append(f"invalid {field} code {code!r}")
    if result.get("resolved") and result.get("lang_iso6393") is None:
        errors.append("resolved result has no language code")
    if result.get("resolved") and result.get("lang_iso6393") == "und":
        errors.append("und language code must be unresolved")
    if errors:
        result["resolved"] = False
        result["reason"] = "; ".join(errors)
    result["raw"] = raw
    return result


def resolve_one(client, model: str, vector_store_id: str, raw: str, max_results: int) -> dict:
    response = client.responses.create(
        model=model,
        input=PROMPT.format(raw_json=json.dumps(raw, ensure_ascii=False)),
        tools=[{
            "type": "file_search",
            "vector_store_ids": [vector_store_id],
            "max_num_results": max_results,
        }],
        tool_choice="required",
        text={
            "format": {
                "type": "json_schema",
                "name": "language_tag_resolution",
                "strict": True,
                "schema": SCHEMA,
            }
        },
    )
    return json.loads(response.output_text)


def write_outputs(results: list[dict]) -> None:
    fields = ("lang_iso6393", "script_iso15924", "region_iso31661", "variant")
    resolved = {
        item["raw"]: {key: item.get(key) for key in fields}
        for item in results
        if item["resolved"]
    }
    unresolved = {
        item["raw"]: {**{key: item.get(key) for key in fields}, "reason": item.get("reason")}
        for item in results
        if not item["resolved"]
    }
    RESOLVED_PATH.write_text(json.dumps(resolved, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    UNRESOLVED_PATH.write_text(json.dumps(unresolved, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {len(resolved)} resolved labels to {RESOLVED_PATH}")
    print(f"Wrote {len(unresolved)} unresolved labels to {UNRESOLVED_PATH}")


def write_cache(cache: dict[str, dict]) -> None:
    CACHE_PATH.write_text(json.dumps(cache, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    from openai import OpenAI
    
    args = parse_args()

    ensure_search_files()
    labels = load_languages(args.submissions)
    if args.limit is not None:
        labels = labels[:args.limit]
    print(f"Resolving {len(labels)} distinct language labels")

    client = OpenAI(api_key=load_openai_key())
    vector_store_id = ensure_vector_store(client, args.reupload)
    valid_codes = load_valid_codes()
    cache = {}
    if not args.restart and CACHE_PATH.exists():
        cache = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    results = []
    for index, raw in enumerate(labels, 1):
        print(f"[{index}/{len(labels)}] {raw}", flush=True)
        if raw in cache:
            results.append(validate(cache[raw], raw, valid_codes))
            print("  reused cached resolution")
            continue
        try:
            result = resolve_one(client, args.model, vector_store_id, raw, args.max_results)
        except Exception as exc:
            result = {
                "raw": raw,
                "lang_iso6393": None,
                "script_iso15924": None,
                "region_iso31661": None,
                "variant": None, "resolved": False, "reason": f"API error: {exc}",
            }
            results.append(validate(result, raw, valid_codes))
            write_outputs(results)
            continue
        result = validate(result, raw, valid_codes)
        cache[raw] = result
        write_cache(cache)
        results.append(result)
        write_outputs(results)
    write_outputs(results)


if __name__ == "__main__":
    main()

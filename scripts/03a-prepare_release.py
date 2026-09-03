# %%

import collections
import json
import os
import re
import statistics

import fastchrf
import numpy as np

from utils import submission_is_before_2026_09_01

os.chdir(os.path.dirname(__file__)+"/..")

from last_translation_benchmark.utils import (
    save_compact_json,
    simple_lang,
)

with open("data/submissions.json", "r") as f:
    submissions_all = json.load(f)


with open("data/lang2iso.json", "r") as f:
    lang2iso = json.load(f)


def _models_are_bad(sub):
    subs = [x for x in sub["translations"] if x["model"] != "human"]
    verified = [
        # pass if at least one verifier is satisfied
        any(all(vl) for vl in mt_obj.get("verified_extra", {}).values() if all(v is not None for v in vl))
        for mt_obj in subs
    ]
    # passing at most half of the models
    return statistics.mean(verified) <= 0.5

def _human_is_ok(sub):
    obj = next((x for x in sub["translations"] if x["model"] == "human"), None)
    # we should always have human
    if obj is None:
        return False

    verified = obj.get("verified_extra", {})
    verified = [all(vl) for vl in verified.values() if all(v is not None for v in vl)]
    if not verified:
        return False
    return statistics.mean(verified) >= 0.75

submissions_accepted = [
    s for s in submissions_all
    # take accepted examples before September 1, 2026
    if s["status"] == "accept" and submission_is_before_2026_09_01(s)
]

for submission in submissions_accepted:
    submission["translations"] = [
        t for t in submission["translations"]
        if not t["model"].startswith("SKIP: ")
        and not t["model"].startswith("PRIVILEGE-")
    ]

submissions_maybe_eval = [
    sub for sub in submissions_accepted
    if _models_are_bad(sub) and _human_is_ok(sub) and sub["source_media"] is None and sub["source_instructions"] is None
]

langs_to_examples = collections.defaultdict(list)
for submission in submissions_maybe_eval:
    lang1_simple = simple_lang(submission["source_lang"])
    lang2_simple = simple_lang(submission["target_lang"])
    langs_to_examples[(lang1_simple, lang2_simple)].append(submission)

def translation_similarity(translations: list[dict]) -> float:
    translations = [t["translation"] for t in translations]
    translations = [t for t in translations if t is not None]
    return np.average(fastchrf.pairwise_chrf([translations], [translations])) # type: ignore

def translation_easiness(translations: list[dict]) -> float:
    verified = [all(t.get("verified_extra", {}).get("Gemini 3.1 Pro", [True])) for t in translations]
    return statistics.mean(verified) if verified else 1.0

ltbv1eval_ids = {
    sub["id"]
    for examples in langs_to_examples.values()
    if len(examples) >= 10
    for sub in sorted(
        examples,
        # prioritize difficult-enough examples
        # then later select by diversity https://aclanthology.org/2025.tacl-1.80/
        key=lambda s: (translation_easiness(s["translations"]), translation_similarity(s["translations"])),
        reverse=False
    )[:20]
}

def get_language_iso(lang_name: str) -> str | None:
    return (
        lang2iso.get(lang_name)
        or lang2iso.get(lang_name.split("(")[0].strip())
        or lang2iso.get(lang_name.split(",")[0].strip())
        or lang2iso.get(lang_name.split("(")[0].split(",")[0])
    )

ATTRIBUTION_COMMENT_RE = re.compile(
    r"(?i)"  # Ignore casing
    r"^(?:"
    r"(https?://[^\s\"]+)|"  # Case 1: If whole comment is a URL
    r"(?:(?:attribute|attribution|credit|(?:text )?source)\b[^:/\n]*[:/]"  # Case 2: Attribute/Credit/Source…
    r"|found from|from the book|quoted in|(?:image|sentence)(?: is)? taken from)\s*"  # Case 3: Other phrases
    r"(?:.*?(https?://[^\s\"]+)|(.*))"
    r")"
)

def get_attribute_from_comments(comments: list[dict]) -> str | None:
    attribution_texts = []
    for comment in comments:
        text = comment.get("text", "").strip()
        match = ATTRIBUTION_COMMENT_RE.match(text)
        if match:
            extracted = match.group(1) or match.group(2) or match.group(3)
            extracted = (extracted or "").replace("Target translation is my own.", "").strip(" \n.\\:")
            if extracted:
                attribution_texts.append(extracted)
    return "\n".join(attribution_texts) if attribution_texts else None

submissions_v1: list[dict] = []
subset_sizes = collections.Counter()

# reset all tags
for submission in submissions_all:
    submission["tags"] = []

for submission in submissions_accepted:
    tags = (
        ["LTBv1"]
        + (["LTBv1-eval"] if submission["id"] in ltbv1eval_ids else [])
    )
    submission_new = {
        "id": submission["id"],
        "source_text": submission["source_text"],
        "source_lang": submission["source_lang"],
        "target_lang": submission["target_lang"],
        "source_lang_iso": get_language_iso(submission["source_lang"]),
        "target_lang_iso": get_language_iso(submission["target_lang"]),
        "source_instructions": submission["source_instructions"],
        "source_media": submission["source_media"],
        "attribution": get_attribute_from_comments(submission["comments"]),
        "translations": [
            {
                "model": mt_obj["model"],
                "translation": mt_obj["translation"],
                "verified": mt_obj.get("verified_extra", {}).get("Gemini 3.1 Pro"),
            }
            for mt_obj in submission["translations"]
        ],
        "verification_rules": submission["verification_rules"],
        "linguistics": [
            tag for k, subl in submission.get("linguistics", {}).items() if k != "observations" for tag in subl
        ],
        "tags": tags,
    }
    subset_sizes.update(submission_new["tags"])
    submissions_v1.append(submission_new)

print("Subset sizes:", subset_sizes)
save_compact_json(submissions_v1, "data/v1.json")
# save_compact_json(submissions_all, "data/submissions.json")


# make sure that all these examples are present in the final v1.json
for id in [96, 3703, 322, 18, 689, 1239, 4391, 2234, 3497, 3184, 478, 212, 400, 582, 336, 83, 2690, 1261, 4254, 314, 2484, 152]:
    assert any(sub["id"] == id for sub in submissions_v1), f"Missing example with id {id} in v1.json"

gemini_passrate = []
human_passrate = []
for sub_obj in submissions_accepted:
    if sub_obj["id"] not in ltbv1eval_ids:
        continue
    for mt_obj in sub_obj["translations"]:
        if mt_obj["model"] == "Gemini 3.1 Pro":
            verified = mt_obj.get("verified_extra", {}).get("Gemini 3.1 Pro")
            if verified is not None:
                gemini_passrate.append(all(verified))
        if mt_obj["model"] == "human":
            verified = mt_obj.get("verified_extra", {}).get("Gemini 3.1 Pro")
            if verified is not None:
                human_passrate.append(all(verified))
print(f"LTBv1-eval | Gemini 3.1 Pro: {statistics.mean(gemini_passrate):.2%}")
print(f"LTBv1-eval | human:          {statistics.mean(human_passrate):.2%}")

"""
scp data/v1.json ltb:/home/zouhar/last-translation-benchmark/data/
hf upload zouhar/last-translation-benchmark data/v1.json data/v1.json --repo-type dataset
"""
# %%

import datetime
import json
import os
import collections
import fastchrf
import statistics
import numpy as np

os.chdir(os.path.dirname(__file__)+"/..")

from last_translation_benchmark.utils import save_compact_json, simple_lang

with open("data/submissions.json", "r") as f:
    submissions = json.load(f)


with open("data/lang2iso.json", "r") as f:
    lang2iso = json.load(f)


def _models_are_bad(sub):
    # passing at most half of the models
    # pass if at least one verifier is satisfied
    subs = [x for x in sub["translations"] if x["model"] != "human"]
    verified = [
        any(all(vl) for vl in mt_obj.get("verified_extra", {}).values() if all(v is not None for v in vl))
        for mt_obj in subs
    ]
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


submissions = [
    s for s in submissions
    # take accepted examples before September 1, 2026
    if s["status"] == "accept"
    and datetime.datetime.strptime(s["created_at"].split(" ")[0], "%Y-%m-%d").astimezone(datetime.UTC) < datetime.datetime(2026, 9, 1, tzinfo=datetime.UTC)
    and _models_are_bad(s) and _human_is_ok(s)
]

for submission in submissions:
    submission["translations"] = [
        t for t in submission["translations"]
        if not t["model"].startswith("SKIP: ")
        and not t["model"].startswith("PRIVILEGE-")
    ]

langs_to_examples = collections.defaultdict(list)
for submission in submissions:
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

ltb_v1_micro_ids = {
    submission["id"]
    for examples in langs_to_examples.values()
    if len(examples) >= 20
    for submission in sorted(
        examples,
        # prioritize difficult-enough examples
        # then later select by diversity https://aclanthology.org/2025.tacl-1.80/
        key=lambda s: (translation_easiness(s["translations"]) >= 0.15, translation_similarity(s["translations"])),
        reverse=False
    )[:5]
}

def get_language_iso(lang_name: str) -> str | None:
    return (
        lang2iso.get(lang_name)
        or lang2iso.get(lang_name.split("(")[0].strip())
        or lang2iso.get(lang_name.split(",")[0].strip())
        or lang2iso.get(lang_name.split("(")[0].split(",")[0])
    )

submissions_new: list[dict] = []
subset_sizes = collections.Counter()
for submission in submissions:
    submission_new = {
        "id": submission["id"],
        "source_text": submission["source_text"],
        "source_lang": submission["source_lang"],
        "target_lang": submission["target_lang"],
        "source_lang_iso": get_language_iso(submission["source_lang"]),
        "target_lang_iso": get_language_iso(submission["target_lang"]),
        "source_instructions": submission["source_instructions"],
        "source_media": submission["source_media"],
        "translations": [
            {
                "model": mt_obj["model"],
                "translation": mt_obj["translation"],
                "eval_verifier": mt_obj.get("verified_extra", {}).get("Gemini 3.1 Pro"),
            }
            for mt_obj in submission["translations"]
        ],
        "verification_rules": submission["verification_rules"],
        "created_at": submission["created_at"],
        "linguistics": submission.get("linguistics", {}),
        "tags": (
            ["LTBv1"]
            + (["LTBv1-text"] if submission["source_media"] is None and submission["source_instructions"] is None else [])
            + (["LTBv1-micro"] if submission["id"] in ltb_v1_micro_ids else [])
        ),
    }
    subset_sizes.update(submission_new["tags"])
    submission_new["linguistics"].pop("observations", None)
    submissions_new.append(submission_new)

print("Subset sizes:", subset_sizes)
save_compact_json(submissions_new, "data/v1.json")

gemini_passrate = []
for sub_obj in submissions:
    if sub_obj["id"] not in ltb_v1_micro_ids:
        continue
    for mt_obj in sub_obj["translations"]:
        if mt_obj["model"] == "Gemini 3.1 Pro":
            verified = mt_obj.get("verified_extra", {}).get("Gemini 3.1 Pro")
            if verified is not None:
                gemini_passrate.append(all(verified))
print(f"Gemini 3.1 Pro pass rate: {statistics.mean(gemini_passrate):.2%}")

"""
scp data/v1.json ltb:/home/zouhar/last-translation-benchmark/data/
"""
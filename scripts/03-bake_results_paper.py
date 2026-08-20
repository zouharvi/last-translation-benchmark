# %%

import collections
import itertools
import json
import math
import os
import random
import statistics
from datetime import datetime

import matplotlib.pyplot as plt
import numpy as np
import scipy.stats
from lingtypology import glottolog

os.chdir(os.path.dirname(os.path.abspath(__file__))+ "/../")

os.makedirs("computed/", exist_ok=True)

AUTHORSHIP_POINTS_MIN = 10

print("Loading data")

with open("data/users.json", "r") as f:
    data_users = json.load(f)

with open("data/submissions.json", "r") as f:
    data_submissions = json.load(f)

data_out = {}

user_count = collections.defaultdict(set)
user_count["registered"] = {x["username"] for x in data_users}
user_count["submitted"] = {x["username"] for x in data_submissions}
user_count["accepted"] = {x["username"] for x in data_submissions if x["status"] == "accept"}
user_count["reviewers"] = {x["reviewed_by"] for x in data_submissions if x["reviewed_by"] is not None}
user_count["admins"] = {x["username"] for x in data_users if "admin" in x["roles"]}
data_out["user_count"] = {k: len(v) for k, v in user_count.items()}

print("Processing language data")

# language distribution
language_count = collections.Counter()
language_count_simple = collections.Counter()
language_count_pairs = collections.Counter()
for submission in data_submissions:
    if submission["status"] != "accept":
        continue
    lang1, lang2 = submission["source_lang"].strip(), submission["target_lang"].strip()
    lang1_simple, lang2_simple = lang1.split("(")[0].strip(), lang2.split("(")[0].strip()
    language_count_pairs[lang1_simple + " - " + lang2_simple] += 1
    language_count[lang1_simple] += 1
    language_count[lang2_simple] += 1

    language_count_simple[lang1_simple] += 1
    language_count_simple[lang2_simple] += 1

# download classification into resourcedness
enum2resourcedness = {
    '5': 'Ultra-High',
    '4': 'High',
    '3': 'Medium',
    '2': 'Low',
    '1': 'Minimal',
    '0': 'Zero',
}
if not os.path.exists("data/lang2resourcedness.json"):
    import requests
    r = requests.get("https://microsoft.github.io/linguisticdiversity/assets/lang2tax.txt")
    lang2resourcedness = {}
    for line in r.text.splitlines():
        lang, resourcedness = line.strip().split(",")
        lang2resourcedness[lang] = enum2resourcedness[resourcedness]
    with open("data/lang2resourcedness.json", "w") as f:
        json.dump(lang2resourcedness, f, indent=2, ensure_ascii=False)

with open("data/lang2resourcedness.json", "r") as f:
    lang2resourcedness = json.load(f)

language_family = collections.Counter()
language_resourcedness = collections.Counter({
    resourcedness: 0 for resourcedness in enum2resourcedness.values()
})
for lang_simple, count in language_count_simple.items():
    if lang_simple == "English":
        continue

    if lang_simple == "Farsi":
        lang_simple = "Persian"

    if lang_simple.lower() in lang2resourcedness:
        language_resourcedness[lang2resourcedness[lang_simple.lower()]] += count

    if lang_simple == "Persian":
        lang_simple = "Western Farsi"
    elif lang_simple == "Chinese":
        lang_simple = "Mandarin Chinese"
    elif lang_simple == "Hebrew":
        lang_simple = "Modern Hebrew"
    elif "Arabic" in lang_simple:
        lang_simple = "Arabic"
    elif "Czech" in lang_simple:
        lang_simple = "Czech"
    
    lang_families = glottolog.get_affiliations([lang_simple])[0].split(",")[0]
    if lang_families:
        language_family[lang_families] += count
    else:
        language_family["Other"] += count

other_language_family = language_family.pop("Other", 0)
for lang, count in language_family.most_common()[4:]:
    other_language_family += count
    del language_family[lang]
language_family["Other"] = other_language_family
data_out["language_family"] = {
    family: count/language_family.total()
    for family, count in language_family.most_common()
}
data_out["language_resourcedness"] = {
    resourcedness: count/language_count_simple.total()
    for resourcedness, count in language_resourcedness.items()
}
data_out["language_count"] = dict(language_count.most_common())
data_out["language_count_simple"] = dict(language_count_simple.most_common())
data_out["language_count_simple_pairs"] = dict(language_count_pairs.most_common())

print("Processing contributions visualization")
# progress over time figure
def date_to_delta(date_str):
    # subtract fom 2026-05-01
    # 2026-05-26 23:23
    # remove micros?
    if date_str.count(":") == 2:
        date_str = date_str.rsplit(":", 1)[0]
    date_obj = datetime.strptime(date_str, "%Y-%m-%d %H:%M")
    delta = date_obj - datetime(2026, 5, 1)
    return delta.days

# number of accepted, rejected, pending submissions
status_count = collections.Counter()
delta_today = date_to_delta(datetime.now().strftime("%Y-%m-%d %H:%M"))
dates_pending = [0]*(delta_today+1)
dates_accepted = [0]*(delta_today+1)
dates_returned = [0]*(delta_today+1)
for submission in data_submissions:
    status_count[submission["status"]] += 1
    dates = [submission["created_at"]] + [x["created_at"] for x in submission["comments"]]
    delta_first = date_to_delta(min(dates))
    delta_last = date_to_delta(max(dates))

    if submission["status"] == "accept":
        for i in range(delta_last+1, delta_today+1): 
            dates_accepted[i] += 1
        for i in range(delta_first, delta_last):
            dates_pending[i] += 1
    elif submission["status"] == "return":
        for i in range(delta_first, delta_last+1):
            dates_pending[i] += 1
        for i in range(delta_last, delta_today+1):
            dates_returned[i] += 1
    elif submission["status"] == "pending":
        for i in range(delta_first, delta_today+1):
            dates_pending[i] += 1

dates_accepted = np.array(dates_accepted)
dates_pending = np.array(dates_pending)
dates_returned = np.array(dates_returned)

plt.figure(figsize=(4, 2.5))
plt.plot(range(delta_today+1), dates_accepted, color="green", linewidth=2)
plt.plot(range(delta_today+1), dates_pending, color="orange", linewidth=2)
plt.plot(range(delta_today+1), dates_returned, color="red", linewidth=2)
plt.plot(range(delta_today+1), dates_accepted+dates_pending+dates_returned, color="black", linewidth=2)
plt.ylabel("Number of submissions")
plt.xlabel("Days since 2026-05-01")
plt.text(
    x=delta_today,
    y=dates_accepted[-1],
    s=f" Accepted: {status_count['accept']}",
    ha="left", va="center"
)
plt.text(
    x=delta_today,
    y=dates_pending[-1],
    s=f" Pending: {status_count['pending']}",
    ha="left", va="center",
)
plt.text(
    x=delta_today,
    y=dates_returned[-1],
    s=f" Returned: {status_count['return']}",
    ha="left", va="center",
)
plt.text(
    x=delta_today,
    y=dates_accepted[-1]+dates_pending[-1]+dates_returned[-1],
    s=f" Total: {len(data_submissions)}",
    ha="left", va="center",
)

plt.gca().spines[["top", "right"]].set_visible(False)
plt.tight_layout(pad=0.5)
plt.gca().patch.set_alpha(0)
plt.gcf().patch.set_alpha(0)
plt.savefig("computed/collection_progress.svg")


data_out["status_count"] = dict(status_count.most_common())
data_out["quota_per_submission"] = sum(x["quota_used"] for x in data_users if x["quota_used"]) / len(data_submissions)
data_out["proportion_multimodal"] = statistics.mean([x["source_media"] is not None for x in data_submissions if x["status"] == "accept"])
data_out["proportion_instructions"] = statistics.mean([x["source_instructions"] is not None for x in data_submissions if x["status"] == "accept"])
data_out["source_text_chars"] = statistics.mean([len(x["source_text"]) for x in data_submissions if x["status"] == "accept" and "English" in x["source_lang"]])
data_out["source_text_words"] = statistics.mean([len(x["source_text"].split()) for x in data_submissions if x["status"] == "accept" and "English" in x["source_lang"]])
data_out["verification_rules"] = statistics.mean([len(x["verification_rules"]) for x in data_submissions if x["status"] == "accept"])


WHITELIST_LLM = {
    "interactive",
    "Qwen 3.7 Flash",
    "Qwen 3.7 Plus",
    "Gemma 4",
    "Gemini 3.1 Pro",
    "Gemini 3.5 Flash Lite",
    "GPT-5.4 Mini",
}

WHITELIST_MT = {
    "human",
    "Gemma 4",
    "Gemini 2.5 Flash",
    "Llama 4 Maverick", 
    "GPT-5.4 Mini",
    "GPT-5.6 Sol",
    "GPT-5.6 Luna",
    "GPT-5.6 Terra",
    "Claude Haiku 4.5",
    "Claude Sonnet 4.5",
    "Command A", 
    "Command A+",
    "Qwen 3.7 Plus",
    "Gemini 3.1 Pro",
    "Gemini 3.5 Flash Lite",
    "Qwen 3.7 Flash",
    "gpt-oss-20b",
    "Kimi K3",
    "Google Translate",
    "Lara",
    "Nemotron 3 Ultra",
    "Deepseek V4 Pro",
    "TranslateGemma",
    "Tower+",
    "GemmaX2-28-9B",
    "HY-MT2",
    "Seed-X-PPO-7B",
    "NLLB 3.3B",
    "Command A Translate",
    "TinyAya Global",
    "PRIVILEGE-ALL: Gemma 4",
    "PRIVILEGE-ALL: Gemini 3.5 Flash Lite",
    "PRIVILEGE-ALL: GPT-5.4 Mini",
}

print("Processing model results")

# compute per model results
data_models = collections.defaultdict(lambda: collections.defaultdict(list))
data_models_selfbias = collections.defaultdict(lambda: {"llm": [], "verifier": []})
with open("computed/autometrics_cache.json", "r") as f:
    data_autometrics_cache = json.load(f)

data_submissions_accepted = [x for x in data_submissions if x["status"] == "accept"]
data_submissions_textonly = [
    x for x in data_submissions_accepted
    if x["source_media"] is None and x["source_instructions"] is None
]
data_submissions_v1 = [
    x for x in data_submissions_textonly
    # passing at most half of the models
    # pass if at least one verifier is satisfied
    if statistics.mean(
        any(all(vl) for vl in mt_obj.get("verified_extra", {}).values() if all(v is not None for v in vl))
        for mt_obj in x["translations"]
        if mt_obj["model"] != "human"
    ) <= 0.5
]
print("- Original:", len(data_submissions))
print("- Accepted:", len(data_submissions_accepted))
print("- Accepted, text-only:", len(data_submissions_textonly))
print("- v1:", len(data_submissions_v1))

for submission in data_submissions_v1:
    human_translation = next(x for x in submission["translations"] if x["model"] == "human")["translation"]

    model_ranking_verifier = collections.defaultdict(dict)
    model_ranking_llm = collections.defaultdict(dict)
    for entry in submission["translations"]:
        autometrics_key = f"{submission['source_lang']}_#_{submission['target_lang']}_#_{submission['source_text']}_#_{entry['translation']}_#_{human_translation}"
        if autometrics_key in data_autometrics_cache:
            for metric, score in data_autometrics_cache[autometrics_key].items():
                if score is not None:
                    data_models[entry["model"]]["AUTOMETRIC: " + metric].append(score)
        for verifier, results in entry.get("verified_extra", {}).items():
            if all(x is not None for x in results):
                data_models[entry["model"]]["VERIFIER: " + verifier].append(all(results))
                model_ranking_verifier[entry["model"]][verifier] = all(results)
        for verifier, result in entry.get("judge_extra", {}).items():
            if result is not None:
                data_models[entry["model"]]["JUDGE: " + verifier].append(result)
                model_ranking_llm[entry["model"]][verifier] = result

    # compute self-bias according to https://arxiv.org/abs/2509.26600
    model_ranking_verifier = {
        k_mt: {k_llm: v for k_llm, v in v.items() if k_llm in WHITELIST_LLM}
        for k_mt, v in model_ranking_verifier.items()
        if k_mt in WHITELIST_MT
    }
    model_ranking_llm = {
        k_mt: {k_llm: v for k_llm, v in v.items() if k_llm in WHITELIST_LLM}
        for k_mt, v in model_ranking_llm.items()
        if k_mt in WHITELIST_MT
    }
    # shuffle dicts to avoid bias in ranking
    model_ranking_verifier = {k: dict(sorted(v.items(), key=lambda _: random.random())) for k, v in model_ranking_verifier.items()}
    model_ranking_llm = {k: dict(sorted(v.items(), key=lambda _: random.random())) for k, v in model_ranking_llm.items()}

    models = model_ranking_verifier.keys() & model_ranking_llm.keys()
    if len(models) >= 2:
        for model in models:
            if model not in model_ranking_verifier or model not in model_ranking_llm:
                continue
            if model not in model_ranking_verifier[model] or model not in model_ranking_llm[model]:
                continue
            if len(model_ranking_verifier[model]) < 2 or len(model_ranking_llm[model]) < 2:
                continue
            if any(not [model_ranking_verifier[m][m2] for m2 in model_ranking_verifier if m2 in model_ranking_verifier[m] if m2 != model] for m in model_ranking_verifier):
                continue
            if any(not [model_ranking_llm[m][m2] for m2 in model_ranking_llm if m2 in model_ranking_llm[m] if m2 != model] for m in model_ranking_llm):
                continue

            ranking_by_all_verifier = {m: statistics.mean([model_ranking_verifier[m][m2] for m2 in model_ranking_verifier if m2 in model_ranking_verifier[m] if m2 != model]) for m in model_ranking_verifier}
            ranking_by_all_verifier = {k: v for k, v in sorted(ranking_by_all_verifier.items(), key=lambda item: item[1], reverse=True)}
            ranking_by_all_verifier = {k: rank for rank, (k, v) in enumerate(ranking_by_all_verifier.items(), start=1)}
            ranking_by_all_llm = {m: statistics.mean([model_ranking_llm[m][m2] for m2 in model_ranking_llm if m2 in model_ranking_llm[m] if m2 != model]) for m in model_ranking_llm}
            ranking_by_all_llm = {k: v for k, v in sorted(ranking_by_all_llm.items(), key=lambda item: item[1], reverse=True)}
            ranking_by_all_llm = {k: rank for rank, (k, v) in enumerate(ranking_by_all_llm.items(), start=1)}

            ranking_by_self_verifier = {m: model_ranking_verifier[m][model] for m in model_ranking_verifier if model in model_ranking_verifier[m]}
            ranking_by_self_verifier = {k: v for k, v in sorted(ranking_by_self_verifier.items(), key=lambda item: item[1], reverse=True)}
            ranking_by_self_verifier = {k: rank for rank, (k, v) in enumerate(ranking_by_self_verifier.items(), start=1)}
            ranking_by_self_llm = {m: model_ranking_llm[m][model] for m in model_ranking_llm if model in model_ranking_llm[m]}
            ranking_by_self_llm = {k: v for k, v in sorted(ranking_by_self_llm.items(), key=lambda item: item[1], reverse=True)}
            ranking_by_self_llm = {k: rank for rank, (k, v) in enumerate(ranking_by_self_llm.items(), start=1)}
            data_models_selfbias[model]["verifier"].append((ranking_by_all_verifier[model] - ranking_by_self_verifier[model])/len(ranking_by_self_verifier))
            data_models_selfbias[model]["llm"].append((ranking_by_all_llm[model] - ranking_by_self_llm[model])/len(ranking_by_self_llm))

data_out["model_selfbias"] = {
    model: {
        "verifier": statistics.mean(results["verifier"]) if results["verifier"] else None,
        "llm": statistics.mean(results["llm"]) if results["llm"] else None,
    }
    for model, results in data_models_selfbias.items()
}



print("Processing human annotations")

with open("data/annotations.json", "r") as f:
    data_annotations_raw = json.load(f)
data_annotations = [
    (item["annotation"][0], item["item"][0])
    for campaign_data in data_annotations_raw.values()
    for item in campaign_data
    if len(item["annotation"]) == 1
]
data_annotations_form = [
    (item["annotation"][1:], item["item"][1:])
    for campaign_data in data_annotations_raw.values()
    for item in campaign_data
    if len(item["annotation"]) > 1
]
for annotation, item in data_annotations:
    for model, results in annotation.items():
        if "considering these rules" in item.get("instructions", ""):
            kind = "with rules"
        else:
            kind = "standalone"
        data_models[model]["HUMAN: " + kind].append(results["score"])   

data_out["rules_annotation"] = {
    "recall": [],
    "precision": [],
}
data_out["rules_annotation_users"] = len({
    item["user_id"]
    for campaign_data in data_annotations_raw.values()
    for item in campaign_data
})
data_out["rules_annotation_languages"] = len({
    item["user_id"].removesuffix("D0").removesuffix("D1")
    for campaign_data in data_annotations_raw.values()
    for item in campaign_data
})
data_out["rules_annotation_submissions"] = len([
    item
    for campaign_data in data_annotations_raw.values()
    for item in campaign_data
])
for annotations, items in data_annotations_form:
    for annotation, item in zip(annotations, items):
        if "would it fail correct translations?" in item["text"]:
            if annotation == "This rule is too strict":
                data_out["rules_annotation"]["recall"].append(0)
            elif annotation == "This rule is realistic and reasonable":
                data_out["rules_annotation"]["recall"].append(1)
            elif annotation == "Not sure":
                pass
            else:
                raise ValueError("Unknown annotation item text: " + item["text"])
        elif "translations that are incorrect but would pass all of these verifications at the same time" in item["text"]:
            if annotation == "These rules are fine as they cover most cases":
                data_out["rules_annotation"]["precision"].append(1)
            elif annotation == "Some incorrect translations might pass through":
                data_out["rules_annotation"]["precision"].append(0)
            elif annotation == "Not sure":
                pass
            else:
                raise ValueError("Unknown annotation item text: " + item["text"])
        else:
            raise ValueError("Unknown annotation item text: " + item["text"])

data_out["rules_annotation"] = {
    k: statistics.mean(v)
    for k, v in data_out["rules_annotation"].items()
}

# average results across metrics
all_metrics = {
    k for results in data_models.values()
    for k in results
    if (not (k.startswith("VERIFIER: ")) and (not k.startswith("JUDGE: "))) or any(k.endswith(k_allowed) for k_allowed in WHITELIST_LLM)
}
data_out["model_results"] = {
    model.replace("human", "Human"): {
        key: results.get(key, [])
        for key in all_metrics
    }
    for model, results in data_models.items()
    if model in WHITELIST_MT
}

print("Processing pairwise correlations and stability")

# pairwise Kendall's tau correlation between metrics (human, autometrics, verifier, judge)
metrics_pairwise_tau = collections.defaultdict(list)
for metric1, metric2 in itertools.product(all_metrics, all_metrics):
    scores1 = []
    scores2 = []
    for model in data_out["model_results"]:
        if data_out["model_results"][model][metric1] and data_out["model_results"][model][metric2]:
            scores1.append(statistics.mean(data_out["model_results"][model][metric1]))
            scores2.append(statistics.mean(data_out["model_results"][model][metric2]))

    tau, p_value = scipy.stats.kendalltau(scores1, scores2)
    kind1 = metric1.split(": ")[0]
    kind2 = metric2.split(": ")[0]
    if kind1 == "HUMAN":
        kind1 = metric1
    if kind2 == "HUMAN":
        kind2 = metric2
    metrics_pairwise_tau[f"{kind1} ||| {kind2}"].append(tau)

# do stability
for metric in all_metrics:
    if metric.startswith("HUMAN: "):
        continue
    scores1_all = [
        data_out["model_results"][model][metric]
        for model in data_out["model_results"]
        if data_out["model_results"][model][metric] is not None and data_out["model_results"][model][metric]
    ]
    scores1 = [
        statistics.mean(scores)
        for scores in scores1_all
    ]
    for _ in range(10):
        scores2 = [
            statistics.mean(random.sample(scores, math.ceil(len(scores)*0.01)))
            for scores in scores1_all
        ]
        tau, p_value = scipy.stats.kendalltau(scores1, scores2)
        metrics_pairwise_tau[f"STABILITY ||| {metric.split(': ')[0]}"].append(tau)
data_out["metrics_pairwise_tau"] = {k: statistics.mean(v) for k, v in metrics_pairwise_tau.items()}

# average scroes

data_out["model_results"] = {
    model: {
        key: statistics.mean(results[key]) if results[key] else None
        for key in all_metrics
    }
    for model, results in data_models.items()
    if model in WHITELIST_MT
}


print("Processing authors")

username_to_name_affiliation = {
    u["username"]: (u["name"], u["affiliation"])
    for u in data_users
    if u["credit_consent"]
}
# add contributors
user_points = {}
for s in data_submissions:
    # check if date is be fore September 1, 2026
    if datetime.strptime(s["created_at"].split(" ")[0], "%Y-%m-%d") >= datetime(2026, 9, 1):
        continue
    # consider pending submissions fine
    if s["status"] not in {"accept", "pending"}:
        continue

    contributor = username_to_name_affiliation.get(s.get("username"), None)
    reviewer = username_to_name_affiliation.get(s.get("reviewed_by"), None)

    if contributor is not None:
        user_points[contributor] = user_points.get(contributor, 0) + 1

    if reviewer is not None:
        user_points[reviewer] = user_points.get(reviewer, 0) + 0.2

# sorting will happen in Typst but we can "pre-sort"
data_out["contributors"] = [
    {"name": k[0], "affiliation": k[1], "points": float(np.round(pts, 1))}
    for k, pts in user_points.items()
    if pts >= AUTHORSHIP_POINTS_MIN
]
data_out["contributors"].sort(key=lambda x: (x["points"], x["name"]), reverse=True)

print("Saving")

with open("computed/baked.json", "w") as f:
    json.dump(data_out, f, indent=2, ensure_ascii=False)

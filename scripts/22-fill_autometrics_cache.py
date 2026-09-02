# %%

import collections
import contextlib
import json
import os
import subprocess

import sacrebleu
import tqdm
from frozendict import frozendict

os.chdir(os.path.dirname(os.path.abspath(__file__))+"/..")

with open("data/submissions.json", "r") as f:
    data_submissions = json.load(f)

data_to_score = set()

for submission in data_submissions:
    if submission["status"] != "accept":
        continue
    if submission["source_media"] is not None or submission["source_instructions"] is not None:
        continue
    translation_reference = next(x for x in submission["translations"] if x["model"] == "human")
    for translation in submission["translations"]:
        if translation["model"].startswith("SKIP: "):
            continue
        data_to_score.add(frozendict({
            "source_lang": submission["source_lang"],
            "target_lang": submission["target_lang"],
            "source_text": submission["source_text"] or "",
            "translation": translation["translation"] or "",
            "reference": translation_reference["translation"] or "",
        }))

data_to_score = list(data_to_score)

if not os.path.exists("computed/autometrics_cache.json"):
    with open("computed/autometrics_cache.json", "w") as f:
        json.dump({}, f)

with open("computed/autometrics_cache.json", "r") as f:
    data_cache = collections.defaultdict(dict)
    data_cache.update(json.load(f))

def submission_to_key(submission, translation):
    return f"{submission['source_lang']}_#_{submission['target_lang']}_#_{submission['source_text']}_#_{translation['translation']}_#_{submission['reference']}"

def filter_unscored(data_to_score, data_cache, metric):
    unscored = []
    for x in data_to_score:
        key = submission_to_key(x, x)
        if key not in data_cache or metric not in data_cache[key]:
            unscored.append(x)
    return unscored

# COMET
for model, name in [("Unbabel/wmt22-cometkiwi-da", "Comet QE 22"), ("Unbabel/wmt22-comet-da", "Comet 22")]:
    data_to_score_local = filter_unscored(data_to_score, data_cache, name)
    print(len(data_to_score_local), "left to score by", name)
    if not data_to_score_local:
        continue
    import comet
    model = comet.load_from_checkpoint(comet.download_model(model))
    data = [
        {
            "src": x["source_text"],
            "mt": x["translation"],
            "ref": x["reference"],
        }
        for x in data_to_score_local
    ]
    scores = model.predict(data, batch_size=8, gpus=1).scores # type: ignore
    for score, x in zip(scores, data_to_score_local):
        data_cache[submission_to_key(x, x)][name] = score

# MetricX 
if os.path.exists(os.path.expanduser("~/bin/metricx")):
    for model, name in [("google/metricx-24-hybrid-large-v2p6", "MetricX 24"), ("google/metricx-24-hybrid-large-v2p6", "MetricX QE 24")]:
        data_to_score_local = filter_unscored(data_to_score, data_cache, name)
        print(len(data_to_score_local), "left to score by", name)
        data_to_score_local = data_to_score_local[:2_000]
        if not data_to_score_local:
            continue
        # temporarily change to bin/metricx
        with contextlib.chdir(os.path.expanduser("~/bin/metricx")):
            with open("input.jsonl", "w") as f:
                for x in data_to_score_local:
                    f.write(json.dumps({
                        "source": x["source_text"],
                        "hypothesis": x["translation"],
                        "reference": "" if "QE" in name else x["reference"],
                    }, ensure_ascii=False)+"\n")
            out = subprocess.run(
                [
                    "python3", "-m", "metricx24.predict",
                    "--tokenizer", "google/mt5-xl",
                    "--model_name_or_path", model,
                    "--max_input_length", "1024", "--batch_size", "1",
                    "--input_file", "./input.jsonl", "--output_file", "./output.jsonl"
                ] + (["--qe"] if "QE" in name else []),
                check=True
            )
            with open("output.jsonl", "r") as f:
                output = [json.loads(line) for line in f]
        for x, line in zip(data_to_score_local, output):
            score = 100*(1-line["prediction"])
            scores = max(0, min(100, score))
            data_cache[submission_to_key(x, x)][name] = score
else:
    print("MetricX not found, skipping MetricX scoring.")


# ChrF
data_to_score_local = filter_unscored(data_to_score, data_cache, "ChrF")
for x in tqdm.tqdm(data_to_score_local):
    chrf = sacrebleu.corpus_chrf(
        [x["translation"]],
        [[x["reference"]]],
    ).score
    data_cache[submission_to_key(x, x)]["ChrF"] = chrf

with open("computed/autometrics_cache.json", "w") as f:
    json.dump(data_cache, f, indent=2, ensure_ascii=False)
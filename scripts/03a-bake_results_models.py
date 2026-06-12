#!/usr/bin/env python3
import collections
import json
import argparse
import statistics
import utils_fig
import matplotlib.pyplot as plt

args = argparse.ArgumentParser()
args.add_argument("--data", default="data/submissions.json")
args = args.parse_args()

with open(args.data, "r") as f:
    data = json.load(f)

model_results = collections.defaultdict(list)
for submission in data:
    for entry in submission["translations"]:
        if entry["verified"] is None:
            continue
        if entry["model"] in {"Google", "perfect", "Gemini 2.5 Flash Lite", "MyMemory"}:
            continue
        model_results[entry["model"]].append(all(entry["verified"]))

model_results = {
    m: statistics.mean(v)
    for m, v in model_results.items()
    if len(v) >= 30
}


# horizontal bars, sort by descending value
model_results = dict(sorted(model_results.items(), key=lambda item: item[1], reverse=True))
plt.figure(figsize=(7, 2.5))
plt.barh(
    list(model_results.keys()),
    list(model_results.values()),
    color="#64748b",
)
# add text percentage at the end of bars
for model, score in model_results.items():
    plt.text(score, model, f'{score*100:.0f}%', va='center', ha="left", fontsize=7)
plt.gca().spines[['right', 'top']].set_visible(False)
plt.gca().xaxis.set_major_formatter(plt.FuncFormatter(lambda x, pos: f'{x*100:.0f}%')) # type: ignore
plt.xlabel("Correct translations\n")
plt.tight_layout(pad=0.2)
plt.gca().set_facecolor("none")
plt.gcf().set_facecolor("none")
plt.savefig("computed/bake_results_model.svg")
plt.show()
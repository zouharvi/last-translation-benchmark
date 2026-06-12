# %%

import collections
import json
import os

os.makedirs("../computed/", exist_ok=True)

with open("../data/users.json", "r") as f:
    data_users = json.load(f)

with open("../data/submissions.json", "r") as f:
    data_submissions = json.load(f)

data_out = {}

user_counts = collections.defaultdict(set)
user_counts["registered"] = set(x["username"] for x in data_users)
user_counts["submitted"] = set(x["username"] for x in data_submissions)
user_counts["accepted"] = set(x["username"] for x in data_submissions if x["status"] == "accept")
user_counts["reviewers"] = set(x["reviewed_by"] for x in data_submissions if x["reviewed_by"] is not None)
user_counts["admins"] = set(x["username"] for x in data_users if "admin" in x["roles"])

data_out["user_counts"] = {k: len(v) for k, v in user_counts.items()}

# language distribution
language_counts = collections.Counter()
for submission in data_submissions:
    language_counts[submission["source_lang"].strip()] += 1
    language_counts[submission["target_lang"].strip()] += 1


data_out["language_counts"] = dict(language_counts.most_common())


# number of accepted, rejected, pending submissions
status_counts = collections.Counter()
for submission in data_submissions:
    status_counts[submission["status"]] += 1

data_out["status_counts"] = dict(status_counts.most_common())

# number of quota_used per all submissions
data_out["quota_per_submission"] = f"{sum(x["quota_used"] for x in data_users if x["quota_used"]) / len(data_submissions):.1f}"

counter_passing = collections.Counter()
for submission in data_submissions:
    # how many systems pass
    if submission["translations"] is None:
        continue
    passing = sum(all(entry["verified"]) for entry in submission["translations"] if entry["verified"] is not None)
    counter_passing[passing-1] += 1

print(counter_passing)
data_out["passing_counts"] = dict(counter_passing.most_common())

with open("../computed/bake_results.json", "w") as f:
    json.dump(data_out, f, indent=2)
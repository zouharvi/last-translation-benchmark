
# %%

import json

POINTS_MIN = 1

with open("../data/users.json", "r") as f:
    users = json.load(f)

with open("../data/submissions.json", "r") as f:
    submissions = json.load(f)

submissions =  [
    x for x in submissions if x["status"] == "accept"
]

user_points = {}
for s in submissions:
    uid = s.get("user_id")
    user_points[uid] = user_points.get(uid, 0) + 1

# Filter authors who have enough points and gave credit consent
authors = []
for u in users:
    pts = user_points.get(u["id"], 0)
    if pts >= POINTS_MIN and u["credit_consent"]:
        authors.append(
            {
                "name": u.get("name") or u["username"],
                "affiliation": u.get("affiliation", ""),
                "points": pts,
            }
        )

# Sort authors by points (desc) then name
authors.sort(key=lambda x: (x["points"], x["name"]), reverse=True)

# Clean export format
authors_export = [
    (a["name"], a["affiliation"]) for a in authors
]
# Remove duplicates. fromkeys is used over set to preserve order.
authors_export = list(dict.fromkeys(authors_export))
authors_export = [{"name": a[0], "affiliation": a[1]} for a in authors_export]

with open("../data/contributors.json", "w") as f:
    json.dump(authors_export, f, indent=2, ensure_ascii=False)
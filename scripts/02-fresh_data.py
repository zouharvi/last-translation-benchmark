# %%

import json
import os
import urllib.parse

import requests

os.chdir(os.path.dirname(os.path.abspath(__file__))+ "/../")

from last_translation_benchmark.utils import get_config

os.makedirs("data/", exist_ok=True)

URL_USERS = "https://last-translation-benchmark.vilda.net/api/admin/download-users"
URL_SUBMISSIONS = "https://last-translation-benchmark.vilda.net/api/admin/download-submissions"
COOKIES = {
    "ltb_user": urllib.parse.quote(get_config("LTB_ADMIN_USER")),
    "ltb_token": urllib.parse.quote(get_config("LTB_ADMIN_TOKEN"))
}

req = requests.get(URL_USERS, cookies=COOKIES)
req.raise_for_status()
with open("data/users.json", "wb") as f:
    f.write(req.content)

req = requests.get(URL_SUBMISSIONS, cookies=COOKIES)
req.raise_for_status()
submissions_new = req.json()

submissions_fname = "data/submissions.json"
submissions_old = json.load(open(submissions_fname)) if os.path.exists(submissions_fname) else []
submissions_id_to_obj = {s["id"]: s for s in submissions_old}

data_count_new = 0
data_count_updated = 0
for sub_obj in submissions_new:
    if sub_obj["id"] not in submissions_id_to_obj:
        if sub_obj["status"] == "accept":
            data_count_new += 1
        submissions_id_to_obj[sub_obj["id"]] = sub_obj
    elif submissions_id_to_obj[sub_obj["id"]]["status"] != "accept":
        if sub_obj["status"] == "accept":
            data_count_updated += 1
        submissions_id_to_obj[sub_obj["id"]] = sub_obj

print("Added", data_count_new)
print("Updated", data_count_updated)

merged = sorted(submissions_id_to_obj.values(), key=lambda x: x["id"])
with open(submissions_fname, "w") as f:
    json.dump(merged, f, indent=2, ensure_ascii=False)
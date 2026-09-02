# %%

import collections
import json
import os
import urllib.parse

import requests

os.chdir(os.path.dirname(os.path.abspath(__file__))+ "/../")

from last_translation_benchmark.utils import get_config, save_compact_json

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
if os.path.exists(submissions_fname):
    with open(submissions_fname, "r") as f:
        submissions_old = json.load(f)
else:
    submissions_old = []
submissions_id_to_obj = {s["id"]: s for s in submissions_old}

def is_same(sub_obj_old, sub_obj_new):
    return (
        sub_obj_old["status"] == sub_obj_new["status"]
        and sub_obj_old["source_text"] == sub_obj_new["source_text"]
        and sub_obj_old["source_media"] == sub_obj_new["source_media"]
        and sub_obj_old["source_instructions"] == sub_obj_new["source_instructions"]
        and sub_obj_old["source_lang"] == sub_obj_new["source_lang"]
        and sub_obj_old["target_lang"] == sub_obj_new["target_lang"]
        and sub_obj_old["verification_rules"] == sub_obj_new["verification_rules"]
        and (
            next(mt_obj["translation"] for mt_obj in sub_obj_old["translations"] if mt_obj["model"] == "human")
            == next(mt_obj["translation"] for mt_obj in sub_obj_new["translations"] if mt_obj["model"] == "human")
        )
    )

count_new_accepted = 0
count_new_other = 0
count_old_other_accept = 0
count_old_other_other = 0
count_old_accept_other = 0
count_old_accept_accept = 0
count_noop_accept_accept = 0
count_noop_other_other = 0
count_drop = 0
for sub_obj_new in submissions_new:
    if sub_obj_new["id"] not in submissions_id_to_obj:
        # we are adding previously unseen example, proceed
        if sub_obj_new["status"] == "accept":
            count_new_accepted += 1
        else:
            count_new_other += 1

        submissions_id_to_obj[sub_obj_new["id"]] = sub_obj_new
    else:
        sub_obj_old = submissions_id_to_obj[sub_obj_new["id"]]
        # our example already exists, depends on the status
        if sub_obj_old["status"] == "accept" and sub_obj_new["status"] == "accept":
            # both are accepted, check if sources match
            if is_same(sub_obj_old, sub_obj_new):
                count_noop_accept_accept += 1
            else:
                # uh-oh,something changed! overwrite
                count_old_accept_accept += 1
                submissions_id_to_obj[sub_obj_new["id"]] = sub_obj_new
        elif sub_obj_old["status"] == "accept" and sub_obj_new["status"] != "accept":
            # old is accepted, new is not accepted, overwrite
            count_old_accept_other += 1
            submissions_id_to_obj[sub_obj_new["id"]] = sub_obj_new
        elif sub_obj_old["status"] != "accept" and sub_obj_new["status"] == "accept":
            # old is not accepted, new is accepted, overwrite
            count_old_other_accept += 1
            submissions_id_to_obj[sub_obj_new["id"]] = sub_obj_new
        elif sub_obj_old["status"] != "accept" and sub_obj_new["status"] != "accept":
            # old is not accepted, new is not accepted, overwrite
            if is_same(sub_obj_old, sub_obj_new):
                count_noop_other_other += 1
            else:
                count_old_other_other += 1
                submissions_id_to_obj[sub_obj_new["id"]] = sub_obj_new

# look at which ones aren't in submissions_new
submissions_new_ids = {s["id"] for s in submissions_new}
for sub_obj in list(submissions_id_to_obj.values()):
    if sub_obj["id"] not in submissions_new_ids:
        # this submission is no longer present in the new data, drop it
        count_drop += 1
        del submissions_id_to_obj[sub_obj["id"]]

print("Added new with accepted", count_new_accepted)
print("Added new with other   ", count_new_other)
print("Updated old from accept to other", count_old_accept_other)
print("Updated old from accept to accept", count_old_accept_accept)
print("Updated old from other to accepted", count_old_other_accept)
print("Updated old from other to other", count_old_other_other)
print("Dropped", count_drop)
print("Nothing changed accept-accept", count_noop_accept_accept)
print("Nothing changed other-other", count_noop_other_other)

print("\nBefore:", collections.Counter([s["status"] for s in submissions_old]))
print("After:", collections.Counter([s["status"] for s in submissions_id_to_obj.values()]))

merged = sorted(submissions_id_to_obj.values(), key=lambda x: x["id"])
save_compact_json(merged, submissions_fname)
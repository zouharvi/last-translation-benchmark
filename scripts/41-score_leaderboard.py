import argparse
import asyncio
import json
import os
import sqlite3
import statistics
import urllib.parse

import tqdm
import utils

os.chdir(os.path.dirname(os.path.abspath(__file__))+"/..")
from last_translation_benchmark.utils import get_config, get_prompt_verify

args = argparse.ArgumentParser()
args.add_argument("uid", type=int, help="Leaderboard entry ID to score")
args.add_argument("--chunks", type=int, default=20, help="Number of concurrent submissions to process")
args = args.parse_args()
CHUNK_SIZE = args.chunks

db = sqlite3.connect(get_config("DB_PATH"))
lb_entry = db.execute("SELECT submissions, info FROM leaderboard WHERE id = ?", (args.uid,)).fetchone()
if not lb_entry:
    raise ValueError(f"Leaderboard entry with ID {args.uid} not found.")

lb_subs, lb_info = json.loads(lb_entry[0]), json.loads(lb_entry[1])
with open("data/v1.json") as f:
    id_to_submission = {x["id"]: x for x in json.load(f)}

COOKIES = {
    "ltb_user": urllib.parse.quote(get_config("LTB_SCORER_USER")),
    "ltb_token": urllib.parse.quote(get_config("LTB_SCORER_TOKEN")),
}

async def main():
    async def process_sub(sub_obj_lb):
        sub_obj = id_to_submission.get(sub_obj_lb["id"])

        if not sub_obj or sub_obj_lb["translation"] is None:
            sub_obj_lb["verification"] = None
            return

        # process only LTBv1-eval
        if "LTBv1-eval" not in sub_obj["tags"]:
            return

        # empty translations count as "attempts"
        if sub_obj_lb["translation"] == "":
            sub_obj_lb["verification"] = [False]*len(sub_obj["verification_rules"])
            return

        rule_results = []
        for rule in sub_obj["verification_rules"]:
            prompt = get_prompt_verify(sub_obj["source_text"], sub_obj_lb["translation"], rule, sub_obj["source_media"])
            payload = {"model": "google/gemini-3.1-pro-preview", "prompt": prompt, "cache": True}
            if sub_obj["source_media"]:
                payload["source_media"] = sub_obj["source_media"]
                
            r = await utils.request_post_with_backoff(url=get_config("LTB_API_URL"), json=payload, cookies=COOKIES)
            await asyncio.sleep(1)
            if r.status_code == 200:
                res_text = r.json()
                if res_text is None:
                    rule_results.append(False)
                    continue

                try:
                    tokens = res_text.strip().lower().strip(" \t\n\r.,!?\"'*").split()
                    text_clean = tokens[-1] if tokens else ""
                    if "pass" in text_clean:
                        rule_results.append(True)
                    elif "fail" in text_clean:
                        rule_results.append(False)
                    elif "pass" in res_text.lower():
                        rule_results.append(True)
                    elif "fail" in res_text.lower():
                        rule_results.append(False)
                    else:
                        rule_results.append(False)
                except Exception as e:
                    print(f"Error processing response for submission {sub_obj_lb['id']}, rule '{rule}': {e}")
                    rule_results.append(None)
            else:
                rule_results.append(False)

        sub_obj_lb["verification"] = rule_results

    pbar = tqdm.tqdm(total=len(lb_subs))
    for chunk_i in range(0, len(lb_subs), CHUNK_SIZE):
        sub_chunk = lb_subs[chunk_i:chunk_i+CHUNK_SIZE]
        await asyncio.gather(*[process_sub(sub) for sub in sub_chunk])
        pbar.update(len(sub_chunk))
    pbar.close()

    sub_lb_scored = [sub_obj_lb for sub_obj_lb in lb_subs if sub_obj_lb.get("verification") is not None]
    if sub_lb_scored:
        lb_info["score"] = statistics.mean([
            all(sub_obj_lb["verification"])
            for sub_obj_lb in sub_lb_scored
        ])
    else:
        lb_info["score"] = 0.0
    db.execute("UPDATE leaderboard SET status = 'scored', info = ?, submissions = ? WHERE id = ?", (json.dumps(lb_info), json.dumps(lb_subs), args.uid)) # type: ignore
    db.commit()

if __name__ == "__main__":
    asyncio.run(main())

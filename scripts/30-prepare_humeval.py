# %%

import collections
import json
import os
import copy
import random
os.chdir(os.path.dirname(os.path.abspath(__file__))+"/..")

with open("data/submissions.json", "r") as f:
    submissions = json.load(f)

submissions = [x for x in submissions if x["status"] == "accept"]

MODELS = ["human", "Google Translate", "Gemini 3.5 Flash Lite", "GPT-5.4 Mini", "Gemma 4"]
STYLE_FORM = "<style>.form-container { max-width: 1000px !important; }</style>"
STYLE_CESA = """
<style>
.output_scrollable { flex-direction: column; gap: 20px !important; }
.output_item { display: block !important; }
.output_src { width: calc(100% - 10px) !important; margin-bottom: 30px; }
.output_block { width: 1000px; margin-left: auto; margin-right: auto;}
.output_response { width: 400px !important; display: inline-block !important; }
.slider_label_cESA { width: 200px; text-align: left; display: inline-block; }
</style>
"""

submissions_perlangs = collections.defaultdict(list)

for submission in submissions:
    if submission["source_media"] is not None or submission["source_instructions"] is not None:
        continue
    if len(submission["verification_rules"]) > 3:
        continue
    if len(submission["source_text"]) > 500:
        continue
    if any(x["translation"] is None or len(x["translation"]) > 500 for x in submission["translations"]):
        continue
    submission["target_lang"] = submission["target_lang"].replace(" (United States)", "")
    submissions_perlangs[(submission["source_lang"], submission["target_lang"])].append(submission)

submissions_perlangs = {
    ls: random.Random(0).sample(submissions, k=min(len(submissions), 30))
    for ls, submissions in submissions_perlangs.items()
    if len(submissions) >= 10
}

campaign_data = {
    "campaign_id": f"Last Translation Benchmark v1",
    "info": {
        "assignment": "task-based",
        "protocol": "cESA",
        "shuffle": True,
        "users": [],
    },
    "data": []
}
for (lang1, lang2), submissions in submissions_perlangs.items():
    task_data = []
    for submission in submissions:
        doc_obj = {
            "src": submission["source_text"],
            "tgt": {
                model: [x["translation"] for x in submission["translations"] if x["model"] == model][0]
                for model in MODELS
                if any(x["model"] == model for x in submission["translations"])
            },
            "instructions": STYLE_CESA,
            "item_id": submission["id"],
        }
        doc_obj_rules = copy.deepcopy(doc_obj)
        doc_obj_rules["instructions"] = (
            "<div class='white-box' style='margin: -80px 10px 10px 0px; background-color: #e7e2cf;'>" +
            "Now also verify the translations by considering these rules. You may disagree with their necessity.<br><br>" +
            "<br>\n".join(["<b>Rule: </b>" + x["value"] for x in submission["verification_rules"]]) +
            "<div>"+STYLE_CESA
        )
        doc_obj_form = [
            {
                "text": "<b>Source text:</b> " + submission["source_text"] + STYLE_FORM,
                "form": None,
            },
        ]

        for rule in submission["verification_rules"]:
            doc_obj_form.append({
                "text": f"<br><br>Do you think the rule is realistic, or would it fail correct translations?<br><br><b>Rule:</b> {rule['value']}",
                "form": "choices",
                "choices": ["This rule is realistic and reasonable", "This rule is too strict", "Not sure"],
            })
        doc_obj_form.append({
            "text": (
                "<br><br>Are there translations that are incorrect but would pass all of these verifications at the same time?<br><br>"+
                "<br>".join(["<b>Rule: </b>" + x["value"] for x in submission["verification_rules"]])
            ),
            "form": "choices",
            "choices": ["These rules are fine as they cover most cases", "Some incorrect translations might pass through", "Not sure"],
        })


        task_data.append([doc_obj])
        task_data.append([doc_obj_rules])
        task_data.append(doc_obj_form)

    campaign_data["data"].append(task_data)
    campaign_data["data"].append(task_data)
    campaign_data["info"]["users"].append({"user_id": f"{lang1} -> {lang2} D0"})
    campaign_data["info"]["users"].append({"user_id": f"{lang1} -> {lang2} D1"})
    print(f"Campaign {lang1} -> {lang2} has {len(task_data)} items")

os.makedirs("humeval", exist_ok=True)
with open("humeval/campaigns.json", "w") as f:
    json.dump(campaign_data, f, ensure_ascii=False, indent=2)


"""
cd humeval
pearmut add campaigns.json
pearmut run --port 8001 --url https://pearmut.ngrok.io
ngrok http 8001 --url=pearmut.ngrok.io --traffic-policy-file=/home/vilda/pearmut/misc/policy.yml
"""
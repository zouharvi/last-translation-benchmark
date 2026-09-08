import json
from lara_sdk import AccessKey, Translator
import os
import tqdm
import iso639

os.chdir(os.path.dirname(__file__)+"/../..")

from last_translation_benchmark.utils import get_config, save_compact_json
from last_translation_benchmark.languages import LANGUAGES

with open("data/v1.json", "r") as f:
    data = json.load(f)
data = [x for x in data if "LTBv1-eval" in x["tags"]]
lara_translator = Translator(AccessKey(get_config("LARA_API_ID"), get_config("LARA_API_SECRET")))


LANGUAGES = [lang for lang in LANGUAGES if lang["code_lara"] is not None]

def lang_to_lara_lang(lang_iso: str | None, lang_name: str) -> str:
    matching_languages = [lang for lang in LANGUAGES if lang["name"] == lang_name]
    if matching_languages:
        return matching_languages[0]["code_lara"]

    lang_name = lang_name.split("(")[0].split(",")[0].strip()
    matching_languages = [lang for lang in LANGUAGES if lang["name"] == lang_name]
    if matching_languages:
        return matching_languages[0]["code_lara"]

    if lang_iso is not None:
        try:
            lang = iso639.Language.from_part3(lang_iso).part1
            if lang is not None:
                return lang
            else:
                return lang_iso
        except Exception:
            return lang_iso

    return lang_name

os.makedirs("computed/submissions", exist_ok=True)
if os.path.exists("computed/submissions/lara2_thinkpro_fluid.json"):
    with open("computed/submissions/lara2_thinkpro_fluid.json", "r") as f:
        data_existing = {
            item["id"]: item["translation"] for item in json.load(f)
        }
else:
    data_existing = {}

data_new = []
for item in tqdm.tqdm(data):

    if item["id"] in data_existing and data_existing[item["id"]] != "":
        translation = data_existing[item["id"]]
    else:
        src_lang = lang_to_lara_lang(item["source_lang_iso"], item["source_lang"])
        tgt_lang = lang_to_lara_lang(item["target_lang_iso"], item["target_lang"])
        try:
            translation = lara_translator.translate(
                item["source_text"],
                source=src_lang,
                target=tgt_lang,
                style="fluid",
                reasoning="think pro", # type: ignore
            ).translation
        except Exception as e:
            print(f"Error translating {item['id']}: {e}")
            translation = ""
        
    data_new.append({
        "id": item["id"],
        "translation": translation
    })

    save_compact_json(data_new, "computed/submissions/lara2_thinkpro_fluid.json")
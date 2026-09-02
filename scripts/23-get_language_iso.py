import json
import os
import urllib.parse

import requests

os.chdir(os.path.dirname(__file__)+"/..")
from last_translation_benchmark.utils import get_config

COOKIES = {
    "ltb_user": urllib.parse.quote(get_config("LTB_API_USER")),
    "ltb_token": urllib.parse.quote(get_config("LTB_API_TOKEN"))
}

with open("data/submissions.json", "r") as f:
    submissions = json.load(f)

langs_unique = list({
    s["source_lang"]
    for s in submissions if s["status"] == "accept"
} | {
    s["target_lang"]
    for s in submissions if s["status"] == "accept"
})

prompt = """
Get the ISO 639-3 language code for each of the languages.
Rules:
- Preserve the original languagen ame exactly.
- Never invent a code.
- Use the most specific ISO-639-3 code available. For example, dialects with their own unambiguous ISO 639-3 code should use it.
- For historical variants, if no specific code is available for that historical variant, set ISO-639-3 to the modern language code and use variant to specify the historical variant.
- For a hyperlocal dialect/place not captured exactly by ISO-639-3, put the most relevant language in ISO-639-3 and specify the place in variant.
- If a macrolanguage is specified with no further information that is specific enough, set ISO-639-3 to the macrolanguage code and use variant to specify the extra information. Extra information may be place names, dialects, or other details.
- If no language is specified or can be figured out - only writing script, or multiple languages, or not enough information to resolve a language, set it to null.
- Output in the same JSON format which is dictionary from strings to strings/null, e.g. {"Czech": "ces", "Romanian (Moldova)": "ron", ...}
- Keep it simple. Don't overcomplicate it.

""" + json.dumps(langs_unique, ensure_ascii=False)


payload = {
    "model": "google/gemini-3.1-pro-preview",
    "prompt": prompt,
    "cache": True,
}

response = requests.post(url=get_config("LTB_API_URL"), json=payload, cookies=COOKIES)
response.raise_for_status()
res_text = response.json().strip("`").removeprefix("json").strip().strip("`")
result = json.loads(res_text)

with open("data/lang2iso.json", "w") as f:
    json.dump(result, f, ensure_ascii=False, indent=2)
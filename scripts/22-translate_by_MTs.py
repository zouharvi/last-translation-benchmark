import json
import os
import re
import tomllib
import asyncio
import threading
import unicodedata
from tqdm.asyncio import tqdm
import tiktoken
import requests

os.chdir(os.path.dirname(os.path.abspath(__file__))+"/..")
_CONFIG = {}
for _config_file in ("config.toml", "config.template.toml"):
    if os.path.exists(_config_file):
        with open(_config_file, "rb") as _f:
            _CONFIG = tomllib.load(_f)
        break


def get_config(key: str, default: str = "") -> str:
    return _CONFIG.get(key) or os.getenv(key, default)

VLLM_HOST = get_config("VLLM_HOST", "localhost")

def vllm_base_url(port: int) -> str:
    return f"http://{VLLM_HOST}:{port}/v1"

MODELS = [
    {"name": "TranslateGemma", "provider": "vllm-chat-translategemma", "model": "google/translategemma-27b-it", "base_url": vllm_base_url(8001)},
    {"name": "Command-A-Translate", "provider": "cohere", "model": "command-a-translate-08-2025"},
    {"name": "HY-MT2", "provider": "vllm-chat", "model": "tencent/Hy-MT2-30B-A3B", "base_url": vllm_base_url(8002)},
    {"name": "Seed-X-PPO-7B", "provider": "vllm-completion-seedx", "model": "ByteDance-Seed/Seed-X-PPO-7B", "base_url": vllm_base_url(8003)},
    {"name": "Tower+", "provider": "vllm-chat", "model": "Unbabel/Tower-Plus-9B", "base_url": vllm_base_url(8004)},
    # {"name": "QwenMT", "provider": "alibaba", "model": "qwen-mt-plus"},
    {"name": "NLLB-200", "provider": "transformers-nllb", "model": "facebook/nllb-200-3.3B"},
    {"name": "NLLB-MoE-54B", "provider": "transformers-nllb", "model": "facebook/nllb-moe-54b"},
    {"name": "GemmaX2-28-9B", "provider": "vllm-completion-gemmax2", "model": "ModelSpace/GemmaX2-28-9B-v0.1", "base_url": vllm_base_url(8006)},
]
MODEL_FILTER = get_config("MT_MODEL_FILTER")
if MODEL_FILTER:
    MODELS = [m for m in MODELS if m["name"] == MODEL_FILTER]
    if not MODELS:
        raise ValueError(f"MT_MODEL_FILTER={MODEL_FILTER!r} does not match any model name")

LIMIT = int(get_config("MT_LIMIT") or 0) or None

DATA_FILE = "data/submissions.json"
CACHE_FILE = "data/submissions_mt_models.json"
CONCURRENCY = 32

ALIBABA_URL = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1/chat/completions"
COHERE_URL = "https://api.cohere.com/v2/chat"

LANG_CODES = {
    "english": ("en", "eng_Latn"), "chinese": ("zh", "zho_Hans"),
    "chinese (simplified)": ("zh", "zho_Hans"), "chinese (traditional)": ("zh", "zho_Hant"),
    "german": ("de", "deu_Latn"), "french": ("fr", "fra_Latn"), "français": ("fr", "fra_Latn"),
    "spanish": ("es", "spa_Latn"),
    "italian": ("it", "ita_Latn"), "portuguese": ("pt", "por_Latn"), "japanese": ("ja", "jpn_Jpan"),
    "korean": ("ko", "kor_Hang"), "russian": ("ru", "rus_Cyrl"), "arabic": ("ar", "arb_Arab"),
    "dutch": ("nl", "nld_Latn"), "polish": ("pl", "pol_Latn"), "turkish": ("tr", "tur_Latn"),
    "vietnamese": ("vi", "vie_Latn"), "thai": ("th", "tha_Thai"), "hindi": ("hi", "hin_Deva"),
    "hebrew": ("he", "heb_Hebr"), "persian": ("fa", "pes_Arab"), "farsi": ("fa", "pes_Arab"),
    "ukrainian": ("uk", "ukr_Cyrl"), "czech": ("cs", "ces_Latn"), "greek": ("el", "ell_Grek"),
    "romanian": ("ro", "ron_Latn"), "indonesian": ("id", "ind_Latn"), "swedish": ("sv", "swe_Latn"),
    "finnish": ("fi", "fin_Latn"), "danish": ("da", "dan_Latn"), "hungarian": ("hu", "hun_Latn"),
    "bengali": ("bn", "ben_Beng"), "urdu": ("ur", "urd_Arab"), "telugu": ("te", "tel_Telu"),
    "tamil": ("ta", "tam_Taml"), "marathi": ("mr", "mar_Deva"), "gujarati": ("gu", "guj_Gujr"),
    "kannada": ("kn", "kan_Knda"), "malayalam": ("ml", "mal_Mlym"), "punjabi": ("pa", "pan_Guru"),
    "croatian": ("hr", "hrv_Latn"), "slovak": ("sk", "slk_Latn"), "bulgarian": ("bg", "bul_Cyrl"),
    "lithuanian": ("lt", "lit_Latn"), "estonian": ("et", "est_Latn"), "catalan": ("ca", "cat_Latn"),
    "amharic": ("am", "amh_Ethi"),
    "egyptian arabic": ("ar", "arz_Arab"),
    "arabic tunisian": ("ar", "aeb_Arab"),
    "jordanian arabic": ("ar", "ajp_Arab"),  # South Levantine - covers Jordan/Palestine
    "lebanese arabic": ("ar", "apc_Arab"),  # North Levantine - covers Lebanon/Syria
    "yemeni arabic": ("ar", "acq_Arab"),  # Ta'izzi-Adeni - the Yemeni FLORES-200 variety
    "algerian": ("ar", "ary_Arab"), "arabic algerian": ("ar", "ary_Arab"),
    "sudanese arabic": ("ar", "arz_Arab"),
    "esperanto": ("eo", "epo_Latn"),
    "filipino": ("tl", "tgl_Latn"),
    "hausa": ("ha", "hau_Latn"),
    "kurdish": ("ku", "ckb_Arab"),  # observed data value is "Kurdish (Sorani)"
    "luxembourgish": ("lb", "ltz_Latn"),
    "odia": ("or", "ory_Orya"),
    "sanskrit": ("sa", "san_Deva"),
    "ligurian": (None, "lij_Latn"),
    "volapük": ("vo", None),
    "romansh": ("rm", None),  # dialect (Sursilvan/Sutsilvan/...) lost - see normalize_lang's paren-stripping
}


def normalize_lang(name: str):
    base = re.sub(r"\s*\(.*?\)\s*", "", name or "").strip().lower()
    base = "".join(ch for ch in base if not unicodedata.category(ch).startswith("Cf"))
    return LANG_CODES.get(base)


class UnsupportedLanguage(Exception):
    """Raised when a model needs a language code (see LANG_CODES) that a
    submission's source/target language isn't mapped to."""


def cache_key(sub) -> str:
    return f"{sub['source_lang']}_#_{sub['target_lang']}_#_{sub['source_text']}"


def get_prompt(sub) -> str:
    prompt = f"Translate the following text from {sub['source_lang']} to {sub['target_lang']}. Output only the translation and nothing else:\n{sub['source_text']}"
    return prompt


def estimate_tokens(text: str) -> int:
    encoder = tiktoken.get_encoding("cl100k_base")
    return len(encoder.encode(text))


async def request_post_with_backoff(**kwargs):
    delay = 1
    await asyncio.sleep(0.5)
    for _ in range(3):
        response = requests.post(**kwargs)
        if response.status_code == 200:
            return response
        elif response.status_code == 429:
            print(f"Rate limited. Retrying in {delay} seconds...")
        else:
            raise Exception(f"Request failed with status {response.status_code}: {response.text}")
        await asyncio.sleep(delay)
        delay *= 2

    raise Exception("Request failed after 3 retries")


async def request_vllm_chat(model, prompt: str) -> str | None:
    payload = {
        "model": model["model"],
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0,
        "max_tokens": 1024,
    }
    response = await request_post_with_backoff(url=f"{model['base_url']}/chat/completions", json=payload)
    return response.json()["choices"][0]["message"]["content"]


_TOKENIZER_CACHE = {}
_TRANSFORMERS_LOCK = threading.Lock()


def _get_tokenizer(model_id: str):
    if model_id not in _TOKENIZER_CACHE:
        with _TRANSFORMERS_LOCK:
            if model_id not in _TOKENIZER_CACHE:
                from transformers import AutoTokenizer
                _TOKENIZER_CACHE[model_id] = AutoTokenizer.from_pretrained(model_id)
    return _TOKENIZER_CACHE[model_id]


async def request_vllm_chat_translategemma(model, sub) -> str | None:
    src_codes = normalize_lang(sub["source_lang"])
    tgt_codes = normalize_lang(sub["target_lang"])
    if not src_codes or not tgt_codes:
        missing = sub["source_lang"] if not src_codes else sub["target_lang"]
        raise UnsupportedLanguage(f"{missing!r} not in LANG_CODES")
    if src_codes[0] is None or tgt_codes[0] is None:
        missing = sub["source_lang"] if src_codes[0] is None else sub["target_lang"]
        raise UnsupportedLanguage(f"{missing!r} has no TranslateGemma code")

    def _render():
        tokenizer = _get_tokenizer(model["model"])
        messages = [{
            "role": "user",
            "content": [{
                "type": "text",
                "source_lang_code": src_codes[0],
                "target_lang_code": tgt_codes[0],
                "text": sub["source_text"],
                "image": None,
            }],
        }]
        return tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)

    prompt = await asyncio.to_thread(_render)
    return await request_vllm_completion(model, prompt)


async def request_vllm_completion(model, prompt: str, extra_body: dict | None = None) -> str | None:
    payload = {
        "model": model["model"],
        "prompt": prompt,
        "temperature": 0,
        "max_tokens": 1024,
        **(extra_body or {}),
    }
    response = await request_post_with_backoff(url=f"{model['base_url']}/completions", json=payload)
    return response.json()["choices"][0]["text"].strip()


_NLLB_MODEL_CACHE = {}
_NLLB_INFERENCE_LOCK = threading.Lock()


def _get_nllb_model(model_id: str):
    if model_id not in _NLLB_MODEL_CACHE:
        with _TRANSFORMERS_LOCK:  # see comment on _TRANSFORMERS_LOCK above
            if model_id not in _NLLB_MODEL_CACHE:
                import torch
                from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
                tokenizer = AutoTokenizer.from_pretrained(model_id)
                if torch.cuda.is_available():
                    model = AutoModelForSeq2SeqLM.from_pretrained(model_id, dtype=torch.bfloat16, device_map="auto")
                else:
                    model = AutoModelForSeq2SeqLM.from_pretrained(model_id, dtype=torch.bfloat16)
                model.eval()
                _NLLB_MODEL_CACHE[model_id] = (tokenizer, model)
    return _NLLB_MODEL_CACHE[model_id]


async def request_nllb(model, sub) -> str | None:
    src_codes = normalize_lang(sub["source_lang"])
    tgt_codes = normalize_lang(sub["target_lang"])
    if not src_codes or not tgt_codes:
        missing = sub["source_lang"] if not src_codes else sub["target_lang"]
        raise UnsupportedLanguage(f"{missing!r} not in LANG_CODES")
    _, src_flores = src_codes
    _, tgt_flores = tgt_codes
    if not src_flores or not tgt_flores:
        missing = sub["source_lang"] if not src_flores else sub["target_lang"]
        raise UnsupportedLanguage(f"{missing!r} has no FLORES-200 code for {model['name']}")

    def _generate():
        import torch
        tokenizer, nllb_model = _get_nllb_model(model["model"])
        with _NLLB_INFERENCE_LOCK:
            tokenizer.src_lang = src_flores
            inputs = tokenizer(sub["source_text"], return_tensors="pt").to(nllb_model.device)
            forced_bos_token_id = tokenizer.convert_tokens_to_ids(tgt_flores)
            with torch.inference_mode():
                generated = nllb_model.generate(**inputs, forced_bos_token_id=forced_bos_token_id, max_new_tokens=512)
            return tokenizer.batch_decode(generated, skip_special_tokens=True)[0]

    return await asyncio.to_thread(_generate)


async def request_cohere(model, prompt: str) -> str | None:
    headers = {"Authorization": f"Bearer {get_config('COHERE_API_KEY')}", "Content-Type": "application/json"}
    payload = {
        "model": model["model"],
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0,
        "max_tokens": 4096,
    }
    response = await request_post_with_backoff(url=COHERE_URL, json=payload, headers=headers)
    contents = response.json()["message"]["content"]
    texts = [c["text"] for c in contents if c["type"] == "text"]
    return texts[0] if texts else None


# async def request_alibaba(model, sub) -> str | None:
#     headers = {"Authorization": f"Bearer {get_config('ALIBABA_API_KEY')}", "Content-Type": "application/json"}
#     payload = {
#         "model": model["model"],
#         "messages": [{"role": "user", "content": sub["source_text"]}],
#         "translation_options": {"source_lang": sub["source_lang"], "target_lang": sub["target_lang"]},
#     }
#     response = await request_post_with_backoff(url=ALIBABA_URL, json=payload, headers=headers)
#     return response.json()["choices"][0]["message"]["content"]


async def translate_with_model(model, sub) -> str | None:
    provider = model["provider"]

    if provider == "vllm-chat":
        return await request_vllm_chat(model, get_prompt(sub))

    if provider == "vllm-chat-translategemma":
        return await request_vllm_chat_translategemma(model, sub)

    if provider == "cohere":
        return await request_cohere(model, get_prompt(sub))

    # if provider == "alibaba":
    #     return await request_alibaba(model, sub)

    if provider == "vllm-completion-seedx":
        codes = normalize_lang(sub["target_lang"])
        if not codes:
            raise UnsupportedLanguage(f"{sub['target_lang']!r} not in LANG_CODES")
        iso1, _ = codes
        if iso1 is None:
            raise UnsupportedLanguage(f"{sub['target_lang']!r} has no Seed-X-PPO-7B tag")
        prompt = f"Translate the following {sub['source_lang']} sentence into {sub['target_lang']}:\n{sub['source_text']} <{iso1}>"
        return await request_vllm_completion(model, prompt)

    if provider == "vllm-completion-gemmax2":
        prompt = f"Translate this from {sub['source_lang']} to {sub['target_lang']}:\n{sub['source_lang']}: {sub['source_text']}\n{sub['target_lang']}:"
        return await request_vllm_completion(model, prompt)

    if provider == "transformers-nllb":
        return await request_nllb(model, sub)

    raise ValueError(f"Unknown provider: {provider}")


async def main():
    with open(DATA_FILE, "r") as f:
        submissions = json.load(f)

    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "r") as f:
            cache = json.load(f)
    else:
        cache = {}

    accepted = [sub for sub in submissions if sub["status"] == "accept" and not sub.get("source_media")]
    if LIMIT:
        accepted = accepted[:LIMIT]

    text_count = estimate_tokens(" ".join(get_prompt(sub) for sub in accepted))
    print(f"Total tokens: {text_count}")
    print(f"Models: {', '.join(m['name'] for m in MODELS)}")

    for sub in accepted:
        cache.setdefault(cache_key(sub), {})
    
    # Main loop
    for model in MODELS:
        pending = [sub for sub in accepted if model["name"] not in cache[cache_key(sub)]]
        if not pending:
            continue

        semaphore = asyncio.Semaphore(CONCURRENCY)

        async def _process_submission(sub, model=model):
            async with semaphore:
                try:
                    translation = await translate_with_model(model, sub)
                    return sub, translation, None
                except UnsupportedLanguage as e:
                    # permanent - this model will never support this
                    # language, so record it rather than retrying forever
                    return sub, None, str(e)
                except Exception as e:
                    print(f"  Request failed for {model['name']}: {e}")
                    return sub, None, None

        for coro in tqdm.as_completed(
            [_process_submission(sub) for sub in pending],
            total=len(pending), desc=f"Translating with {model['name']}",
        ):
            sub, translation, skip_reason = await coro
            key = cache_key(sub)

            if skip_reason is not None:
                cache[key][model["name"]] = {"model": model["model"], "translation": None, "skipped": skip_reason}
            elif translation is not None:
                cache[key][model["name"]] = {"model": model["model"], "translation": translation}
            else:
                continue
            with open(CACHE_FILE, "w") as f:
                json.dump(cache, f, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    asyncio.run(main())

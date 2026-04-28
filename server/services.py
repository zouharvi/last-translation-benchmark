import httpx
from deep_translator import DeeplTranslator, GoogleTranslator
from openrouter import OpenRouter

from .utils import get_config

_openrouter_client: OpenRouter | None = None

def translate_google(text: str, src_lang: str, tgt_lang: str) -> str:
    return GoogleTranslator(source=src_lang, target=tgt_lang).translate(text)


def translate_deepl(text: str, src_lang: str, tgt_lang: str) -> str:
    DEEPL_API_KEY = get_config("DEEPL_API_KEY", "")
    if not DEEPL_API_KEY:
        raise ValueError("No DeepL API key configured")
    return DeeplTranslator(
        api_key=DEEPL_API_KEY, source=src_lang, target=tgt_lang, use_free_api=True
    ).translate(text)


def translate_mymemory(text: str, src_lang: str, tgt_lang: str) -> str:
    resp = httpx.get(
        "https://api.mymemory.translated.net/get",
        params={"q": text, "langpair": f"{src_lang}|{tgt_lang}"},
        timeout=10,
    )
    data = resp.json()
    if data.get("responseStatus") == 200:
        return data["responseData"]["translatedText"]
    raise Exception(data.get("responseDetails", "API returned an error"))

def _get_client() -> OpenRouter:
    global _openrouter_client
    if _openrouter_client is None:
        _openrouter_client = OpenRouter(api_key=get_config("OPENROUTER_API_KEY", ""))
    return _openrouter_client

def call_llm(prompt: str, model: str = "google/gemini-2.5-flash-lite") -> str:
    # use openrouter api
    client = _get_client()
    response = client.chat.send(
        model=model,
        messages=[
            {
                "role": "user",
                "content": prompt,
            }
        ],
        seed=0,
    )
    return response.choices[0].message.content


def verify_llm(translation: str, rule: str) -> bool:
    text = call_llm(
        f"Your goal is to verify whether a translation fulfills a criterion.\n\nCriterion: {rule}\n\nTranslation to verify: {translation}\n\nOutput only pass or fail and nothing else.",
        model="google/gemini-2.5-flash-lite",
    )
    text = text.strip().lower()
    if "pass" in text and "fail" in text:
        raise ValueError(f"Invalid LLM response: {text}")
    else:
        return "pass" in text


def translate_gemini2_5flash(text: str, src_lang: str, tgt_lang: str) -> str:
    prompt = f"Translate the following text from {src_lang} to {tgt_lang}. Output only the translation and nothing else:\n{text}"
    return call_llm(prompt, model="google/gemini-2.5-flash-lite")


def translate_gemma4(text: str, src_lang: str, tgt_lang: str) -> str:
    prompt = f"Translate the following text from {src_lang} to {tgt_lang}. Output only the translation and nothing else:\n{text}"
    return call_llm(prompt, model="google/gemma-4-31b-it")


def translate_qwen3p6(text: str, src_lang: str, tgt_lang: str) -> str:
    prompt = f"Translate the following text from {src_lang} to {tgt_lang}. Output only the translation and nothing else:\n{text}"
    return call_llm(prompt, model="qwen/qwen3.6-plus")


def translate_gpt4p1nano(text: str, src_lang: str, tgt_lang: str) -> str:
    prompt = f"Translate the following text from {src_lang} to {tgt_lang}. Output only the translation and nothing else:\n{text}"
    return call_llm(prompt, model="openai/gpt-4.1-nano")

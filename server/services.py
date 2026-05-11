import asyncio

import httpx
import lara_sdk
from deep_translator import DeeplTranslator, GoogleTranslator
from openrouter import OpenRouter

from .languages import LANGUAGES
from .utils import get_config

OPENROUTER_CLIENT = OpenRouter(api_key=get_config("OPENROUTER_API_KEY", ""))
HTTP_CLIENT = httpx.AsyncClient(timeout=10)
LARA_CLIENT = lara_sdk.Translator(
    lara_sdk.AccessKey(
        id=get_config("LARA_API_ID", ""),
        secret=get_config("LARA_API_SECRET", ""),
    )
)

NAME_TO_CODE_GOOGLE = {
    x["name"].lower(): x["code_google"]
    for x in LANGUAGES
    if x["code_google"] is not None
}
NAME_TO_CODE_LARA = {
    x["name"].lower(): x["code_lara"] for x in LANGUAGES if x["code_lara"] is not None
}


def translate_google(text: str, src_lang: str, tgt_lang: str) -> str:
    source_code = NAME_TO_CODE_GOOGLE.get(src_lang.lower(), None)
    target_code = NAME_TO_CODE_GOOGLE.get(tgt_lang.lower(), None)
    if source_code is None or target_code is None:
        return None

    return GoogleTranslator(source=source_code, target=target_code).translate(text)


def translate_deepl(text: str, src_lang: str, tgt_lang: str) -> str:
    DEEPL_API_KEY = get_config("DEEPL_API_KEY", "")
    if not DEEPL_API_KEY:
        raise ValueError("No DeepL API key configured")
    return DeeplTranslator(
        api_key=DEEPL_API_KEY, source=src_lang, target=tgt_lang, use_free_api=True
    ).translate(text)


async def translate_mymemory(text: str, src_lang: str, tgt_lang: str) -> str:
    resp = await HTTP_CLIENT.get(
        "https://api.mymemory.translated.net/get",
        params={"q": text, "langpair": f"{src_lang}|{tgt_lang}"},
    )
    data = resp.json()
    if data.get("responseStatus") == 200:
        return data["responseData"]["translatedText"]
    raise Exception(data.get("responseDetails", "API returned an error"))


async def translate_lara(text: str, src_lang: str, tgt_lang: str) -> str:
    source_code = NAME_TO_CODE_LARA.get(src_lang.lower(), None)
    target_code = NAME_TO_CODE_LARA.get(tgt_lang.lower(), None)
    if source_code is None or target_code is None:
        return None

    resp = await asyncio.to_thread(
        lambda: LARA_CLIENT.translate(
            text=text,
            source=source_code,
            target=target_code,
        )
    )
    return resp.translation


async def call_llm(prompt: str, model: str = "google/gemini-2.5-flash") -> str:
    # use global openrouter client
    response = await OPENROUTER_CLIENT.chat.send_async(
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


async def verify_llm(source_text: str, translation: str, rule: str) -> bool:
    text = await call_llm(
        f"Your goal is to verify whether a translation fulfills a criterion.\n\nCriterion: {rule}\n\nSource text: {source_text}\n\nTranslation to verify: {translation}\n\nOutput only pass or fail and nothing else.",
        model="google/gemini-2.5-pro",
    )
    text = text.strip().lower()
    if "pass" in text and "fail" in text:
        raise ValueError(f"Invalid LLM response: {text}")
    else:
        return "pass" in text


async def translate_gemini2_5flash(text: str, src_lang: str, tgt_lang: str) -> str:
    prompt = f"Translate the following text from {src_lang} to {tgt_lang}. Output only the translation and nothing else:\n{text}"
    return await call_llm(prompt, model="google/gemini-2.5-flash")


async def translate_gemma4(text: str, src_lang: str, tgt_lang: str) -> str:
    prompt = f"Translate the following text from {src_lang} to {tgt_lang}. Output only the translation and nothing else:\n{text}"
    return await call_llm(prompt, model="google/gemma-4-31b-it")


async def translate_llama4(text: str, src_lang: str, tgt_lang: str) -> str:
    prompt = f"Translate the following text from {src_lang} to {tgt_lang}. Output only the translation and nothing else:\n{text}"
    return await call_llm(prompt, model="meta-llama/llama-4-scout:nitro")


async def translate_gpt4p1nano(text: str, src_lang: str, tgt_lang: str) -> str:
    prompt = f"Translate the following text from {src_lang} to {tgt_lang}. Output only the translation and nothing else:\n{text}"
    return await call_llm(prompt, model="openai/gpt-4.1-nano")

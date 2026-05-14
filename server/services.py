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
    if source_code is None or target_code is None or not text:
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
    if source_code is None or target_code is None or not text:
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


async def verify_llm(source_text: str, translation: str, rule: str, source_media: str = None) -> bool:
    prompt = f"Your goal is to verify whether a translation fulfills a criterion.\n\nCriterion: {rule}\n\nSource text: {source_text}\n\nTranslation to verify: {translation}\n\nOutput only pass or fail and nothing else."
    if source_media:
        has_audio = "audio" in source_media.split(",")[0]
        context_type = "audio" if has_audio else "image"
        prompt += f"\n\nUse the provided {context_type} as additional context."

    text = await call_llm_multimodal(prompt, model="google/gemini-2.5-pro", source_media=source_media)
    text = text.strip().lower()
    if "pass" in text and "fail" in text:
        raise ValueError(f"Invalid LLM response: {text}")
    else:
        return "pass" in text


async def call_llm_multimodal(prompt: str, model: str, source_media: str = None) -> str:
    if not source_media:
        return await call_llm(prompt, model=model)

    base64_data = None
    if source_media.startswith("data:") and "," in source_media:
        header, base64_data = source_media.split(",", 1)
        mime = header[5:].split(";", 1)[0]
        has_audio = "audio" in mime
        has_image = "image" in mime
    else:
        return await call_llm(prompt, model=model)

    if len(base64_data) > 1024 * 1024:
        raise ValueError("Media data too large (max 1MB)")

    content = [{"type": "text", "text": prompt}]
    if has_audio:
        content.append(
            {
                "type": "input_audio",
                "input_audio": {
                    "data": base64_data,
                    "format": mime.split("/")[1],
                },
            }
        )
    elif has_image:
        content.append({"type": "image_url", "image_url": {"url": source_media}})
    else:
        return await call_llm(prompt, model=model)

    response = await OPENROUTER_CLIENT.chat.send_async(
        model=model,
        messages=[{"role": "user", "content": content}],
    )
    return response.choices[0].message.content


async def translate_openrouter(
    text: str, src_lang: str, tgt_lang: str, model: str, source_media: str = None
) -> str:
    if not source_media:
        prompt = f"Translate the following text from {src_lang} to {tgt_lang}. Output only the translation and nothing else:\n{text}"
        return await call_llm(prompt, model=model)

    # Detect media type for prompt
    has_audio = "audio" in source_media.split(",")[0]
    context_type = "audio" if has_audio else "image"

    if text:
        prompt = (
            f"Translate the following text from {src_lang} to {tgt_lang}. "
            f"Use the provided {context_type} as additional context. "
            f"Output only the translation and nothing else:\n{text}"
        )
    else:
        prompt = f"Translate the provide {context_type} from {src_lang} to {tgt_lang}. Output only the textual translation and nothing else."

    return await call_llm_multimodal(prompt, model, source_media)


async def translate_gemini2_5flash(
    text: str, src_lang: str, tgt_lang: str, source_media: str = None
) -> str:
    return await translate_openrouter(
        text, src_lang, tgt_lang, "google/gemini-2.5-flash", source_media
    )


async def translate_gemma4(
    text: str, src_lang: str, tgt_lang: str, source_media: str = None
) -> str:
    return await translate_openrouter(
        text, src_lang, tgt_lang, "google/gemma-4-31b-it", source_media
    )


async def translate_llama4(
    text: str, src_lang: str, tgt_lang: str, source_media: str = None
) -> str:
    return await translate_openrouter(
        text, src_lang, tgt_lang, "meta-llama/llama-4-scout:nitro", source_media
    )


async def translate_gpt4p1nano(
    text: str, src_lang: str, tgt_lang: str, source_media: str = None
) -> str:
    return await translate_openrouter(
        text, src_lang, tgt_lang, "openai/gpt-4.1-nano", source_media
    )

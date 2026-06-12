import asyncio
import base64
import mimetypes
import tempfile

import httpx
import lara_sdk
from deep_translator import DeeplTranslator, GoogleTranslator
from openrouter import OpenRouter

from .db import sqlite_cache
from .languages import LANGUAGES
from .utils import get_config, log, retry_async

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


def translate_google(
    text: str,
    src_lang: str,
    tgt_lang: str,
    source_media: str | None = None,
    source_instructions: str | None = None,
) -> str| None:
    source_code = NAME_TO_CODE_GOOGLE.get(src_lang.lower(), None)
    target_code = NAME_TO_CODE_GOOGLE.get(tgt_lang.lower(), None)
    if (
        source_code is None
        or target_code is None
        or not text
        or source_media
        or source_instructions
    ):
        return None

    return GoogleTranslator(source=source_code, target=target_code).translate(text)


@sqlite_cache()
async def translate_google_with_api(
    text: str,
    src_lang: str,
    tgt_lang: str,
    source_media: str | None = None,
    source_instructions: str | None = None,
) -> str | None:
    source_code = NAME_TO_CODE_GOOGLE.get(src_lang.lower(), None)
    target_code = NAME_TO_CODE_GOOGLE.get(tgt_lang.lower(), None)
    if (
        source_code is None
        or target_code is None
        or not text
        or source_media
        or source_instructions
    ):
        return None

    api_key = get_config("GOOGLE_TRANSLATE_API_KEY", "")
    if not api_key:
        raise ValueError("No Google Translate API key configured")

    response = await HTTP_CLIENT.post(
        "https://translation.googleapis.com/language/translate/v2",
        data={
            "q": text,
            "source": source_code,
            "target": target_code,
            "format": "text",
            "key": api_key,
        },
    )
    response.raise_for_status()
    return response.json()["data"]["translations"][0]["translatedText"]


def translate_deepl(
    text: str, src_lang: str, tgt_lang: str, source_media: str | None = None
) -> str | None:
    if source_media:
        return None
    DEEPL_API_KEY = get_config("DEEPL_API_KEY", "")
    if not DEEPL_API_KEY:
        raise ValueError("No DeepL API key configured")
    return DeeplTranslator(
        api_key=DEEPL_API_KEY, source=src_lang, target=tgt_lang, use_free_api=True
    ).translate(text)


@sqlite_cache()
async def translate_lara(
    text: str,
    src_lang: str,
    tgt_lang: str,
    source_media: str | None = None,
    source_instructions: str | None = None,
) -> str | None:
    source_code = NAME_TO_CODE_LARA.get(src_lang.lower(), None)
    target_code = NAME_TO_CODE_LARA.get(tgt_lang.lower(), None)
    if source_code is None or target_code is None:
        return None

    if source_media:
        if source_media.startswith("data:") and "," in source_media:
            header, base64_data = source_media.split(",", 1)
            mime = header[5:].split(";", 1)[0]
            if "image" not in mime:
                return None
            # we dont support both image an text or instructions in Lara
            if text or source_instructions:
                return None

            with tempfile.NamedTemporaryFile(
                suffix=mimetypes.guess_extension(mime) or ".png"
            ) as f:
                f.write(base64.b64decode(base64_data))
                f.flush()
                temp_path = f.name

                resp = await asyncio.to_thread(
                    lambda: LARA_CLIENT.images.translate_text(
                        image_path=temp_path,
                        source=source_code,
                        target=target_code,
                    )
                )
                return "\n".join(p.translation for p in resp.paragraphs)

    if not text:
        return None

    resp = await asyncio.to_thread(
        lambda: LARA_CLIENT.translate(
            text=text,
            source=source_code,
            target=target_code,
            instructions=[source_instructions] if source_instructions else None,  # type: ignore
        )
    )
    return resp.translation # type: ignore


@sqlite_cache(discard_none=True)
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
    content = response.choices[0].message.content
    if content is None:
        log(f"None LLM response: {response.choices[0]}")
    return content  # type: ignore


@retry_async(times=3)
async def verify_llm(
    source_text: str, translation: str, rule: str, source_media: str | None = None
) -> bool:
    if not source_text and source_media:
        source_text = "(attached)"
    prompt = f"Your goal is to verify whether a translation fulfills a criterion.\n\nCriterion: {rule}\n\nInput: {source_text}\n\nTranslation to verify: {translation}\n\nOutput only pass or fail and nothing else."
    if source_media:
        mime = source_media.split(",")[0]
        context_type = "audio" if "audio" in mime else ("video" if "video" in mime else "image")
        prompt += f"\n\nUse the provided {context_type} as additional context."

    text = await call_llm_multimodal(
        prompt, model="google/gemini-2.5-pro", source_media=source_media
    )
    if text is None:
        raise ValueError("No response from LLM. Try simplifying your input and verification rules.")
    text_clean = text.strip().lower().strip(" \t\n\r.,!?\"'*")
    if text_clean == "pass":
        return True
    elif text_clean == "fail":
        return False
    else:
        raise ValueError(f"Invalid LLM response: {text}")


@sqlite_cache(discard_none=True)
async def call_llm_multimodal(
    prompt: str, model: str, source_media: str | None = None
) -> str:
    if not source_media:
        return await call_llm(prompt, model=model)

    base64_data = None
    if source_media.startswith("data:") and "," in source_media:
        header, base64_data = source_media.split(",", 1)
        mime = header[5:].split(";", 1)[0]
        has_audio = "audio" in mime
        has_image = "image" in mime
        has_video = "video" in mime
    else:
        return await call_llm(prompt, model=model)

    if len(base64_data) > 2 * 1024 * 1024:
        raise ValueError("Media data too large (max 2MB)")

    content: list = [{"type": "text", "text": prompt}]
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
    elif has_video:
        content.append({"type": "video_url", "video_url": {"url": source_media}})
    elif has_image:
        content.append({"type": "image_url", "image_url": {"url": source_media}})
    else:
        return await call_llm(prompt, model=model)

    response = await OPENROUTER_CLIENT.chat.send_async(
        model=model,
        messages=[{"role": "user", "content": content}],
    )
    msg_content = response.choices[0].message.content
    if msg_content is None:
        log(f"None LLM response: {response.choices[0]}")
    return msg_content # type: ignore


async def translate_openrouter(
    text: str,
    src_lang: str,
    tgt_lang: str,
    model: str,
    source_media: str| None = None,
    source_instructions: str| None = None,
) -> str:
    if not source_media:
        prompt = f"Translate the following text from {src_lang} to {tgt_lang}. Output only the translation and nothing else:\n{text}"
        if source_instructions:
            prompt += f'\nAdditional instructions for this translation are: "{source_instructions}"'
        return await call_llm(prompt, model=model)

    # Detect media type for prompt
    mime = source_media.split(",")[0]
    has_audio = "audio" in mime
    has_video = "video" in mime
    context_type = "audio" if has_audio else ("video" if has_video else "image")

    if text:
        prompt = (
            f"Translate the following text from {src_lang} to {tgt_lang}. "
            f"Use the provided {context_type} as additional context. "
            f"Output only the translation and nothing else:\n{text}"
        )
    else:
        prompt = f"Translate the provide {context_type} from {src_lang} to {tgt_lang}. Output only the textual translation and nothing else."

    if source_instructions:
        prompt += f'\nAdditional instructions for this translation are: "{source_instructions}"'

    return await call_llm_multimodal(prompt, model, source_media)

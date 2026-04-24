import httpx
from deep_translator import DeeplTranslator, GoogleTranslator
from openrouter import OpenRouter

from .utils import get_config


def translate_google(text: str, src: str, tgt: str) -> str:
    return GoogleTranslator(source=src, target=tgt).translate(text)


def translate_deepl(text: str, src: str, tgt: str) -> str:
    DEEPL_API_KEY = get_config("DEEPL_API_KEY", "")
    if not DEEPL_API_KEY:
        raise ValueError("No DeepL API key configured")
    return DeeplTranslator(
        api_key=DEEPL_API_KEY, source=src, target=tgt, use_free_api=True
    ).translate(text)


def translate_mymemory(text: str, src: str, tgt: str) -> str:
    resp = httpx.get(
        "https://api.mymemory.translated.net/get",
        params={"q": text, "langpair": f"{src}|{tgt}"},
        timeout=10,
    )
    data = resp.json()
    if data.get("responseStatus") == 200:
        return data["responseData"]["translatedText"]
    raise Exception(data.get("responseDetails", "API returned an error"))


def call_llm(prompt: str, model: str = "google/gemini-2.5-flash-lite") -> str:
    # use openrouter api
    client = OpenRouter(api_key=get_config("OPENROUTER_API_KEY", ""))
    response = client.chat.send(
        model=model,
        messages=[
            {
                "role": "user",
                "content": prompt,
            }
        ],
    )
    return response.choices[0].message.content.lower()


def verify_llm(translation: str, rule: str) -> bool:
    text = call_llm(
        f"Criterion: {rule}\n\nTranslation to verify: {translation}\n\nOutput only pass or fail and nothing else.",
        model="google/gemini-2.5-flash-lite",
    )
    if "pass" in text and "fail" in text:
        raise ValueError(f"Invalid LLM response: {text}")
    else:
        return "pass" in text


def translate_gemini2_5flash(text: str, src: str, tgt: str) -> str:
    prompt = f"Translate the following text from {src} to {tgt}. Output only the translation and nothing else.:\n{text}"
    return call_llm(prompt, model="google/gemini-2.5-flash-lite")


def translate_gemma4(text: str, src: str, tgt: str) -> str:
    prompt = f"Translate the following text from {src} to {tgt}. Output only the translation and nothing else.:\n{text}"
    return call_llm(prompt, model="google/gemma-4-31b-it")


def translate_qwen3p6(text: str, src: str, tgt: str) -> str:
    prompt = f"Translate the following text from {src} to {tgt}. Output only the translation and nothing else.:\n{text}"
    return call_llm(prompt, model="qwen/qwen3.6-plus")


def translate_gpt4p1nano(text: str, src: str, tgt: str) -> str:
    prompt = f"Translate the following text from {src} to {tgt}. Output only the translation and nothing else.:\n{text}"
    return call_llm(prompt, model="openai/gpt-4.1-nano")

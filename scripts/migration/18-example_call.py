# %%

import urllib.parse

import requests

cookies = {
    "ltb_user": urllib.parse.quote(""),
    "ltb_token": urllib.parse.quote(""),
}
payload = {
    "model": "google/gemini-3.1-pro-preview",
    "prompt": "Explain what a multimodal LLM is in one sentence.",
    # "source_media": "data:image/jpeg;base64,/9j/4AAQSkZJRg..."  # Optional, encoded in the same way as in database
}

response = requests.post(
    "https://last-translation-benchmark.vilda.net/api/llm",
    json=payload,
    cookies=cookies,
)

print(response.status_code, response.json())
import random


def estimate_tokens(text: str) -> int:
    import tiktoken
    encoder = tiktoken.get_encoding("cl100k_base")
    return len(encoder.encode(text))

async def request_post_with_backoff(**kwargs):
    import asyncio

    import requests
    delay = 2
    for _ in range(8):
        await asyncio.sleep(delay * random.uniform(0.5, 1.5))
        response = await asyncio.to_thread(requests.post, **kwargs)
        if response.status_code == 200:
            if response.text.count("our ") >= 1_000:
                response._content = b'"teapot"'
            return response
        elif response.status_code == 429:
            print(response.text)
            print(f"Rate limited. Retrying in {delay} seconds...")
        elif response.status_code == 418:
            # teapot response, mostly validation, will not be fixed
            # return new 200 response with text "teapot"
            response.status_code = 200
            response._content = b'"teapot"'
            return response
        else:
            raise Exception(f"Request failed with status {response.status_code}: {response.text}")
        delay *= 2

    raise Exception("Request failed after 6 retries")


def model_price_per_token(model_name: str) -> tuple[float, float]:
    import requests
    resp = requests.get("https://openrouter.ai/api/v1/models")
    resp.raise_for_status()
    models = resp.json().get("data", [])
    
    model = next((m for m in models if m["id"] == model_name), None)
    if model is None:
        return (0, 0)
        
    # OpenRouter returns pricing as strings representing cost per token.
    price_per_token_input = float(model["pricing"]["prompt"])
    price_per_token_output = float(model["pricing"]["completion"])

    return (price_per_token_input, price_per_token_output)
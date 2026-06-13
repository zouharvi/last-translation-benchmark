This folder contains scripts for transplanting submissions across language pairs.

# Run


```bash
conda run -n ltb python scripts/langtransfer/llm_transplant.py source Hindi --limit 3 --prompt 1 --fill-api-translations --verification-model debugging
```

Arguments:
- `transplant_side`: `source` or `target`
- `transplant_lang`: new language name
- `--prompt`: numeric prompt key from `llm_transplant_prompts.py`
- `--limit`: first N submissions only
- `--fill-api-translations`: fill model translations and `verified` arrays
- `--verification-model`: `debugging` (default) uses OpenAI `gpt-5.4-mini`; `openrouter` uses the backend verifier (avoid for cost)

# Data

Input:
`data/langtransfer/submissions_v2.json`

Output:
`data/langtransfer/transplanted/langtransfer_p{prompt}_{side}_{lang}.json`

# Prompts

Prompts are in:
`scripts/langtransfer/llm_transplant_prompts.py`

# Keys

Put keys in:
`scripts/langtransfer/keys.toml`

```toml
OPENAI_API_KEY = "..."
OPENROUTER_API_KEY = "..."
```

`OPENAI_API_KEY` is required for transplant generation and checking verification rules.
`OPENROUTER_API_KEY` is required when filling OpenRouter model translations or using backend verification.

This branch is for transplanting submissions across language pairs.
Currently, it contains code to run the naive transplanting approach with LLMs.

# Run like this:
```bash
python scripts/langtransfer/llm_transplant.py target Swahili --limit 10 --prompt 1
```

Arguments:
- `transplant_side`: `source` or `target`
- `transplant_lang`: new language name
- `--prompt`: numeric prompt key from `llm_transplant_prompts.py`
- `--limit`: first N submissions only (debugging)

# Data
Input:
Original submission data expected here:
`data/langtransfer/submissions.json`

Output path:
Transplanted data written here:
`data/langtransfer/transplanted/langtransfer_p{prompt}_{side}_{lang}.json`

# Prompts
The current prompt used is in
`scripts/langtransfer/llm_transplant_prompts.py`

This is just a simple default, feel free to try new ones as numbered keys! We can keep IO instructions the same for parsing.


# Keys
Put keys in:
`scripts/langtransfer/keys.toml`

```toml
OPENAI_API_KEY = "..."
OPENROUTER_API_KEY = ""
```

Transplanting uses OpenAI directly.

Currently, we don't fill in translations from other models for the new pair, so OpenRouter key not required for now.


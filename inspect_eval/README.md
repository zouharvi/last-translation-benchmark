# LTB as an Inspect AI eval

Runs the `LTBv1-eval` subset (911 text-only items) with [Inspect AI](https://inspect.aisi.org.uk/), scored the same way as the leaderboard (`scripts/41-score_leaderboard.py`): one judge call per verification rule, and an item counts as correct only if every rule passes.

```bash
pip install -e .
```

```bash
inspect eval inspect_eval/ltb.py --model openrouter/google/gemma-4-31b-it
```

The judge defaults to `google/gemini-3.8-flash`, the leaderboard verifier. Override it with `-T judge_model=<model>` or `--model-role grader=<model>`. Scores are only comparable to the leaderboard when the same judge is used.

The model under test gets a minimal instruction (`TRANSLATE_PROMPT` in `ltb.py`), since the leaderboard itself takes submitted translations and defines no prompt.

## Data

`LTBv1-eval.jsonl` is a pinned snapshot of the eval subset, without the `translations` and `source_media` fields. The current snapshot was taken from `LTBv1.json` on 2026-09-14. To refresh it:

```bash
python inspect_eval/make_snapshot.py path/to/LTBv1.json
```

## Tests

```bash
cd inspect_eval && pytest test_ltb.py
```

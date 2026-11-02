"""Last Translation Benchmark (LTBv1-eval) as an Inspect AI task.

Each item is a source text plus one or more natural-language verification
rules. A judge model answers pass/fail per rule, and a translation counts as
correct only if every rule passes. The headline metric is the leaderboard
score: the mean over items of all(rules passed).

Mirrors scripts/41-score_leaderboard.py: same verifier prompt
(server/utils.py::get_prompt_verify), same pass/fail parse, empty translations
fail every rule, default judge google/gemini-3.8-flash. The data is a pinned
snapshot of the text-only LTBv1-eval subset (see make_snapshot.py).

The only piece not taken from upstream is the instruction given to the model
under test, since LTB leaderboard submissions bring their own translations.

    inspect eval inspect_eval/ltb.py --model openrouter/google/gemma-4-31b-it
    inspect eval inspect_eval/ltb.py -T judge_model=openai/gpt-6-luna --limit 20
"""

from pathlib import Path
from typing import Any

from inspect_ai import Task, task
from inspect_ai.dataset import Sample, json_dataset
from inspect_ai.model import get_model
from inspect_ai.scorer import (
    Metric,
    SampleScore,
    Score,
    Scorer,
    Target,
    Value,
    metric,
    scorer,
)
from inspect_ai.solver import TaskState, generate

DATA_PATH = Path(__file__).parent / "LTBv1-eval.jsonl"
DEFAULT_JUDGE = "google/gemini-3.8-flash"

TRANSLATE_PROMPT = (
    "Translate the following text from {source_lang} to {target_lang}.\n"
    "Output only the translation, with no explanation or extra text."
)

# verbatim from server/utils.py::get_prompt_verify (text-only branch)
VERIFY_PROMPT = (
    "Your goal is to verify whether a translation fulfills a criterion.\n\n"
    "Criterion: {rule}\n\nInput: {source_text}\n\nTranslation to verify: {translation}\n\n"
    "Output only pass or fail and nothing else."
)


def parse_verify(res_text: str) -> bool:
    """Same pass/fail parse as scripts/41-score_leaderboard.py."""
    tokens = res_text.strip().lower().strip(" \t\n\r.,!?\"'*").split()
    text_clean = tokens[-1] if tokens else ""
    if "pass" in text_clean:
        return True
    if "fail" in text_clean:
        return False
    if "pass" in res_text.lower():
        return True
    if "fail" in res_text.lower():
        return False
    return False


def record_to_sample(r: dict[str, Any]) -> Sample:
    prompt = TRANSLATE_PROMPT.format(source_lang=r["source_lang"], target_lang=r["target_lang"])
    if r["source_instructions"]:
        prompt += f"\n\nAdditional instructions: {r['source_instructions']}"
    return Sample(
        id=r["id"],
        input=f"{prompt}\n\n{r['source_text']}",
        metadata={
            "source_text": r["source_text"],
            "lang_pair": f"{r['source_lang']}->{r['target_lang']}",
            "verification_rules": r["verification_rules"],
            "linguistics": r["linguistics"],
        },
    )


@metric
def pass_rate_by_lang_pair() -> Metric:
    def compute(scores: list[SampleScore]) -> Value:
        by_pair: dict[str, list[float]] = {}
        for s in scores:
            by_pair.setdefault(s.score.metadata["lang_pair"], []).append(s.score.as_float())
        return {pair: sum(v) / len(v) for pair, v in sorted(by_pair.items())}

    return compute


@metric
def pass_rate() -> Metric:
    def compute(scores: list[SampleScore]) -> Value:
        return sum(s.score.as_float() for s in scores) / len(scores)

    return compute


@scorer(metrics=[pass_rate(), pass_rate_by_lang_pair()])
def ltb_verifier(judge_model: str = DEFAULT_JUDGE) -> Scorer:
    """One judge call per verification rule; correct iff all rules pass."""

    async def score(state: TaskState, target: Target) -> Score:
        judge = get_model(role="grader", default=judge_model)
        translation = state.output.completion
        rules = state.metadata["verification_rules"]

        # empty translations fail every rule without a judge call
        if translation == "":
            verdicts = ["(empty translation)"] * len(rules)
            results = [False] * len(rules)
        else:
            verdicts = []
            for rule in rules:
                prompt = VERIFY_PROMPT.format(
                    rule=rule, source_text=state.metadata["source_text"], translation=translation
                )
                verdicts.append((await judge.generate(prompt)).completion)
            results = [parse_verify(v) for v in verdicts]

        return Score(
            value=1 if all(results) else 0,
            answer=translation,
            explanation="\n".join(f"{'PASS' if ok else 'FAIL'}: {rule}" for ok, rule in zip(results, rules)),
            metadata={"lang_pair": state.metadata["lang_pair"], "rule_results": results, "judge_outputs": verdicts},
        )

    return score


@task
def ltb(judge_model: str = DEFAULT_JUDGE) -> Task:
    """LTBv1-eval (911 text-only items). judge_model is overridden by a `grader` model role if given."""
    return Task(
        dataset=json_dataset(str(DATA_PATH), record_to_sample),
        solver=generate(),
        scorer=ltb_verifier(judge_model),
        version="1.0.0",
    )

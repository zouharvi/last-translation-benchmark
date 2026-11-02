from inspect_ai import eval as inspect_eval
from inspect_ai.model import ModelOutput, get_model
from ltb import ltb, parse_verify


def test_parse_verify():
    assert parse_verify("Pass.")
    assert not parse_verify("fail")
    assert parse_verify("The translation is a pass.")
    # the last token decides, as upstream
    assert not parse_verify("Not a pass, it is a fail")
    assert not parse_verify("")


def test_dataset():
    samples = ltb().dataset
    assert len(samples) == 911
    assert all(s.metadata["verification_rules"] for s in samples)


def test_scoring_end_to_end():
    # item is correct only if the judge passes every rule
    target = get_model("mockllm/model", custom_outputs=[ModelOutput.from_content("mockllm/model", "translation")] * 2)
    judge = get_model(
        "mockllm/model",
        custom_outputs=[ModelOutput.from_content("mockllm/model", v) for v in ["pass", "pass", "pass", "fail"]],
    )
    # samples 40 and 63 have two rules each
    [log] = inspect_eval(ltb(), model=target, model_roles={"grader": judge}, sample_id=[40, 63], display="none")
    scores = {s.id: s.scores["ltb_verifier"].value for s in log.samples}
    assert sorted(scores.values()) == [0, 1]

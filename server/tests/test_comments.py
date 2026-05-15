import importlib
from pathlib import Path

import pytest


@pytest.mark.anyio
async def test_contributor_can_comment_without_reviewer_comment(monkeypatch):
    (Path(__file__).resolve().parents[1] / "static").mkdir(exist_ok=True)
    routers = importlib.import_module("server.routers")
    models = importlib.import_module("server.models")

    submission = {
        "id": 32,
        "user_id": 10,
        "created_at": "2026-05-15 17:35:00",
        "reviewer_comment": "",
    }
    saved = {}

    async def fake_get_submission_by_id(_sid: int):
        return submission

    async def fake_save_submission(updated: dict):
        saved["submission"] = updated

    monkeypatch.setattr(routers, "get_submission_by_id", fake_get_submission_by_id)
    monkeypatch.setattr(routers, "save_submission", fake_save_submission)

    user = {"id": 10, "username": "c1", "roles": ["contributor"]}
    response = await routers.add_comment(
        32, models.CommentReq(comment="My note"), user=user
    )

    assert response == {"ok": True}
    assert saved["submission"]["comments"][0]["author"] == "c1"
    assert saved["submission"]["comments"][0]["role"] == "contributor"
    assert saved["submission"]["comments"][0]["text"] == "My note"

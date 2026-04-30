import asyncio
import secrets
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException

from .auth import get_current_user, require_admin
from .db import db_state, next_id, save_data
from .languages import LANGUAGES
from .models import (
    CommentReq,
    CreateUserReq,
    ProfileReq,
    QuotaReq,
    ScoreReq,
    SubmissionReq,
    TranslateReq,
    VerifyReq,
)
from .services import (
    translate_gemini2_5flash,
    translate_gemma4,
    translate_google,
    translate_gpt4p1nano,
    translate_mymemory,
    translate_qwen3p6,
    verify_llm,
)
from .utils import CONTRIBUTOR_QUOTA_DEFAULT

router = APIRouter()

# --- Users ---


@router.get("/api/me")
def me(user=Depends(get_current_user)):
    total_points = sum(
        s["points"]
        for s in db_state["submissions"]
        if s["user_id"] == user["id"] and s["points"] >= 0
    )
    return {
        "username": user["username"],
        "roles": user["roles"],
        "quota": user["quota"],
        "quota_used": user["quota_used"],
        "total_points": total_points,
        "name": user["name"],
        "affiliation": user.get("affiliation", ""),
        "email": user.get("email", ""),
        "credit_consent": user.get("credit_consent", False),
    }


@router.put("/api/profile")
def update_profile(req: ProfileReq, user=Depends(get_current_user)):
    user.update(
        {
            "name": req.name,
            "affiliation": req.affiliation,
            "email": req.email,
            "credit_consent": req.credit_consent,
        }
    )
    save_data()
    return {"ok": True}


def _admin_user_view(u: dict) -> dict:
    return {
        "id": u["id"],
        "username": u["username"],
        "roles": u.get("roles", []),
        "magic_token": u.get("magic_token", ""),
        "name": u.get("name", ""),
        "affiliation": u.get("affiliation", ""),
        "email": u.get("email", ""),
        "credit_consent": u.get("credit_consent", False),
        "quota": u.get("quota", CONTRIBUTOR_QUOTA_DEFAULT),
        "quota_used": u.get("quota_used", 0),
    }


@router.get("/api/admin/users")
def admin_users(user=Depends(get_current_user)):
    require_admin(user)
    return [_admin_user_view(u) for u in db_state["users"]]


@router.post("/api/admin/users", status_code=201)
def admin_create_user(req: CreateUserReq, user=Depends(get_current_user)):
    require_admin(user)
    if not req.username.strip():
        raise HTTPException(status_code=400, detail="Username cannot be empty")
    if any(
        u["username"].lower() == req.username.strip().lower() for u in db_state["users"]
    ):
        raise HTTPException(status_code=409, detail="Username already exists")
    valid_roles = {"admin", "contributor", "reviewer"}
    bad = [r for r in req.roles if r not in valid_roles]
    if bad:
        raise HTTPException(status_code=400, detail=f"Invalid roles: {bad}")
    new_user = {
        "id": next_id(db_state["users"]),
        "username": req.username.strip(),
        "magic_token": secrets.token_urlsafe(24),
        "roles": req.roles,
        "quota": CONTRIBUTOR_QUOTA_DEFAULT,
        "quota_used": 0,
    }
    db_state["users"].append(new_user)
    save_data()
    return _admin_user_view(new_user)


@router.delete("/api/admin/users/{uid}", status_code=200)
def admin_delete_user(uid: int, user=Depends(get_current_user)):
    require_admin(user)
    if user["id"] == uid:
        raise HTTPException(status_code=400, detail="Cannot delete yourself")
    target = next((u for u in db_state["users"] if u["id"] == uid), None)
    if target is None:
        raise HTTPException(status_code=404, detail="User not found")
    db_state["users"] = [u for u in db_state["users"] if u["id"] != uid]
    save_data()
    return {"ok": True}


@router.post("/api/admin/users/{uid}/rotate-token")
def admin_rotate_token(uid: int, user=Depends(get_current_user)):
    require_admin(user)
    target = next((u for u in db_state["users"] if u["id"] == uid), None)
    if target is None:
        raise HTTPException(status_code=404, detail="User not found")
    target["magic_token"] = secrets.token_urlsafe(24)
    save_data()
    return {"magic_token": target["magic_token"]}


@router.post("/api/admin/users/{uid}/adjust-quota")
def admin_adjust_quota(uid: int, req: QuotaReq, user=Depends(get_current_user)):
    require_admin(user)
    target = next((u for u in db_state["users"] if u["id"] == uid), None)
    if target is None:
        raise HTTPException(status_code=404, detail="User not found")
    target["quota"] = max(0, target.get("quota", CONTRIBUTOR_QUOTA_DEFAULT) + req.delta)
    save_data()
    return {"quota": target["quota"], "quota_used": target.get("quota_used", 0)}


# --- Translate ---

NAME_TO_CODE = {x["name"].lower(): x["code"] for x in LANGUAGES}


@router.post("/api/translate-submission")
def translate_submission(req: TranslateReq, user=Depends(get_current_user)):
    if "contributor" not in user.get("roles", []):
        raise HTTPException(
            status_code=403, detail="Only contributors can use translation quota"
        )

    if not req.text or not req.text.strip():
        raise HTTPException(status_code=400, detail="Enter source text first")

    if (
        not req.source_lang
        or not req.source_lang.strip()
        or not req.target_lang
        or not req.target_lang.strip()
    ):
        raise HTTPException(status_code=400, detail="Both languages must be specified")
    if len(req.source_lang) > 50 or len(req.target_lang) > 50:
        raise HTTPException(
            status_code=400, detail="Language has to be at most 50 characters long"
        )

    source_name = req.source_lang
    target_name = req.target_lang
    source_code = NAME_TO_CODE.get(source_name.lower())
    target_code = NAME_TO_CODE.get(target_name.lower())

    quota_used = user["quota_used"]
    quota = user.get("quota", CONTRIBUTOR_QUOTA_DEFAULT)
    if quota_used >= quota:
        raise HTTPException(status_code=429, detail="Quota exceeded")

    async def _run_translate(name: str, func, *args):
        try:
            res = await asyncio.to_thread(func, *args)
            return {"api": name, "translation": res, "error": None}
        except Exception as exc:
            return {"api": name, "translation": None, "error": str(exc)}

    async def _run_all():
        tasks = []
        # Standard services (only if codes exist)
        if source_code and target_code:
            tasks.append(
                _run_translate(
                    "MyMemory",
                    translate_mymemory,
                    req.text,
                    source_code,
                    target_code,
                )
            )
            tasks.append(
                _run_translate(
                    "Google", translate_google, req.text, source_code, target_code
                )
            )

        # LLM services (always use names)
        llm_tasks = [
            _run_translate(
                "Gemini 2.5 Flash Lite",
                translate_gemini2_5flash,
                req.text,
                source_name,
                target_name,
            ),
            _run_translate(
                "Gemma 4",
                translate_gemma4,
                req.text,
                source_name,
                target_name,
            ),
            _run_translate(
                "Qwen 3.6 Plus",
                translate_qwen3p6,
                req.text,
                source_name,
                target_name,
            ),
            _run_translate(
                "GPT-4.1 Nano",
                translate_gpt4p1nano,
                req.text,
                source_name,
                target_name,
            ),
        ]
        tasks.extend(llm_tasks)
        return await asyncio.gather(*tasks)

    results = asyncio.run(_run_all())

    user["quota_used"] = quota_used + 1
    save_data()
    return {"results": results, "quota": quota, "quota_used": quota_used + 1}


@router.post("/api/verify-submission")
def verify_submission(req: VerifyReq, user=Depends(get_current_user)):
    if not req.verification_rules:
        return {"results": [True] * len(req.translations)}

    async def _verify_single(translation: str) -> bool:
        for rule in req.verification_rules:
            if rule.type == "contains":
                if rule.value not in translation:
                    return False
            elif rule.type == "not_contains":
                if rule.value in translation:
                    return False
            elif rule.type == "llm":
                try:
                    res = await asyncio.to_thread(verify_llm, translation, rule.value)
                    if not res:
                        return False
                except Exception as exc:
                    raise HTTPException(status_code=502, detail=f"LLM API error: {exc}")
        return True

    async def _run_verify():
        return await asyncio.gather(*[_verify_single(t) for t in req.translations])

    results = asyncio.run(_run_verify())
    return {"results": results}


# --- Submissions ---


@router.post("/api/submissions")
def create_submission(req: SubmissionReq, user=Depends(get_current_user)):
    if "contributor" not in user.get("roles", []):
        raise HTTPException(
            status_code=403, detail="Only contributors can submit submissions"
        )

    if (
        not req.source_lang
        or not req.source_lang.strip()
        or not req.target_lang
        or not req.target_lang.strip()
        or not req.source_text
        or not req.translations
        or not req.verification_rules
    ):
        raise HTTPException(status_code=400, detail="Field missing")

    sid = next_id(db_state["submissions"])
    db_state["submissions"].append(
        {
            "id": sid,
            "user_id": user["id"],
            "username": user["username"],
            "source_text": req.source_text,
            "source_lang": req.source_lang,
            "target_lang": req.target_lang,
            "verification_rules": [r.model_dump() for r in req.verification_rules],
            "translations": [t.model_dump() for t in req.translations],
            "points": -1,
            "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
        }
    )
    save_data()
    return {"ok": True}


@router.put("/api/submissions/{sid}")
def update_submission(sid: int, req: SubmissionReq, user=Depends(get_current_user)):
    submission = next((s for s in db_state["submissions"] if s["id"] == sid), None)
    if submission is None:
        raise HTTPException(status_code=404, detail="Submission not found")

    if submission["user_id"] != user["id"]:
        raise HTTPException(
            status_code=403, detail="Not authorized to update this submission"
        )

    submission.update(
        {
            "source_text": req.source_text,
            "source_lang": req.source_lang,
            "target_lang": req.target_lang,
            "verification_rules": [r.model_dump() for r in req.verification_rules],
            "translations": [t.model_dump() for t in req.translations],
            "points": -1,  # Reset to pending
            "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
        }
    )
    save_data()
    return {"ok": True}


@router.get("/api/submissions")
def get_submissions(user=Depends(get_current_user)):
    if "reviewer" in user.get("roles", []):
        rows = sorted(
            db_state["submissions"],
            key=lambda s: (s["points"], s["created_at"]),
        )
    else:
        rows = sorted(
            [s for s in db_state["submissions"] if s["user_id"] == user["id"]],
            key=lambda s: s["created_at"],
            reverse=True,
        )

    return rows


@router.post("/api/submissions/{sid}/score")
def score_submission(sid: int, req: ScoreReq, user=Depends(get_current_user)):
    if "reviewer" not in user.get("roles", []):
        raise HTTPException(
            status_code=403, detail="Only reviewer users can score submissions"
        )
    if req.action not in ("reject", "accept", "comment"):
        raise HTTPException(
            status_code=400, detail="Action must be reject, accept, or comment"
        )
    submission = next((s for s in db_state["submissions"] if s["id"] == sid), None)
    if submission is None:
        raise HTTPException(status_code=404, detail="Submission not found")
    if req.action == "accept":
        submission["points"] = 1
    elif req.action == "reject":
        submission["points"] = 0
    else:  # comment — stays pending, stores comment for contributor
        submission["points"] = -1
    submission["reviewer_comment"] = req.comment or ""

    if req.comment:
        if "comments" not in submission:
            submission["comments"] = []
        submission["comments"].append(
            {
                "author": user["username"],
                "role": "reviewer",
                "text": req.comment,
                "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
            }
        )

    save_data()
    return {"ok": True}


@router.post("/api/submissions/{sid}/comment")
def add_comment(sid: int, req: CommentReq, user=Depends(get_current_user)):
    submission = next((s for s in db_state["submissions"] if s["id"] == sid), None)
    if submission is None:
        raise HTTPException(status_code=404, detail="Submission not found")

    is_reviewer = "reviewer" in user.get("roles", [])
    is_owner = submission["user_id"] == user["id"]

    if not (is_reviewer or is_owner):
        raise HTTPException(status_code=403, detail="Not authorized to comment")

    if "comments" not in submission:
        submission["comments"] = []
        if submission.get("reviewer_comment"):
            submission["comments"].append(
                {
                    "author": "Reviewer",
                    "role": "reviewer",
                    "text": submission["reviewer_comment"],
                    "timestamp": submission["created_at"],
                }
            )

    if not is_reviewer and not submission["comments"]:
        raise HTTPException(status_code=403, detail="Reviewer must comment first")

    submission["comments"].append(
        {
            "author": user["username"],
            "role": "reviewer" if is_reviewer else "contributor",
            "text": req.comment,
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
        }
    )

    if is_reviewer:
        submission["points"] = -1
        submission["reviewer_comment"] = req.comment

    save_data()
    return {"ok": True}

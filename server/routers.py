import asyncio
import secrets
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException

from .auth import get_current_user, require_admin
from .db import (
    delete_user,
    get_submission_by_id,
    get_user_by_id,
    get_users,
    next_submission_id,
    next_user_id,
    save_submission,
    save_user,
)
from .db import (
    get_submissions as db_get_submissions,
)
from .models import (
    CommentReq,
    ProfileReq,
    QuotaReq,
    ReviewScopeReq,
    RolesReq,
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
    translate_lara,
    translate_llama4,
    verify_llm,
)
from .utils import CONTRIBUTOR_QUOTA_DEFAULT

router = APIRouter()

# --- Users ---


@router.get("/api/me")
async def me(user=Depends(get_current_user)):
    submissions = await db_get_submissions(user_id=user["id"])
    total_accepted = sum(1 for s in submissions if s.get("points") == 1)
    now = datetime.now(timezone.utc)
    last_active = user.get("last_active", "")
    if (
        not last_active
        or (
            now - datetime.fromisoformat(last_active).replace(tzinfo=timezone.utc)
        ).total_seconds()
        > 300
    ):
        user["last_active"] = now.strftime("%Y-%m-%d %H:%M:%S")
        await save_user(user)
    return {
        "username": user["username"],
        "roles": user["roles"],
        "quota": user["quota"],
        "quota_used": user["quota_used"],
        "total_accepted": total_accepted,
        "total_submitted": len(submissions),
        "name": user.get("name", ""),
        "affiliation": user.get("affiliation", ""),
        "email": user.get("email", ""),
        "credit_consent": user.get("credit_consent", False),
    }


@router.put("/api/profile")
async def update_profile(req: ProfileReq, user=Depends(get_current_user)):
    user.update(
        {
            "name": req.name,
            "affiliation": req.affiliation,
            "email": req.email,
            "credit_consent": req.credit_consent,
        }
    )
    await save_user(user)
    return {"ok": True}


@router.post("/api/register", status_code=201)
async def register_user(req: ProfileReq):
    if not req.name.strip() or not req.email.strip():
        raise HTTPException(status_code=400, detail="Name and email are required")

    users = await get_users()

    # Generate unique username from email prefix
    base_username = req.email.split("@")[0].lower()
    base_username = "".join(c for c in base_username if c.isalnum() or c in "._-")
    if not base_username:
        base_username = "user"

    username = base_username
    counter = 1
    existing_usernames = {u["username"].lower() for u in users}
    while username.lower() in existing_usernames:
        username = f"{base_username}{counter}"
        counter += 1

    new_user = {
        "id": await next_user_id(),
        "username": username,
        "magic_token": secrets.token_urlsafe(24),
        "roles": ["contributor"],
        "quota": CONTRIBUTOR_QUOTA_DEFAULT,
        "quota_used": 0,
        "name": req.name,
        "affiliation": req.affiliation,
        "email": req.email,
        "credit_consent": req.credit_consent,
    }
    await save_user(new_user)
    return {"ok": True}


async def _admin_user_view(u: dict) -> dict:
    submissions = await db_get_submissions(user_id=u["id"])
    total_accepted = sum(1 for s in submissions if s.get("points") == 1)
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
        "review_langs": u.get("review_langs", []),
        "total_accepted": total_accepted,
        "total_submitted": len(submissions),
        "invite_sent": u.get("invite_sent", ""),
        "last_active": u.get("last_active", ""),
    }


@router.get("/api/admin/users")
async def admin_users(user=Depends(get_current_user)):
    require_admin(user)
    users = await get_users()
    return await asyncio.gather(*[_admin_user_view(u) for u in users])


@router.delete("/api/admin/users/{uid}", status_code=200)
async def admin_delete_user(uid: int, user=Depends(get_current_user)):
    require_admin(user)
    if user["id"] == uid:
        raise HTTPException(status_code=400, detail="Cannot delete yourself")
    target = await get_user_by_id(uid)
    if target is None:
        raise HTTPException(status_code=404, detail="User not found")
    await delete_user(uid)
    return {"ok": True}


@router.post("/api/admin/users/{uid}/rotate-token")
async def admin_rotate_token(uid: int, user=Depends(get_current_user)):
    require_admin(user)
    target = await get_user_by_id(uid)
    if target is None:
        raise HTTPException(status_code=404, detail="User not found")
    target["magic_token"] = secrets.token_urlsafe(24)
    await save_user(target)
    return {"magic_token": target["magic_token"]}


@router.post("/api/admin/users/{uid}/mark-invite-sent")
async def admin_mark_invite_sent(uid: int, user=Depends(get_current_user)):
    require_admin(user)
    target = await get_user_by_id(uid)
    if target is None:
        raise HTTPException(status_code=404, detail="User not found")
    target["invite_sent"] = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    await save_user(target)
    return {"invite_sent": target["invite_sent"]}


@router.post("/api/admin/users/{uid}/adjust-quota")
async def admin_adjust_quota(uid: int, req: QuotaReq, user=Depends(get_current_user)):
    require_admin(user)
    target = await get_user_by_id(uid)
    if target is None:
        raise HTTPException(status_code=404, detail="User not found")
    target["quota"] = max(0, target.get("quota", CONTRIBUTOR_QUOTA_DEFAULT) + req.delta)
    await save_user(target)
    return {"quota": target["quota"], "quota_used": target.get("quota_used", 0)}


@router.post("/api/admin/users/{uid}/roles")
async def admin_update_roles(uid: int, req: RolesReq, user=Depends(get_current_user)):
    require_admin(user)
    target = await get_user_by_id(uid)
    if target is None:
        raise HTTPException(status_code=404, detail="User not found")
    valid_roles = {"admin", "contributor", "reviewer"}
    bad = [r for r in req.roles if r not in valid_roles]
    if bad:
        raise HTTPException(status_code=400, detail=f"Invalid roles: {bad}")
    target["roles"] = req.roles
    await save_user(target)
    return await _admin_user_view(target)


@router.post("/api/admin/users/{uid}/review-scope")
async def admin_update_review_scope(
    uid: int, req: ReviewScopeReq, user=Depends(get_current_user)
):
    require_admin(user)
    target = await get_user_by_id(uid)
    if target is None:
        raise HTTPException(status_code=404, detail="User not found")
    target["review_langs"] = req.review_langs
    await save_user(target)
    return await _admin_user_view(target)


def _submission_matches_scope(submission: dict, review_langs: list[str]) -> bool:
    if not review_langs:
        return True
    langs_lower = {lang.lower() for lang in review_langs}
    return (
        submission["source_lang"].lower() in langs_lower
        or submission["target_lang"].lower() in langs_lower
    )


# --- Translate ---


@router.post("/api/translate-submission")
async def translate_submission(req: TranslateReq, user=Depends(get_current_user)):
    if "contributor" not in user.get("roles", []):
        raise HTTPException(
            status_code=403, detail="Only contributors can use translation quota"
        )

    if not req.text and not req.source_media:
        raise HTTPException(
            status_code=400, detail="Enter source text or add media context first"
        )

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

    quota_used = user["quota_used"]
    quota = user.get("quota", CONTRIBUTOR_QUOTA_DEFAULT)
    if quota_used >= quota:
        raise HTTPException(status_code=429, detail="Quota exceeded")

    async def _run_translate(name: str, func, *args):
        try:
            if asyncio.iscoroutinefunction(func):
                res = await func(*args)
            else:
                res = await asyncio.to_thread(func, *args)
            return {"api": name, "translation": res, "error": None}
        except Exception as exc:
            # skip unsupported models
            if str(exc).startswith("No endpoint found that support input"):
                return {"api": name, "translation": None, "error": None}
            return {"api": name, "translation": None, "error": str(exc)}

    tasks = [
        _run_translate("Lara", translate_lara, req.text, source_name, target_name),
        _run_translate("Google", translate_google, req.text, source_name, target_name),
        _run_translate(
            "Gemini 2.5 Flash",
            translate_gemini2_5flash,
            req.text,
            source_name,
            target_name,
            req.source_media,
        ),
        _run_translate(
            "Gemma 4",
            translate_gemma4,
            req.text,
            source_name,
            target_name,
            req.source_media,
        ),
        _run_translate(
            "Llama 4 Scout",
            translate_llama4,
            req.text,
            source_name,
            target_name,
            req.source_media,
        ),
        _run_translate(
            "GPT-4.1 Nano",
            translate_gpt4p1nano,
            req.text,
            source_name,
            target_name,
            req.source_media,
        ),
    ]
    results = await asyncio.gather(*tasks)

    # filter out translations that did not pass because of language incompatibility
    results = [
        r for r in results if r["translation"] is not None or r["error"] is not None
    ]

    user["quota_used"] = quota_used + 1
    await save_user(user)
    return {"results": results, "quota": quota, "quota_used": quota_used + 1}


@router.post("/api/verify-submission")
async def verify_submission(req: VerifyReq, user=Depends(get_current_user)):
    if not req.verification_rules:
        return {"results": [True] * len(req.translations)}

    async def _verify_single(
        source_text: str, translation: str, source_media: str = None
    ) -> bool:
        for rule in req.verification_rules:
            try:
                res = await verify_llm(req.source_text, translation, rule.value)
                if not res:
                    return False
            except Exception as exc:
                raise HTTPException(status_code=502, detail=f"LLM API error: {exc}")
        return True

    results = await asyncio.gather(
        *[
            _verify_single(req.source_text, t, req.source_media)
            for t in req.translations
        ]
    )
    return {"results": results}


# --- Submissions ---


@router.post("/api/submissions")
async def create_submission(req: SubmissionReq, user=Depends(get_current_user)):
    if "contributor" not in user.get("roles", []):
        raise HTTPException(
            status_code=403, detail="Only contributors can submit submissions"
        )

    if (
        not req.source_lang
        or not req.source_lang.strip()
        or not req.target_lang
        or not req.target_lang.strip()
        or not (req.source_text or req.source_media)
        or not req.translations
        or not req.verification_rules
    ):
        raise HTTPException(status_code=400, detail="Field missing")

    sid = await next_submission_id()
    submission = {
        "id": sid,
        "user_id": user["id"],
        "username": user["username"],
        "source_text": req.source_text,
        "source_media": req.source_media,
        "source_lang": req.source_lang,
        "target_lang": req.target_lang,
        "verification_rules": [r.model_dump() for r in req.verification_rules],
        "translations": [t.model_dump() for t in req.translations],
        "points": -1,
        "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
    }
    await save_submission(submission)
    return {"ok": True}


@router.put("/api/submissions/{sid}")
async def update_submission(
    sid: int, req: SubmissionReq, user=Depends(get_current_user)
):
    submission = await get_submission_by_id(sid)
    if submission is None:
        raise HTTPException(status_code=404, detail="Submission not found")

    if submission["user_id"] != user["id"]:
        raise HTTPException(
            status_code=403, detail="Not authorized to update this submission"
        )

    update: dict = {
        "source_text": req.source_text,
        "source_lang": req.source_lang,
        "target_lang": req.target_lang,
        "verification_rules": [r.model_dump() for r in req.verification_rules],
        "translations": [t.model_dump() for t in req.translations],
        "points": -1,
        "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
    }
    if req.source_media is not None:
        update["source_media"] = req.source_media
    submission.update(update)
    await save_submission(submission)
    return {"ok": True}


@router.get("/api/submissions")
async def list_submissions(user=Depends(get_current_user), mode: str = "contributor"):
    if mode == "reviewer" and "reviewer" in user.get("roles", []):
        rows = sorted(
            await db_get_submissions(),
            key=lambda s: (s["points"], s["created_at"]),
        )
        review_langs = user.get("review_langs", [])
        if review_langs:
            rows = [s for s in rows if _submission_matches_scope(s, review_langs)]
    else:
        rows = sorted(
            await db_get_submissions(user_id=user["id"]),
            key=lambda s: s["created_at"],
            reverse=True,
        )
    return rows


@router.post("/api/submissions/{sid}/score")
async def score_submission(sid: int, req: ScoreReq, user=Depends(get_current_user)):
    if "reviewer" not in user.get("roles", []):
        raise HTTPException(
            status_code=403, detail="Only reviewer users can score submissions"
        )
    if req.action not in ("reject", "accept", "comment"):
        raise HTTPException(
            status_code=400, detail="Action must be reject, accept, or comment"
        )
    submission = await get_submission_by_id(sid)
    if submission is None:
        raise HTTPException(status_code=404, detail="Submission not found")
    if req.action == "accept":
        submission["points"] = 1
    elif req.action == "reject":
        submission["points"] = 0
    else:
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

    await save_submission(submission)
    return {"ok": True}


@router.post("/api/submissions/{sid}/comment")
async def add_comment(sid: int, req: CommentReq, user=Depends(get_current_user)):
    submission = await get_submission_by_id(sid)
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

    await save_submission(submission)
    return {"ok": True}

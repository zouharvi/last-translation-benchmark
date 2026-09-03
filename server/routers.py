import asyncio
import collections
import functools
import inspect
import json
import os
import random
import secrets
import statistics
import sys
import time
from datetime import UTC, datetime
from typing import Annotated, Literal

import cohere
import jsonschema
import openrouter.errors
from fastapi import APIRouter, Body, Depends, HTTPException, Query, Response

from .auth import get_current_user, require_role
from .db import (
    create_leaderboard_entry,
    delete_leaderboard_entry,
    delete_submission,
    delete_user,
    get_latest_sent_email_date,
    get_leaderboard_entries,
    get_leaderboard_entry,
    get_submission_by_id,
    get_user_by_id,
    get_user_by_username,
    get_users,
    save_submission,
    save_user,
    update_leaderboard_entry,
    update_leaderboard_info,
)
from .db import (
    create_submission as db_create_submission,
)
from .db import (
    create_user as db_create_user,
)
from .db import (
    get_submissions as db_get_submissions,
)
from .models import (
    APILLMReq,
    CommentReq,
    LeaderboardInfoUpdateReq,
    LeaderboardSubmitReq,
    LeaderboardUpdateReq,
    NotificationActionReq,
    ProfileReq,
    QuotaReq,
    RecoverLinkReq,
    ReviewScopeReq,
    RolesReq,
    ScoreReq,
    SubmissionReq,
    TranslateReq,
    VerifyReq,
)
from .services import (
    call_llm_multimodal,
    translate_google_with_api,
    translate_lara,
    translate_openrouter,
    verify_llm,
)
from .utils import CONTRIBUTOR_QUOTA_DEFAULT, join_english, send_email, simple_lang

router = APIRouter()
CurrentUser = Annotated[dict, Depends(get_current_user)]
REVIEW_REMINDER_SUBJECT = "Last Translation Benchmark - Review Request"

# --- Users ---


@router.get("/api/me")
async def me(user: CurrentUser):
    submissions = await db_get_submissions(user_id=user["id"])
    total_accepted = sum(1 for s in submissions if s["status"] == "accept")
    return {
        "username": user["username"],
        "roles": user["roles"],
        "quota": user["quota"],
        "quota_used": user["quota_used"],
        "total_accepted": total_accepted,
        "total_submitted": len(submissions),
        "name": user["name"],
        "affiliation": user["affiliation"],
        "email": user["email"],
        "credit_consent": user["credit_consent"],
        "notification_consent": user["notification_consent"],
        "notifications": user["notifications"],
        "review_langs": user.get("review_langs", []),
    }


@router.put("/api/profile")
async def update_profile(req: ProfileReq, user: CurrentUser):
    if not req.name.strip() or not req.email.strip():
        raise HTTPException(status_code=400, detail="Name and email are required")
    new_email = req.email.strip().lower()
    if new_email != user["email"].strip().lower():
        users = await get_users()
        if any(
            u["email"].strip().lower() == new_email
            for u in users
            if u["id"] != user["id"]
        ):
            raise HTTPException(status_code=400, detail="Email already taken")

    user.update(
        {
            "name": req.name,
            "affiliation": req.affiliation,
            "email": req.email,
            "credit_consent": req.credit_consent,
            "notification_consent": req.notification_consent,
        }
    )
    await save_user(user)
    return {"ok": True}


@router.post("/api/register", status_code=201)
async def register_user(req: ProfileReq, response: Response):
    if not req.name.strip() or not req.email.strip():
        raise HTTPException(status_code=400, detail="Name and email are required")

    users = await get_users()

    # Check if email already exists
    if any(u["email"].strip().lower() == req.email.strip().lower() for u in users):
        raise HTTPException(status_code=400, detail="User already registered")

    # Generate username from name: First_Last
    parts = req.name.strip().split()
    base_username = "_".join(part.capitalize() for part in parts)
    base_username = "".join(c for c in base_username if c.isalnum() or c == "_")[:50]
    if not base_username:
        raise HTTPException(status_code=400, detail="Invalid name for username generation")

    username = base_username
    suffix = 2
    while True:
        # Check if username already exists
        if all(u["username"] != username for u in users):
            break

        username = f"{base_username}_{suffix}"
        suffix += 1

    new_user = {
        "username": username,
        "magic_token": secrets.token_urlsafe(24),
        "roles": ["contributor"],
        "quota": CONTRIBUTOR_QUOTA_DEFAULT,
        "quota_used": 0,
        "name": req.name,
        "affiliation": req.affiliation,
        "email": req.email,
        "credit_consent": req.credit_consent,
        "notification_consent": req.notification_consent,
        "notifications": [],
        "review_langs": [],
        "last_active": "",
    }
    # Send registration email directly
    host_public = os.getenv("HOST_PUBLIC") or ""
    host_url = host_public.rstrip("/")
    link = f"{host_url}/?user={username}&token={new_user['magic_token']}"
    email_body = f"""Dear {req.name},

Thank you for registering for the Last Translation Benchmark.

Use this passwordless login link to access the platform and submit hard-to-translate inputs:
{link}

Please make sure that you read the instructions in detail.
Let us know if you have any questions or need to increase your quota.

Best regards, the LTB Team"""

    email_success = await send_email(
        to_email=req.email,
        subject="Last Translation Benchmark - Login Link",
        body=email_body,
        user_obj=new_user,
    )
    
    if not email_success:
        raise HTTPException(status_code=500, detail="Failed to send registration email. Please try again later.")

    await db_create_user(new_user)

    max_age = 10 * 365 * 24 * 60 * 60
    import urllib.parse
    response.set_cookie(key="ltb_user", value=urllib.parse.quote(username), max_age=max_age, path="/", samesite="strict")
    response.set_cookie(key="ltb_token", value=urllib.parse.quote(new_user['magic_token']), max_age=max_age, path="/", samesite="strict")

    return {"ok": True}


@router.post("/api/recover-link")
async def recover_link(req: RecoverLinkReq):
    users = await get_users()
    target_email = req.email.strip().lower()

    for user in users:
        if user["email"].strip().lower() == target_email:
            host_url = (os.getenv("HOST_PUBLIC") or "").rstrip("/")
            link = f"{host_url}/?user={user['username']}&token={user['magic_token']}"
            email_body = f"""Dear {user['name']},

You requested a login link for the Last Translation Benchmark.

Use this passwordless login link to access the platform:
{link}

Best regards, the LTB Team"""
            asyncio.create_task(send_email(
                to_email=target_email,
                subject="Last Translation Benchmark - Login Link",
                body=email_body,
                user_obj=user,
            ))
            break

    return {"ok": True}


@router.get("/api/unsubscribe")
async def unsubscribe(user: str, token: str):
    u = await get_user_by_username(user)
    if u is None or not secrets.compare_digest(u["magic_token"], token):
        raise HTTPException(status_code=400, detail="Invalid unsubscribe link")

    u["notification_consent"] = False
    await save_user(u)

    return {"ok": True, "message": "Successfully unsubscribed"}


async def _admin_user_view(u: dict) -> dict:
    submissions = await db_get_submissions(user_id=u["id"])
    total_accepted = sum(1 for s in submissions if s["status"] == "accept")
    return {
        "id": u["id"],
        "username": u["username"],
        "roles": u["roles"],
        "magic_token": u["magic_token"],
        "name": u["name"],
        "affiliation": u["affiliation"],
        "email": u["email"],
        "credit_consent": u["credit_consent"],
        "notification_consent": u["notification_consent"],
        "quota": u["quota"],
        "quota_used": u["quota_used"],
        "review_langs": u["review_langs"],
        "total_accepted": total_accepted,
        "total_submitted": len(submissions),
        "last_active": u["last_active"],
    }


@router.post("/api/llm")
async def api_call_llm(req: APILLMReq, user: CurrentUser):
    require_role(user, "api")
    
    quota = user["quota"]
    quota_used = user["quota_used"]
    if quota_used >= quota:
        raise HTTPException(status_code=429, detail="Quota exceeded")

    user["quota_used"] = quota_used + 0.1
    await save_user(user)

    try:    
        result = await call_llm_multimodal(
            prompt=req.prompt, model=req.model, source_media=req.source_media, cache=req.cache
        )
    except openrouter.errors.TooManyRequestsResponseError:
        raise HTTPException(status_code=429, detail=f"Too many requests to OpenRouter/{req.model}. Please try again later.")
    except cohere.errors.too_many_requests_error.TooManyRequestsError:
        raise HTTPException(status_code=429, detail=f"Too many requests to Cohere/{req.model}. Please try again later.")
    except openrouter.errors.ResponseValidationError:
        raise HTTPException(status_code=418, detail=f"Response validation error from OpenRouter/{req.model}.")
    except openrouter.errors.BadRequestResponseError as exc:
        raise HTTPException(status_code=418, detail=f"Bad response to OpenRouter/{req.model}. {exc}")
    except openrouter.errors.UnprocessableEntityResponseError as exc:
        raise HTTPException(status_code=418, detail=f"Unprocessable entity for OpenRouter/{req.model}. {exc}")
    except openrouter.errors.NotFoundResponseError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    
    return result

@router.get("/api/admin")
async def admin_overview(user: CurrentUser):
    require_role(user, "admin")
    users = await get_users()
    submissions = await db_get_submissions()

    submissions_total = {}
    for sub in submissions:
        submissions_total[sub["status"]] = submissions_total.get(sub["status"], 0) + 1

    submissions_pending = [x for x in submissions if x["status"] == "pending"]
    username_to_name = {x["username"]: x["name"] for x in users}
    
    review_suggestions_by_user = {}
    covered_submissions = set()

    users_without_scope = {u["username"] for u in users if not u.get("review_langs")}
    user_submissions_langs = collections.defaultdict(set)
    if users_without_scope:
        for sub in submissions:
            if sub["username"] in users_without_scope:
                user_submissions_langs[sub["username"]].add(sub["source_lang"])
                user_submissions_langs[sub["username"]].add(sub["target_lang"])

    for u in users:
        if u["roles"] == ["api"]:
            continue
        u_username = u["username"]
        langs = {"English"}
        if u.get("review_langs"):
            langs |= {lang for lang in u["review_langs"]}
        else:
            langs |= user_submissions_langs.get(u_username, set()).copy()
        langs_noenglish = langs - {"English"}

        feasible_bothmatch = [
            x for x in submissions_pending
            if x["username"] != u_username and (
                (x["source_lang"] in langs or any(lang in x["source_lang"] for lang in langs)) and
                (x["target_lang"] in langs or any(lang in x["target_lang"] for lang in langs))
            )
        ]
        feasible_singlematch = [
            x for x in submissions_pending
            if x["username"] != u_username and (
                (x["source_lang"] in langs_noenglish or any(lang in x["source_lang"] for lang in langs_noenglish)) or
                (x["target_lang"] in langs_noenglish or any(lang in x["target_lang"] for lang in langs_noenglish))
            )
        ]
        if feasible_bothmatch:
            review_suggestions_by_user[u_username] = []
            for f in feasible_bothmatch:
                review_suggestions_by_user[u_username].append({
                    "id": f["id"],
                    "source_lang": f["source_lang"],
                    "target_lang": f["target_lang"],
                    "username": f["username"],
                    "name": username_to_name.get(f["username"])
                })
        for f in feasible_singlematch:
            covered_submissions.add(f["id"])

    submissions_without_reviewer = []
    for sub in submissions_pending:
        if sub["id"] not in covered_submissions:
            submissions_without_reviewer.append({
                "id": sub["id"],
                "source_lang": sub["source_lang"],
                "target_lang": sub["target_lang"],
                "username": sub["username"],
                "name": username_to_name.get(sub["username"])
            })

    user_submissions = {}
    for sub in submissions:
        user_submissions.setdefault(sub["user_id"], []).append(sub)

    user_views = []
    for u in users:
        u_subs = user_submissions.get(u["id"], [])
        total_accepted = sum(1 for s in u_subs if s["status"] == "accept")
        view = {
            "id": u["id"],
            "username": u["username"],
            "roles": u["roles"],
            "magic_token": u["magic_token"],
            "name": u["name"],
            "affiliation": u["affiliation"],
            "email": u["email"],
            "credit_consent": u["credit_consent"],
            "notification_consent": u["notification_consent"],
            "quota": u["quota"],
            "quota_used": u["quota_used"],
            "review_langs": u["review_langs"],
            "total_accepted": total_accepted,
            "total_submitted": len(u_subs),
            "last_active": u["last_active"],
            "review_suggestions": review_suggestions_by_user.get(u["username"], []),
        }
        user_views.append(view)

    pending_languages = {}
    for sub in submissions_pending:
        langs = {sub["source_lang"], sub["target_lang"]}
        for lang in langs:
            pending_languages[lang] = pending_languages.get(lang, 0) + 1

    return {
        "users": user_views,
        "submissions_without_reviewer": submissions_without_reviewer,
        "submissions_total": submissions_total,
        "pending_languages": pending_languages,
    }


@router.get("/api/contributors")
async def get_contributors():
    users = await get_users()
    submissions = await db_get_submissions()
    submissions = [s for s in submissions if s.get("status") == "accept"]

    total_submissions = len(submissions)
    total_authors = len({s["user_id"] for s in submissions})

    language_counts = {}
    for s in submissions:
        lang_src = simple_lang(s["source_lang"])
        if lang_src:
            language_counts[lang_src] = language_counts.get(lang_src, 0) + 1
        lang_tgt = simple_lang(s["target_lang"])
        if lang_tgt:
            language_counts[lang_tgt] = language_counts.get(lang_tgt, 0) + 1

    sorted_languages = sorted(language_counts.items(), key=lambda x: x[1], reverse=True)
    formatted_languages = [[lang, count] for lang, count in sorted_languages]

    user_to_accepted: dict[int, int] = collections.defaultdict(int)
    for submission in submissions:
        user_to_accepted[submission["user_id"]] += 1

    users_by_id = {u["id"]: u for u in users if isinstance(u["id"], int)}
    rows: list[dict] = []
    anonymous_submissions = 0
    anonymous_users = set()
    anonymous_affiliations = set()

    total_authors = len(user_to_accepted.keys())

    for user_id, accepted in user_to_accepted.items():
        user = users_by_id.get(user_id)
        # We keep submissions of deleted users, so user might be None.
        # In that case, default to anonymous (credit_consent=False).
        credit_consent = user["credit_consent"] if user else False

        if accepted < 10:
            continue

        if credit_consent and user:
            rows.append(
                {
                    "name": user["name"],
                    "affiliation": user["affiliation"],
                    "accepted_submissions": accepted,
                    "user_id": user_id,
                }
            )
        else:
            anonymous_submissions += accepted
            anonymous_users.add(user_id)
            if user and user.get("affiliation", ""):
                anonymous_affiliations.add(user["affiliation"].strip())
            else:
                anonymous_affiliations.add(f"empty_{user_id}")

    if anonymous_submissions > 0:
        rows.append(
            {
                "name": f"Anonymous ({len(anonymous_users)} users)",
                "affiliation": f"Multiple affiliations ({len(anonymous_affiliations)})",
                "accepted_submissions": anonymous_submissions,
                "user_id": 0,
            }
        )

    rows.sort(
        key=lambda row: (
            int(row["accepted_submissions"]),
            -row["user_id"],
        ),
        reverse=True,
    )
    return {
        "rows": rows,
        "total_submissions": total_submissions,
        "total_authors": total_authors,
        "languages": formatted_languages,
    }


@router.delete("/api/admin/users/{uid}", status_code=200)
async def admin_delete_user(uid: int, user: CurrentUser):
    require_role(user, "admin")
    if user["id"] == uid:
        raise HTTPException(status_code=400, detail="Cannot delete yourself")
    target = await get_user_by_id(uid)
    if target is None:
        raise HTTPException(status_code=404, detail="User not found")
    await delete_user(uid)
    return {"ok": True}


@router.post("/api/admin/users/{uid}/adjust-quota")
async def admin_adjust_quota(uid: int, req: QuotaReq, user: CurrentUser):
    require_role(user, "admin")
    target = await get_user_by_id(uid)
    if target is None:
        raise HTTPException(status_code=404, detail="User not found")
    target["quota"] = max(0, target["quota"] + req.delta)
    await save_user(target)
    return {"quota": target["quota"], "quota_used": target["quota_used"]}


@router.post("/api/admin/users/{uid}/roles")
async def admin_update_roles(uid: int, req: RolesReq, user: CurrentUser):
    require_role(user, "admin")
    target = await get_user_by_id(uid)
    if target is None:
        raise HTTPException(status_code=404, detail="User not found")
    valid_roles = {"admin", "reviewer", "contributor", "api"}
    bad = [r for r in req.roles if r not in valid_roles]
    if bad:
        raise HTTPException(status_code=400, detail=f"Invalid roles: {bad}")
    target["roles"] = req.roles
    await save_user(target)
    return await _admin_user_view(target)


@router.post("/api/admin/users/{uid}/review-scope")
async def admin_update_review_scope(
    uid: int, req: ReviewScopeReq, user: CurrentUser
):
    require_role(user, "admin")
    target = await get_user_by_id(uid)
    if target is None:
        raise HTTPException(status_code=404, detail="User not found")
    target["review_langs"] = req.review_langs
    await save_user(target)
    return await _admin_user_view(target)


@router.get("/api/admin/users/{uid}/prepare-review-reminder")
async def admin_prepare_review_reminder(uid: int, user: CurrentUser):
    require_role(user, "admin")
    target = await get_user_by_id(uid)
    if target is None:
        raise HTTPException(status_code=404, detail="User not found")
    if not target["notification_consent"]:
        raise HTTPException(status_code=400, detail="User has disabled notifications")

    submissions = await db_get_submissions()

    if "reviewer" in target["roles"]:
        submissions_pending = [x for x in submissions if x["status"] == "pending"]
        langs = {"English"}
        if target["review_langs"]:
            langs |= {lang for lang in target["review_langs"]}
        else:
            for sub in submissions:
                if sub["username"] == target["username"]:
                    langs.add(sub["source_lang"])
                    langs.add(sub["target_lang"])

        feasible = [
            x for x in submissions_pending
            if x["username"] != target["username"] and (
                (x["source_lang"] in langs or any(lang in x["source_lang"] for lang in langs)) and
                (x["target_lang"] in langs or any(lang in x["target_lang"] for lang in langs))
            )
        ]

        host_url = (os.getenv("HOST_PUBLIC") or "").rstrip("/")
        ex_lines = [
            f"- #{f['id']} {f['source_lang']} -> {f['target_lang']}: {f['source_text'][:50].replace('\n', ' ')}{'...' if len(f['source_text']) > 50 else ''}"
            for f in feasible
        ]
        ex_lines_i = random.sample(range(len(ex_lines)), min(len(ex_lines), 10))
        ex_lines_i.sort()
        ex_lines = [ex_lines[i] for i in ex_lines_i]
        ex_text = "\n".join(ex_lines)
        if len(feasible) > 10:
            ex_text += f"\n...and {len(feasible) - 10} more submissions."

        
        body = (
            f"Dear {target['name']},\n\nThank you for your contributions so far! We would like to ask you to review a few examples in the Last Translation Benchmark made by other contributors in {join_english(list(langs))} (or other languages you might know --- let us know). "
            f"As a small incentive, active and quality reviewers are prioritized in the coauthor list ranking. Review link: {host_url}/review?user={target['username']}&token={target['magic_token']}\n\n{ex_text}\n\n"
            f"Please be thorough in your reviews and reach out with any questions.\nThank you, {user['name'].split(' ')[0]} & the LTB team"
        )
    else:
        user_langs = set()
        for sub in submissions:
            if sub["username"] == target["username"]:
                user_langs.add(simple_lang(sub["source_lang"]))
                user_langs.add(simple_lang(sub["target_lang"]))
        
        user_langs.discard("English")
                
        body = (
            f"Dear {target['name']},\n\nThank you for your contributions so far! It's taking us a while to review your Last Translation Benchmark submissions. "
            f"We currently do not have many reviewers for {join_english(list(user_langs))}, and we wanted to ask if you know anyone who would be willing to submit a few examples and later review for these languages as well.\n\n"
            "Also, if you are interested in reviewing, that would be amazing! In this case, please let us know which languages you feel comfortable reviewing. "
            "If you do not know potential other reviewers and do not want to review yourself, there is no need to respond to this email.\n\n"
            f"Thank you, {user['name'].split(' ')[0]} & the LTB team"
        )
    last_reminder = await get_latest_sent_email_date(target["email"], REVIEW_REMINDER_SUBJECT)
    
    return {
        "email_body": body,
        "last_review_reminder": last_reminder
    }


@router.post("/api/admin/users/{uid}/send-review-reminder")
async def admin_send_review_reminder(uid: int, user: CurrentUser, email_body: Annotated[str, Body(embed=True)]):
    require_role(user, "admin")
    target = await get_user_by_id(uid)
    if target is None:
        raise HTTPException(status_code=404, detail="User not found")
    if not target["notification_consent"]:
        raise HTTPException(status_code=400, detail="User has disabled notifications")

    success = await send_email(
        to_email=target.get("email", ""),
        subject=REVIEW_REMINDER_SUBJECT,
        body=email_body,
        user_obj=target,
    )
    if not success:
        raise HTTPException(status_code=500, detail="Failed to send email")

    return await _admin_user_view(target)


@router.get("/api/admin/download-users")
async def admin_download_users(user: CurrentUser):
    require_role(user, "admin")
    users = await get_users()
    content = json.dumps(users, indent=2, ensure_ascii=False)
    return Response(
        content=content,
        media_type="application/json",
        headers={"Content-Disposition": "attachment; filename=users.json"}
    )


@router.get("/api/admin/download-submissions")
async def admin_download_submissions(user: CurrentUser):
    require_role(user, "admin")
    submissions = await db_get_submissions()
    content = json.dumps(submissions, indent=2, ensure_ascii=False)
    return Response(
        content=content,
        media_type="application/json",
        headers={"Content-Disposition": "attachment; filename=submissions.json"}
    )


def _submission_matches_scope(submission: dict, review_langs: set[str]) -> bool:
    if not review_langs:
        return True
    source_lang = submission["source_lang"]
    target_lang = submission["target_lang"]

    source_lang_mine = any(source_lang in lang or lang in source_lang for lang in review_langs)
    target_lang_mine = any(target_lang in lang or lang in target_lang for lang in review_langs)
    return (
        source_lang_mine or target_lang_mine
        or
        ("English" in source_lang and "English" in target_lang)
    )


def _filter_reviewer_submissions(
    rows: list[dict],
    status: str,
    source_langs: list[str],
    target_langs: list[str],
    username: str,
    min_rules: int = 0,
    min_pass_rate: float = 0.0,
    min_avg_pass_rate: float = 0.0,
    min_rule_length: int = 0,
    max_rule_length: int = 0,
) -> list[dict]:
    if status == "pending":
        rows = [s for s in rows if s["status"] == "pending"]
    elif status == "accepted_or_returned":
        rows = [s for s in rows if s["status"] in ("accept", "return")]
    elif status == "accepted":
        rows = [s for s in rows if s["status"] == "accept"]
    elif status == "returned":
        rows = [s for s in rows if s["status"] == "return"]
    if source_langs:
        s_lower = {lang for lang in source_langs}
        rows = [
            sub for sub in rows
            if any(lang in sub["source_lang"] for lang in s_lower)
        ]
    if target_langs:
        t_lower = {lang for lang in target_langs}
        rows = [
            sub for sub in rows
            if any(lang in sub["target_lang"] for lang in t_lower)
        ]
    if username:
        rows = [s for s in rows if s["username"] == username]

    if min_rules > 0:
        rows = [s for s in rows if len(s["verification_rules"]) >= min_rules]

    if min_pass_rate > 0.0:
        passed_rows = []
        # find submissions with at least one rule that has a pass rate >= min_pass_rate
        for s in rows:
            for rule_i in range(len(s["translations"][0]["verified"])):
                pass_rate = statistics.mean([
                    t["verified"][rule_i] for t in s["translations"]
                    if len(t["verified"]) > rule_i
                ])
                if pass_rate >= min_pass_rate:
                    passed_rows.append(s)
                    break

        rows = passed_rows

    if min_avg_pass_rate > 0.0:
        passed_rows = []
        for s in rows:
            avg_checks = statistics.mean([v for t in s["translations"] for v in t["verified"]])
            if avg_checks >= min_avg_pass_rate:
                passed_rows.append(s)
        rows = passed_rows
    if min_rule_length > 0:
        rows = [s for s in rows if any(len(r) >= min_rule_length for r in s["verification_rules"])]

    if max_rule_length > 0:
        rows = [s for s in rows if any(len(r) <= max_rule_length for r in s["verification_rules"])]

    return rows


# --- Translate ---

MODEL_LIBRARY = [
    {"name": "Lara", "fn": translate_lara, "support_image": True, "support_audio": False, "support_video": False, "support_textonly": True},
    {"name": "Google Translate", "fn": translate_google_with_api, "support_image": False, "support_audio": False, "support_video": False, "support_textonly": True},
    {"name": "Gemini 3.1 Pro", "fn": functools.partial(translate_openrouter, model="google/gemini-3.1-pro-preview"), "support_image": True, "support_audio": True, "support_video": True, "support_textonly": True},
    {"name": "Gemma 4", "fn": functools.partial(translate_openrouter, model="google/gemma-4-31b-it"), "support_image": True, "support_audio": True, "support_video": True, "support_textonly": True},
    {"name": "Llama 4 Maverick", "fn": functools.partial(translate_openrouter, model="meta-llama/llama-4-maverick"), "support_image": True, "support_audio": False, "support_video": False, "support_textonly": True},
    {"name": "GPT-5.4 Mini", "fn": functools.partial(translate_openrouter, model="openai/gpt-5.4-mini"), "support_image": True, "support_audio": False, "support_video": False, "support_textonly": True},
    {"name": "GPT-5.6 Sol", "fn": functools.partial(translate_openrouter, model="openai/gpt-5.6-sol"), "support_image": True, "support_audio": False, "support_video": False, "support_textonly": True},
    {"name": "Deepseek V4 Pro", "fn": functools.partial(translate_openrouter, model="deepseek/deepseek-v4-pro"), "support_image": True, "support_audio": False, "support_video": False, "support_textonly": True},
    {"name": "Claude Sonnet 4.5", "fn": functools.partial(translate_openrouter, model="anthropic/claude-sonnet-4.5"), "support_image": True, "support_audio": False, "support_video": False, "support_textonly": True},
    {"name": "Gemini 3.7 Flash", "fn": functools.partial(translate_openrouter, model="google/gemini-3.7-flash"), "support_image": True, "support_audio": True, "support_video": True, "support_textonly": False},
    {"name": "Gemini 3.5 Flash Lite", "fn": functools.partial(translate_openrouter, model="google/gemini-3.5-flash-lite"), "support_image": True, "support_audio": True, "support_video": True, "support_textonly": True},
    {"name": "Qwen 3.7 Plus", "fn": functools.partial(translate_openrouter, model="qwen/qwen3.7-plus"), "support_image": False, "support_audio": False, "support_video": True, "support_textonly": False},
    {"name": "Voxtral Small", "fn": functools.partial(translate_openrouter, model="mistralai/voxtral-small-24b-2507"), "support_image": False, "support_audio": True, "support_video": False, "support_textonly": False},
    {"name": "GPT Audio", "fn": functools.partial(translate_openrouter, model="openai/gpt-audio"), "support_image": False, "support_audio": True, "support_video": False, "support_textonly": False},
    {"name": "GPT Audio Mini", "fn": functools.partial(translate_openrouter, model="openai/gpt-audio-mini"), "support_image": False, "support_audio": True, "support_video": False, "support_textonly": False},
    {"name": "Claude Haiku 4.5", "fn": functools.partial(translate_openrouter, model="anthropic/claude-haiku-4.5"), "support_image": True, "support_audio": False, "support_video": False, "support_textonly": True},
    # capped
    # {"name": "TinyAya Global", "fn": functools.partial(translate_openrouter, model="cohere/tiny-aya-global"), "support_image": False, "support_audio": False, "support_video": False, "support_textonly": True},
    # {"name": "Command A+", "fn": functools.partial(translate_openrouter, model="cohere/command-a-plus-05-2026"), "support_image": True, "support_audio": False, "support_video": False, "support_textonly": True},
    # not used anymore
    # {"name": "Gemini 2.5 Pro", "fn": functools.partial(translate_openrouter, model="google/gemini-2.5-pro"), "support_image": False, "support_audio": True, "support_video": True, "support_textonly": False},
    # {"name": "Command A", "fn": functools.partial(translate_openrouter, model="cohere/command-a"), "support_image": True, "support_audio": False, "support_video": False, "support_textonly": True},
    # {"name": "Gemini 2.5 Flash", "fn": functools.partial(translate_openrouter, model="google/gemini-2.5-flash"), "support_image": True, "support_audio": True, "support_video": True, "support_textonly": True},
]


@router.post("/api/translate-submission")
async def translate_submission(req: TranslateReq, user: CurrentUser):
    if not req.text and not req.source_media:
        raise HTTPException(
            status_code=400, detail="Enter source text or add media first"
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
    quota = user["quota"]
    if quota_used >= quota:
        raise HTTPException(status_code=429, detail="Quota exceeded")

    user["quota_used"] = quota_used + 1
    await save_user(user)

    async def _run_translate(
        name: str,
        func,
        text: str,
        src_lang: str,
        tgt_lang: str,
        source_media: str | None = None,
        source_instructions: str | None = None,
    ):
        time_start = time.time()
        try:
            if inspect.iscoroutinefunction(func):
                res = await func(
                    text=text,
                    src_lang=src_lang,
                    tgt_lang=tgt_lang,
                    source_media=source_media,
                    source_instructions=source_instructions,
                )
            else:
                res = await asyncio.to_thread(
                    func,
                    text=text,
                    src_lang=src_lang,
                    tgt_lang=tgt_lang,
                    source_media=source_media,
                    source_instructions=source_instructions,
                )
            return {
                "model": name,
                "translation": res,
                "error": None,
                "time": round(time.time() - time_start, 1),
            }
        except Exception as exc:
            # skip unsupported models
            if str(exc).startswith("No endpoints found that support"):
                return {"model": name, "translation": None, "error": None}
            return {"model": name, "translation": None, "error": str(exc)}

    has_image = False
    has_audio = False
    has_video = False
    if req.source_media:
        mime = req.source_media.split(",")[0]
        if "audio" in mime:
            has_audio = True
        elif "video" in mime:
            has_video = True
        else:
            has_image = True
    
    tasks = []
    for model_info in MODEL_LIBRARY:
        # Check if model supports the current request
        if has_video and not model_info["support_video"]:
            continue
        if has_audio and not model_info["support_audio"]:
            continue
        if has_image and not model_info["support_image"]:
            continue
        if not req.source_media and not model_info["support_textonly"]:
            continue
        
        tasks.append(
            _run_translate(
                model_info["name"],
                model_info["fn"],
                req.text,
                source_name,
                target_name,
                req.source_media,
                req.source_instructions,
            )
        )
    results = await asyncio.gather(*tasks)

    # filter out translations that did not pass because of language incompatibility
    results = [
        r for r in results if r["translation"] is not None or r["error"] is not None
    ]

    if len([r for r in results if r["translation"] is not None]) < 3:
        raise HTTPException(
            status_code=500, detail="Less than 3 models produced outputs"
        )

    return {"results": results, "quota": quota, "quota_used": quota_used + 1}


@router.post("/api/verify-submission")
async def verify_submission(req: VerifyReq, user: CurrentUser):
    VERIFICATION_MODEL = "google/gemini-3.1-pro-preview"
    quota_used = user["quota_used"]
    quota = user["quota"]
    if quota_used >= quota:
        raise HTTPException(status_code=429, detail="Quota exceeded")

    if not req.verification_rules:
        return {"results": [[]] * len(req.translations), "verification_model": VERIFICATION_MODEL}

    user["quota_used"] = quota_used + 1
    await save_user(user)

    async def _verify_single(
        source_text: str, translation: str, source_media: str | None = None
    ) -> list[bool]:
        results = []
        for rule in req.verification_rules:
            try:
                res = await verify_llm(
                    source_text, translation, rule, VERIFICATION_MODEL, source_media
                )
                results.append(res)
            except (OSError, RuntimeError, ValueError, KeyError) as exc:
                raise HTTPException(status_code=502, detail=f"LLM API error: {exc}")
        return results

    unique_translations = list(set(req.translations))
    unique_results = await asyncio.gather(
        *[
            _verify_single(req.source_text, t, req.source_media)
            for t in unique_translations
        ]
    )

    translation_to_result = dict(zip(unique_translations, unique_results))
    results = [translation_to_result[t] for t in req.translations]

    return {"results": results, "verification_model": VERIFICATION_MODEL, "quota": quota, "quota_used": quota_used + 1}


# --- Submissions ---


@router.post("/api/submissions")
async def create_submission(req: SubmissionReq, user: CurrentUser):
    require_role(user, "contributor")

    if (
        not req.source_lang
        or not req.source_lang.strip()
        or not req.target_lang
        or not req.target_lang.strip()
        or not (req.source_text or req.source_media)
        or not req.translations
        or not req.verification_rules
        or not req.verification_model
    ):
        raise HTTPException(status_code=400, detail="Field missing")

    user_submissions = await db_get_submissions(user["id"])
    accepted_count = sum(1 for s in user_submissions if s.get("status") == "accept")
    non_accepted_count = len(user_submissions) - accepted_count

    if accepted_count >= 100:
        raise HTTPException(
            status_code=400,
            detail="You already have more than 100 accepted submissions. To ensure diversity, we'll prefer submissions from other sources, which we would appreciate if you could help us review (get in touch)."
        )
    
    if non_accepted_count >= accepted_count + 20:
        raise HTTPException(
            status_code=400,
            detail="You currently have many non-reviewed submissions. Please wait until those are reviewed before submitting more."
        )

    submission = {
        "user_id": user["id"],
        "username": user["username"],
        "source_text": req.source_text,
        "source_media": req.source_media,
        "source_lang": req.source_lang.strip(),
        "target_lang": req.target_lang.strip(),
        "verification_rules": req.verification_rules,
        "translations": [t.dict() for t in req.translations],
        "verification_model": req.verification_model,
        "status": "pending",
        "created_at": datetime.now(UTC).astimezone().strftime("%Y-%m-%d %H:%M"),
        "source_instructions": req.source_instructions,
        "comments": [
            {
                "author": user["username"],
                "text": "SUBMIT",
                "created_at": datetime.now(UTC).astimezone().strftime("%Y-%m-%d %H:%M"),
            }
        ],
        "reviewed_by": None,
    }
    await db_create_submission(submission)
    return {"ok": True}


@router.put("/api/submissions/{sid}")
async def update_submission(
    sid: int, req: SubmissionReq, user: CurrentUser
):
    submission = await get_submission_by_id(sid)
    if submission is None:
        raise HTTPException(status_code=404, detail="Submission not found")

    if submission["user_id"] != user["id"]:
        raise HTTPException(
            status_code=403, detail="Not authorized to update this submission"
        )

    if submission["status"] == "accept":
        raise HTTPException(
            status_code=403, detail="Cannot edit an accepted submission"
        )

    update: dict = {
        "source_text": req.source_text,
        "source_lang": req.source_lang,
        "target_lang": req.target_lang,
        "verification_rules": req.verification_rules,
        "translations": [t.dict() for t in req.translations],
        "verification_model": req.verification_model,
        "status": "pending",
        "reviewed_by": None,
        "created_at": datetime.now(UTC).astimezone().strftime("%Y-%m-%d %H:%M"),
        "source_instructions": req.source_instructions,
        "source_media": req.source_media,
    }
    submission.update(update)
    submission["comments"].append(
        {
            "author": user["username"],
            "text": "SUBMIT",
            "created_at": datetime.now(UTC).astimezone().strftime("%Y-%m-%d %H:%M"),
        }
    )
    await save_submission(submission)
    return {"ok": True}


@router.delete("/api/submissions/{sid}")
async def delete_submission_endpoint(sid: int, user: CurrentUser):
    submission = await get_submission_by_id(sid)
    if submission is None:
        raise HTTPException(status_code=404, detail="Submission not found")
        
    is_admin = "admin" in user["roles"]
    is_own_returned = (submission["user_id"] == user["id"] and submission["status"] == "return")
    
    if not (is_admin or is_own_returned):
        raise HTTPException(status_code=403, detail="Not allowed to delete this submission")
        
    await delete_submission(sid)
    return {"ok": True}


@router.get("/api/submissions")
async def list_submissions(
    user: CurrentUser,
    mode: Literal["contributor", "reviewer", "admin"] = "contributor",
    status: Literal["pending", "accepted_or_returned", "accepted", "returned", "all"] = "all",
    source_langs: Annotated[list[str] | None, Query()] = None,
    target_langs: Annotated[list[str] | None, Query()] = None,
    username: str = "",
    min_rules: int = 0,
    min_pass_rate: float = 0.0,
    min_avg_pass_rate: float = 0.0,
    min_rule_length: int = 0,
    max_rule_length: int = 0,
):
    source_langs = source_langs or []
    target_langs = target_langs or []
    if mode in ("reviewer", "admin") and "reviewer" in user["roles"]:
        rows = await db_get_submissions()
        review_langs = {lang for lang in user["review_langs"]}
        is_admin = mode == "admin" and "admin" in user["roles"]
        
        if review_langs and not is_admin:
            rows = [s for s in rows if _submission_matches_scope(s, review_langs)]
            
        rows = _filter_reviewer_submissions(
            rows=rows,
            status=status,
            source_langs=source_langs,
            target_langs=target_langs,
            username=username,
            min_rules=min_rules,
            min_pass_rate=min_pass_rate,
            min_avg_pass_rate=min_avg_pass_rate,
            min_rule_length=min_rule_length,
            max_rule_length=max_rule_length,
        )
        
        # prevent non-admins from listing accepted submissions
        if not is_admin:
            rows = [
                s
                for s in rows
                # either not accepted
                if s["status"] != "accept"
                # or own submission
                or s["user_id"] == user["id"]
                # or reviewed by reviewer
                or s["reviewed_by"] == user["username"]
                # or commented by reviewer
                or any(
                    c["author"] == user["username"]
                    for c in s["comments"]
                )
            ]
    else:
        rows = await db_get_submissions(user_id=user["id"])
    
    users = await get_users()
    username_to_name = {u["username"]: u["name"] for u in users}
    for row in rows:
        row["name"] = username_to_name.get(row["username"])
        if "comments" in row and isinstance(row["comments"], list):
            for comment in row["comments"]:
                comment["author_name"] = username_to_name.get(comment["author"])

    return rows


@router.post("/api/submissions/{sid}/score")
async def score_submission(sid: int, req: ScoreReq, user: CurrentUser):
    require_role(user, "reviewer")
    if req.action not in ("return", "accept", "pending"):
        raise HTTPException(
            status_code=400, detail="Action must be return, accept, or pending"
        )
    submission = await get_submission_by_id(sid)
    if submission is None:
        raise HTTPException(status_code=404, detail="Submission not found")

    if submission["user_id"] == user["id"] and "admin" not in user["roles"]:
        raise HTTPException(
            status_code=403,
            detail="Reviewers who are not admins cannot change the status of their own submissions",
        )

    if req.action == "accept":
        submission["status"] = "accept"
        # give +10 credits to the author for accepted submission
        author = await get_user_by_id(submission["user_id"])
        if author:
            author["quota"] += 10
            await save_user(author)

    elif req.action == "return":
        submission["status"] = "return"
    elif req.action == "pending":
        submission["status"] = "pending"
    else:
        raise HTTPException(status_code=400, detail="Invalid action")

    submission["reviewed_by"] = user["username"]

    submission["comments"].append(
        {
            "author": user["username"],
            "text": req.action.upper(),
            "created_at": datetime.now(UTC).astimezone().strftime("%Y-%m-%d %H:%M"),
        }
    )

    if req.action in ("accept", "return"):
        author = await get_user_by_id(submission["user_id"])
        if author:
            prefix = submission["source_text"][:70].replace("\n", " ")
            if not prefix and submission["source_media"]:
                prefix = "Media submission"
            content = (
                f"#{submission['id']}: {prefix}..."
                if len(submission["source_text"]) > 40
                else f"#{submission['id']}: {prefix}"
            )
            author["notifications"].append(
                {
                    "created": datetime.now(UTC).astimezone().strftime("%Y-%m-%d %H:%M"),
                    "type": "accepted" if req.action == "accept" else "returned",
                    "status": "unread",
                    "content": content,
                }
            )
            await save_user(author)

    await save_submission(submission)
    return {"ok": True}


@router.post("/api/submissions/{sid}/comment")
async def add_comment(sid: int, req: CommentReq, user: CurrentUser):
    submission = await get_submission_by_id(sid)
    if submission is None:
        raise HTTPException(status_code=404, detail="Submission not found")

    is_reviewer = "reviewer" in user["roles"]
    is_owner = submission["user_id"] == user["id"]

    if not (is_reviewer or is_owner):
        raise HTTPException(status_code=403, detail="Not authorized to comment")

    submission["comments"].append(
        {
            "author": user["username"],
            "text": req.comment,
            "created_at": datetime.now(UTC).astimezone().strftime("%Y-%m-%d %H:%M"),
        }
    )

    if not is_owner:
        author = await get_user_by_id(submission["user_id"])
        if author:
            prefix = submission["source_text"][:40]
            if not prefix and submission["source_media"]:
                prefix = "Media submission"
            content = (
                f"#{submission['id']}: {prefix}..."
                if len(submission["source_text"]) > 40
                else f"#{submission['id']}: {prefix}"
            )
            author["notifications"].append(
                {
                    "created": datetime.now(UTC).astimezone().strftime("%Y-%m-%d %H:%M"),
                    "type": "commented",
                    "status": "unread",
                    "content": content,
                }
            )
            await save_user(author)

    await save_submission(submission)
    return {"ok": True}


@router.post("/api/notifications")
async def handle_notifications(
    req: NotificationActionReq, user: CurrentUser
):
    if req.action == "view":
        for n in user["notifications"]:
            n["status"] = "viewed"
    elif req.action == "clear":
        user["notifications"] = []
    else:
        raise HTTPException(status_code=400, detail="Invalid action")

    await save_user(user)
    return {"ok": True}


@router.post("/api/leaderboard")
async def leaderboard_submit(req: LeaderboardSubmitReq):
    with open(os.path.dirname(__file__) + "/static/leaderboard_submission.schema.json", "r") as f:
        schema = json.load(f)
    
    try:
        jsonschema.validate(instance=req.submission, schema=schema)
    except jsonschema.ValidationError as e:
        raise HTTPException(status_code=400, detail=f"Schema validation failed: {e.message}")

    if not os.path.exists("data/v1.json"):
        raise HTTPException(status_code=500, detail="Leaderboard data not found")
    with open("data/v1.json", "r") as f:
        leaderboard_data = json.load(f)

    id_to_mt = {sub["id"]: sub for sub in req.submission}
    for subset in ["LTBv1-eval"]:
        required = {
            sub["id"]
            for sub in leaderboard_data
            if subset in sub["tags"]
        }
        # verify that all translations exist for the subset
        if all(
            id_to_mt.get(sub_id) is not None and id_to_mt[sub_id]["translation"] is not None
            for sub_id in required
        ):
            break
    else:
        raise HTTPException(
            status_code=400,
            detail="The submission does not have translations for any of the subsets (currently only LTBv1-eval). Please check the submission and try again."
        )
    
    info = {
        "model_name": req.model_name,
        "model_size": req.model_size,
        "model_type": req.model_type,
        "model_release": req.model_release,
        "model_description": req.model_description,
        "institution": req.institution,
        "submitter_email": req.submitter_email,
        "mode": req.mode
    }
    
    await create_leaderboard_entry(req.submission, info)
    
    return {"ok": True}


@router.get("/api/leaderboard")
async def get_leaderboard(user: CurrentUser, status: str | None = Query(None)):
    is_admin = "admin" in user["roles"]
    if is_admin:
        entries = await get_leaderboard_entries(status=status)
    else:
        entries = await get_leaderboard_entries(visibility="visible", status=status)
    return entries


@router.get("/api/leaderboard/results")
async def get_leaderboard_results(
    mode: str,
    subset: str,
    lang1: str | None = None,
    lang2: str | None = None
):
    v1_path = os.path.dirname(__file__) + "/../data/v1.json"
    if not os.path.exists(v1_path):
        raise HTTPException(status_code=500, detail="Leaderboard data not found")
    with open(v1_path, "r") as f:
        v1_subs = json.load(f)

    # extract language pairs from all subsets (or maybe just the filtered subset? The prompt said "The language pairs should also already be simplified...")
    # Usually dropdowns show all available pairs for the current dataset.
    lang1s = sorted({simple_lang(s["source_lang"]) for s in v1_subs if subset in s["tags"]})
    lang2s = sorted({simple_lang(s["target_lang"]) for s in v1_subs if subset in s["tags"]})

    if lang1 is not None:
        v1_subs = [
            s for s in v1_subs
            if simple_lang(s.get("source_lang", "")) == lang1
        ]
    if lang2 is not None:
        v1_subs = [
            s for s in v1_subs
            if simple_lang(s.get("target_lang", "")) == lang2
        ]

    # filter by subset
    v1_subs = [
        s for s in v1_subs
        if subset == "all" or subset in s.get("tags", [])
    ]

    participants = await get_leaderboard_entries(status="scored", visibility="visible")

    models = []
    for participant in participants:
        # model has not been submitted in the right mode
        if participant["info"].get("mode") != mode:
            continue

        id_to_submission = {sub["id"]: sub for sub in participant.get("submissions", [])}
        
        # don't include models that don't have all translations
        if not all(sub["id"] in id_to_submission for sub in v1_subs):
            continue

        scores = [
            1 if id_to_submission[sub["id"]].get("verification") and all(id_to_submission[sub["id"]]["verification"]) else 0
            for sub in v1_subs
        ]
        
        model_out = {
            "model_name": participant["info"].get("model_name"),
            "model_size": participant["info"].get("model_size"),
            "model_type": participant["info"].get("model_type"),
            "model_release": participant["info"].get("model_release"),
            "model_description": participant["info"].get("model_description"),
            "institution": participant["info"].get("institution"),
            "score": statistics.mean(scores) if scores else 0.0,
        }
        if "display_dx" in participant["info"]:
            model_out["display_dx"] = participant["info"]["display_dx"]
        if "display_dy" in participant["info"]:
            model_out["display_dy"] = participant["info"]["display_dy"]
        models.append(model_out)
        
    models.sort(key=lambda x: x["score"], reverse=True)
    return {
        "models": models,
        "lang1s": lang1s,
        "lang2s": lang2s
    }

@router.post("/api/admin/leaderboard/{uid}")
async def admin_update_leaderboard(uid: int, req: LeaderboardUpdateReq, user: CurrentUser):
    require_role(user, "admin")
    if req.status not in ("pending", "scoring", "scored"):
        raise HTTPException(status_code=400, detail="Invalid status")
    if req.visibility not in ("hidden", "visible"):
        raise HTTPException(status_code=400, detail="Invalid visibility")
    current_entry = await get_leaderboard_entry(uid)
    if not current_entry:
        raise HTTPException(status_code=404, detail="Leaderboard entry not found")

    if req.status == "scoring" and current_entry["status"] == "pending":
        async def run_script():
            os.makedirs("logs", exist_ok=True)
            with open(f"logs/scoring_{uid}.log", "w") as log_file:
                proc = await asyncio.create_subprocess_exec(
                    sys.executable, 
                    os.path.dirname(__file__) + "/../scripts/41-score_leaderboard.py", 
                    str(uid),
                    stdout=log_file,
                    stderr=log_file
                )
                await proc.wait()
                if proc.returncode != 0:
                    await update_leaderboard_entry(uid, "pending", req.visibility)
            
        asyncio.create_task(run_script())

    await update_leaderboard_entry(uid, req.status, req.visibility)
    return {"ok": True}


@router.delete("/api/admin/leaderboard/{uid}")
async def admin_delete_leaderboard(uid: int, user: CurrentUser):
    require_role(user, "admin")
    await delete_leaderboard_entry(uid)
    return {"ok": True}

@router.put("/api/admin/leaderboard/{uid}/info")
async def admin_update_leaderboard_info(uid: int, req: LeaderboardInfoUpdateReq, user: CurrentUser):
    require_role(user, "admin")
    await update_leaderboard_info(uid, req.info)
    return {"ok": True}

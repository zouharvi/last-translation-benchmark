"""
Last Translation Benchmark — FastAPI backend
"""

import asyncio
import hashlib
import json
import os
import re
import secrets
from datetime import date, datetime, timezone
from typing import Optional

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .utils import (
    DAILY_QUOTA,
    DATA_PATH,
)
from .services import (
    translate_google,
    translate_mymemory,
    translate_gemini2_5flash,
    translate_gemma4,
    translate_qwen3p6,
    translate_gpt4p1nano,
    verify_llm,
)

# ---------------------------------------------------------------------------
# JSON data store
# ---------------------------------------------------------------------------

_db: dict = {}


def _load_data() -> None:
    global _db
    os.makedirs(os.path.dirname(DATA_PATH), exist_ok=True)
    if os.path.exists(DATA_PATH):
        with open(DATA_PATH, "r", encoding="utf-8") as f:
            _db = json.load(f)
    else:
        _db = {"users": [], "submissions": [], "tokens": {}}

    # Seed default users on first run
    if not _db["users"]:
        default_users = [
            ("r1", "r1", "reviewer"),
            ("c1", "c1", "contributor"),
            ("c2", "c2", "contributor"),
        ]
        for uid, (username, password, role) in enumerate(default_users, start=1):
            _db["users"].append(
                {
                    "id": uid,
                    "username": username,
                    "password_hash": hashlib.sha256(password.encode()).hexdigest(),
                    "role": role,
                    "quota_used": 0,
                    "quota_date": "",
                }
            )
        _save_data()


def _save_data() -> None:
    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(_db, f, indent=2, ensure_ascii=False)


def _next_id(collection: list) -> int:
    return max((item["id"] for item in collection), default=0) + 1


_load_data()

# ---------------------------------------------------------------------------
# App + middleware
# ---------------------------------------------------------------------------

app = FastAPI(title="Last Translation Benchmark")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Auth dependency
# ---------------------------------------------------------------------------


def _auth(authorization: Optional[str] = Header(None)) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")
    token = authorization[7:]
    user_id = _db["tokens"].get(token)
    if user_id is None:
        raise HTTPException(status_code=401, detail="Invalid token")
    user = next((u for u in _db["users"] if u["id"] == user_id), None)
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid token")
    return user


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class LoginReq(BaseModel):
    username: str
    password: str


class TranslateReq(BaseModel):
    text: str
    source_lang: str = "en"
    target_lang: str = "de"


class VerifyReq(BaseModel):
    translations: list[str]
    verification_rule: str


class TranslationEntry(BaseModel):
    api: str
    translation: str
    verified: Optional[bool] = None


class SubmissionReq(BaseModel):
    source_text: str
    source_lang: str = "en"
    target_lang: str = "de"
    verification_rule: str
    translations: list[TranslationEntry]


class ScoreReq(BaseModel):
    action: str  # "reject" | "accept" | "comment"
    comment: Optional[str] = None


# ---------------------------------------------------------------------------
# Routes — auth
# ---------------------------------------------------------------------------


@app.post("/api/login")
def login(req: LoginReq):
    phash = hashlib.sha256(req.password.encode()).hexdigest()
    user = next(
        (
            u
            for u in _db["users"]
            if u["username"] == req.username and u["password_hash"] == phash
        ),
        None,
    )
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = secrets.token_hex(32)
    _db["tokens"][token] = user["id"]
    _save_data()
    return {"token": token, "role": user["role"], "username": user["username"]}


@app.post("/api/logout")
def logout(user=Depends(_auth), authorization: Optional[str] = Header(None)):
    token = authorization[7:]
    _db["tokens"].pop(token, None)
    _save_data()
    return {"ok": True}


@app.get("/api/me")
def me(user=Depends(_auth)):
    today = date.today().isoformat()
    quota_used = user["quota_used"] if user["quota_date"] == today else 0
    total_points = sum(
        s["points"]
        for s in _db["submissions"]
        if s["user_id"] == user["id"] and s["points"] >= 0
    )
    return {
        "username": user["username"],
        "role": user["role"],
        "quota_used": quota_used,
        "quota_remaining": max(0, DAILY_QUOTA - quota_used),
        "daily_quota": DAILY_QUOTA,
        "total_points": total_points,
    }


# ---------------------------------------------------------------------------
# Routes — translation + verification
# ---------------------------------------------------------------------------


@app.post("/api/translate-submission")
def translate_submission(req: TranslateReq, user=Depends(_auth)):
    if user["role"] != "contributor":
        raise HTTPException(
            status_code=403, detail="Only contributors can use translation quota"
        )

    today = date.today().isoformat()
    quota_used = user["quota_used"] if user["quota_date"] == today else 0
    if quota_used >= DAILY_QUOTA:
        raise HTTPException(status_code=429, detail="Daily quota exceeded")

    async def _run_translate(name: str, func, *args):
        try:
            res = await asyncio.to_thread(func, *args)
            return {"api": name, "translation": res, "error": None}
        except Exception as exc:
            return {"api": name, "translation": None, "error": str(exc)}

    async def _run_all():
        return await asyncio.gather(
            _run_translate(
                "MyMemory",
                translate_mymemory,
                req.text,
                req.source_lang,
                req.target_lang,
            ),
            _run_translate(
                "Google", translate_google, req.text, req.source_lang, req.target_lang
            ),
            _run_translate(
                "Gemini 2.5 Flash Lite",
                translate_gemini2_5flash,
                req.text,
                req.source_lang,
                req.target_lang,
            ),
            _run_translate(
                "Gemma 4",
                translate_gemma4,
                req.text,
                req.source_lang,
                req.target_lang,
            ),
            _run_translate(
                "Qwen 3.6 Plus",
                translate_qwen3p6,
                req.text,
                req.source_lang,
                req.target_lang,
            ),
            _run_translate(
                "GPT-4.1 Nano",
                translate_gpt4p1nano,
                req.text,
                req.source_lang,
                req.target_lang,
            ),
        )

    results = asyncio.run(_run_all())

    user["quota_used"] = quota_used + 1
    user["quota_date"] = today
    _save_data()
    return {"results": results, "quota_remaining": DAILY_QUOTA - quota_used - 1}


@app.post("/api/verify-submission")
def verify_submission(req: VerifyReq, user=Depends(_auth)):
    content_stripped = req.verification_rule.strip()

    # TODO: verify daily quota here as well

    if content_stripped.startswith("#!regex"):
        lines = content_stripped.split("\n", 1)
        req.verification_rule = lines[1].strip() if len(lines) > 1 else ""
        results = []
        try:
            pattern = re.compile(req.verification_rule, re.IGNORECASE)
            for t in req.translations:
                results.append(bool(pattern.search(t)))
        except re.error as exc:
            raise HTTPException(
                status_code=400, detail=f"Invalid regex: {exc}"
            ) from exc
        return {
            "results": results,
        }

    try:

        async def _run_verify():
            async def _verify_llm(translation: str) -> bool:
                return await asyncio.to_thread(
                    verify_llm, translation, req.verification_rule
                )

            return await asyncio.gather(*[_verify_llm(t) for t in req.translations])

        results = asyncio.run(_run_verify())
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"LLM API error: {exc}") from exc

    return {
        "results": results,
    }


# ---------------------------------------------------------------------------
# Routes — submissions
# ---------------------------------------------------------------------------


@app.post("/api/submissions")
def create_submission(req: SubmissionReq, user=Depends(_auth)):
    if user["role"] != "contributor":
        raise HTTPException(
            status_code=403, detail="Only contributors can submit submissions"
        )

    sid = _next_id(_db["submissions"])
    _db["submissions"].append(
        {
            "id": sid,
            "user_id": user["id"],
            "username": user["username"],
            "source_text": req.source_text,
            "source_lang": req.source_lang,
            "target_lang": req.target_lang,
            "verification_rule": req.verification_rule,
            "translations": [t.model_dump() for t in req.translations],
            "points": -1,
            "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
        }
    )
    _save_data()
    return {"ok": True}


@app.get("/api/submissions")
def get_submissions(user=Depends(_auth)):
    if user["role"] == "reviewer":
        rows = sorted(
            _db["submissions"],
            key=lambda s: (s["points"], s["created_at"]),
        )
    else:
        rows = sorted(
            [s for s in _db["submissions"] if s["user_id"] == user["id"]],
            key=lambda s: s["created_at"],
            reverse=True,
        )
    return rows


@app.post("/api/submissions/{sid}/score")
def score_submission(sid: int, req: ScoreReq, user=Depends(_auth)):
    if user["role"] != "reviewer":
        raise HTTPException(
            status_code=403, detail="Only reviewer users can score submissions"
        )
    if req.action not in ("reject", "accept", "comment"):
        raise HTTPException(status_code=400, detail="Action must be reject, accept, or comment")
    submission = next((s for s in _db["submissions"] if s["id"] == sid), None)
    if submission is None:
        raise HTTPException(status_code=404, detail="Submission not found")
    if req.action == "accept":
        submission["points"] = 1
    elif req.action == "reject":
        submission["points"] = 0
    else:  # comment — stays pending, stores comment for contributor
        submission["points"] = -1
    submission["reviewer_comment"] = req.comment or ""
    _save_data()
    return {"ok": True}


# ---------------------------------------------------------------------------
# Static frontend — must be mounted last
# ---------------------------------------------------------------------------

app.mount(
    "/",
    StaticFiles(
        directory=os.path.dirname(os.path.abspath(__file__)) + "/static", html=True
    ),
    name="static",
)

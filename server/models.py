from typing import Optional

from pydantic import BaseModel


class TranslateReq(BaseModel):
    text: str
    source_lang: str = "en"
    target_lang: str = "de"

class Rule(BaseModel):
    type: str  # "llm", "contains", "not_contains"
    value: str

class VerifyReq(BaseModel):
    translations: list[str]
    verification_rules: list[Rule]

class TranslationEntry(BaseModel):
    api: str
    translation: str
    verified: Optional[bool] = None

class SubmissionReq(BaseModel):
    source_text: str
    source_lang: str = "en"
    target_lang: str = "de"
    verification_rules: list[Rule]
    translations: list[TranslationEntry]

class ScoreReq(BaseModel):
    action: str  # "reject" | "accept" | "comment"
    comment: Optional[str] = None

class ProfileReq(BaseModel):
    name: str
    affiliation: str
    email: str
    credit_consent: bool

class CommentReq(BaseModel):
    comment: str

class CreateUserReq(BaseModel):
    username: str
    roles: list[str]

class QuotaReq(BaseModel):
    delta: int

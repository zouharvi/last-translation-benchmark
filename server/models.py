from typing import Optional

from pydantic import BaseModel


class TranslateReq(BaseModel):
    text: str
    source_lang: str = "en"
    target_lang: str = "de"
    source_media: Optional[str] = None

class Rule(BaseModel):
    value: str

class VerifyReq(BaseModel):
    source_text: str
    translations: list[str]
    verification_rules: list[Rule]
    source_media: Optional[str] = None

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
    source_media: Optional[str] = None  # base64 data URL (data:audio/wav;base64,...) for audio/image submissions

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

class QuotaReq(BaseModel):
    delta: int

class RolesReq(BaseModel):
    roles: list[str]

class ReviewScopeReq(BaseModel):
    review_langs: list[str]

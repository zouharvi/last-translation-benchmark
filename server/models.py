
from pydantic import BaseModel, Field

field_source_text = Field(max_length=5000)
field_source_lang = Field(max_length=50)
field_target_lang = Field(max_length=50)
field_source_instructions = Field(default=None, optional=True, max_length=5000) # type: ignore
field_source_media = Field(default=None, optional=True, max_length=1500000) # type: ignore

class TranslateReq(BaseModel):
    text: str = field_source_text 
    source_lang: str = field_source_lang
    target_lang: str = field_target_lang
    source_media: str | None = field_source_media
    source_instructions: str | None = field_source_instructions

class Rule(BaseModel):
    value: str = Field(max_length=500)

class VerifyReq(BaseModel):
    source_text: str = field_source_text
    translations: list[str] = Field(max_length=5000)
    verification_rules: list[Rule] = Field(max_length=5)
    source_media: str | None = field_source_media

class TranslationEntry(BaseModel):
    model: str
    translation: str
    verified: list[bool] | None = None

class SubmissionReq(BaseModel):
    # Restrict to an appropriate character limit, e.g., 5000 chars
    source_text: str = Field(max_length=5000)
    source_lang: str = Field(max_length=50)
    target_lang: str = Field(max_length=50)
    verification_rules: list[Rule] = Field(max_length=5)
    translations: list[TranslationEntry]
    verification_model: str
    
    # source_media is base64-encoded (1500000 chars for ~1MB of binary data).
    source_media: str | None = field_source_media
    source_instructions: str | None = field_source_instructions

class ScoreReq(BaseModel):
    action: str  # "return" | "accept" | "pending"
    comment: str | None = None

class ProfileReq(BaseModel):
    name: str = Field(max_length=50)
    affiliation: str = Field(max_length=100)
    email: str = Field(max_length=100)
    credit_consent: bool
    notification_consent: bool

class RecoverLinkReq(BaseModel):
    email: str = Field(max_length=100)

class CommentReq(BaseModel):
    comment: str = Field(max_length=1000)

class QuotaReq(BaseModel):
    delta: int

class RolesReq(BaseModel):
    roles: list[str]

class ReviewScopeReq(BaseModel):
    review_langs: list[str]

class NotificationActionReq(BaseModel):
    action: str  # "view" | "clear"

class APILLMReq(BaseModel):
    model: str = Field(max_length=50)
    prompt: str = Field(max_length=50000)
    source_media: str | None = field_source_media
    cache: bool = True

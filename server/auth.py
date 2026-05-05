import secrets
from typing import Optional

from fastapi import Cookie, HTTPException

from .db import get_user_by_username


async def get_current_user(
    ltb_token: Optional[str] = Cookie(None), ltb_user: Optional[str] = Cookie(None)
) -> dict:
    if not ltb_token or not ltb_user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    user = await get_user_by_username(ltb_user)
    if user is None or not secrets.compare_digest(user.get("magic_token", ""), ltb_token):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return user


def require_admin(user: dict) -> None:
    if "admin" not in user.get("roles", []):
        raise HTTPException(status_code=403, detail="Admin access required")

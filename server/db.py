import json
import os
import secrets

from .utils import CONTRIBUTOR_QUOTA_DEFAULT, DATA_PATH

db_state: dict = {}


def load_data() -> None:
    global db_state
    os.makedirs(os.path.dirname(DATA_PATH), exist_ok=True)
    if os.path.exists(DATA_PATH):
        with open(DATA_PATH, "r", encoding="utf-8") as f:
            db_state = json.load(f)
    else:
        db_state = {"users": [], "submissions": []}

    # Seed default users on first run
    if not db_state["users"]:
        default_users = [
            ("admin", ["admin", "reviewer"]),
            ("r1", ["reviewer"]),
            ("c1", ["contributor"]),
            ("c2", ["contributor"]),
        ]
        for uid, (username, roles) in enumerate(default_users, start=1):
            db_state["users"].append(
                {
                    "id": uid,
                    "username": username,
                    "magic_token": secrets.token_urlsafe(24),
                    "roles": roles,
                    "quota": CONTRIBUTOR_QUOTA_DEFAULT,
                    "quota_used": 0,
                }
            )
        save_data()

    # Ensure at least one admin user exists
    if not any("admin" in u.get("roles", []) for u in db_state["users"]):
        db_state["users"].insert(
            0,
            {
                "id": next_id(db_state["users"]),
                "username": "admin",
                "magic_token": secrets.token_urlsafe(24),
                "roles": ["admin", "reviewer"],
                "quota": CONTRIBUTOR_QUOTA_DEFAULT,
                "quota_used": 0,
            },
        )
        save_data()

    changed = False
    for user in db_state["users"]:
        if not user.get("magic_token"):
            user["magic_token"] = secrets.token_urlsafe(24)
            changed = True

    if changed:
        save_data()


def save_data() -> None:
    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(db_state, f, indent=2, ensure_ascii=False)


def next_id(collection: list) -> int:
    return max((item["id"] for item in collection), default=0) + 1


load_data()

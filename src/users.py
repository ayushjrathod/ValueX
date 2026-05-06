"""
User context loader.

For the demo this reads from fixtures/users/*.json.
Swap the implementation for a DB call in future.
"""

import json
from pathlib import Path
from typing import Any

_FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "users"

_cache: dict[str, dict[str, Any]] = {}


def _load_all() -> None:
    if _cache:
        return
    for path in _FIXTURES_DIR.glob("*.json"):
        with open(path, encoding="utf-8") as f:
            user = json.load(f)
        _cache[user["user_id"]] = user


def get_user(user_id: str) -> dict[str, Any] | None:
    """Return user profile dict or None if not found."""
    _load_all()
    return _cache.get(user_id)


def list_users() -> list[dict[str, Any]]:
    """Return lightweight summaries for all available fixture users."""
    _load_all()

    users: list[dict[str, Any]] = []
    for user in _cache.values():
        positions = user.get("positions", [])
        preferences = user.get("preferences", {})
        users.append(
            {
                "user_id": user["user_id"],
                "name": user.get("name", "Unknown"),
                "country": user.get("country"),
                "risk_profile": user.get("risk_profile"),
                "base_currency": user.get("base_currency"),
                "positions_count": len(positions),
                "preferred_benchmark": preferences.get("preferred_benchmark"),
            }
        )

    return sorted(users, key=lambda user: user["name"])



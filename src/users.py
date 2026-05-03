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



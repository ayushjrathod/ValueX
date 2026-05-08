"""
In-memory conversation session store.

Stores user/assistant message pairs keyed by session_id so follow-up
queries carry prior context.  Thread-safe, with TTL-based eviction and
a per-session turn cap to bound token usage.

Swap the backend (Redis, Postgres, etc.) by replacing this module;
the public interface is get_session_store() → SessionStore.
"""

import json
import threading
import time
from typing import Any

from src.config.settings import SESSION_MESSAGES_PER_TURN, get_settings


class SessionStore:
    """Agent-agnostic conversation memory."""

    def __init__(
        self,
    ) -> None:
        settings = get_settings()
        self._store: dict[str, list[dict[str, str]]] = {}
        self._timestamps: dict[str, float] = {}
        self._lock = threading.Lock()
        self._max_turns = settings.session_max_turns
        self._ttl = settings.session_ttl_seconds

    def get_history(self, session_id: str) -> list[dict[str, str]]:
        """Return a copy of the conversation history for session_id."""
        with self._lock:
            self._evict_expired()
            return list(self._store.get(session_id, []))

    def add_turn(
        self,
        session_id: str,
        user_message: str,
        assistant_response: dict[str, Any],
    ) -> None:
        """Append one user→assistant exchange to the session."""
        with self._lock:
            sanitized_response = dict(assistant_response)
            sanitized_response.pop("_meta", None)
            history = self._store.setdefault(session_id, [])
            history.append({"role": "user", "content": user_message})
            history.append({
                "role": "assistant",
                "content": json.dumps(sanitized_response, default=str),
            })
            # Trim history to keep only the most recent turns and update the timestamp
            max_items = self._max_turns * SESSION_MESSAGES_PER_TURN
            if len(history) > max_items:
                self._store[session_id] = history[-max_items:]
            self._timestamps[session_id] = time.time()

    def clear(self, session_id: str) -> None:
        """Remove all history for a session."""
        with self._lock:
            self._store.pop(session_id, None)
            self._timestamps.pop(session_id, None)

    def _evict_expired(self) -> None:
        now = time.time()
        expired = [
            sid
            for sid, ts in self._timestamps.items()
            if now - ts > self._ttl
        ]
        for sid in expired:
            self._store.pop(sid, None)
            self._timestamps.pop(sid, None)


_store = SessionStore()


def get_session_store() -> SessionStore:
    """Return the module-level singleton store."""
    return _store

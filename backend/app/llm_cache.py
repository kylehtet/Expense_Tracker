"""In-memory response cache for LLM calls whose input is likely to recur
(e.g. checking the same purchase twice in one session). Keyed by a hash of
the exact deterministic input the prompt is built from, not the whole
request - so unrelated fields (e.g. a request id) can't bust the cache."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Optional

_cache: dict[str, Any] = {}


def cache_key(*parts: Any) -> str:
    payload = json.dumps(parts, sort_keys=True, default=str)
    return hashlib.sha256(payload.encode()).hexdigest()


def get(key: str) -> Optional[Any]:
    return _cache.get(key)


def set(key: str, value: Any) -> None:
    _cache[key] = value


def clear() -> None:
    _cache.clear()

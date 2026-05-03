"""
cache.py - Simple in-memory TTL cache for search results
No Redis needed for basic usage. Swap with Redis for production scale.
"""

import time
import logging
from typing import Optional, List, Dict

logger = logging.getLogger(__name__)

# Cache storage: { query_key: { "data": [...], "expires": timestamp } }
_cache: Dict[str, Dict] = {}

# Cache TTL in seconds (20 minutes)
CACHE_TTL = 60 * 20


def _normalize_key(query: str) -> str:
    return query.strip().lower()


def get_cached_result(query: str) -> Optional[List[Dict]]:
    key = _normalize_key(query)
    entry = _cache.get(key)

    if not entry:
        return None

    if time.time() > entry["expires"]:
        del _cache[key]
        logger.debug(f"Cache expired for: {key}")
        return None

    logger.debug(f"Cache hit for: {key}")
    return entry["data"]


def set_cached_result(query: str, data: List[Dict]) -> None:
    key = _normalize_key(query)
    _cache[key] = {
        "data": data,
        "expires": time.time() + CACHE_TTL,
    }
    logger.debug(f"Cached {len(data)} results for: {key}")

    # Auto-cleanup old entries if cache grows too large
    if len(_cache) > 500:
        _cleanup_expired()


def delete_cached_result(query: str) -> None:
    key = _normalize_key(query)
    _cache.pop(key, None)


def _cleanup_expired() -> None:
    now = time.time()
    expired_keys = [k for k, v in _cache.items() if now > v["expires"]]
    for k in expired_keys:
        del _cache[k]
    logger.debug(f"Cleaned up {len(expired_keys)} expired cache entries")


def get_cache_stats() -> Dict:
    now = time.time()
    active = sum(1 for v in _cache.values() if now <= v["expires"])
    return {
        "total_entries": len(_cache),
        "active_entries": active,
        "expired_entries": len(_cache) - active,
    }

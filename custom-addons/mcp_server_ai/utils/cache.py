import hashlib
import json
import logging
import threading
import time

_logger = logging.getLogger(__name__)

# Thread-safe cache storage: {cache_key: (data, expiry_timestamp)}
_cache_store = {}
_cache_lock = threading.Lock()

# Max cache size in entries (approximate memory control)
MAX_CACHE_ENTRIES = 5000


def get_cache_key(user_id, model, operation, params):
    """Generate a unique cache key for the request."""
    params_str = json.dumps(params, sort_keys=True, default=str)
    raw_key = f"mcp:{user_id}:{model}:{operation}:{params_str}"
    key_hash = hashlib.md5(raw_key.encode()).hexdigest()
    return f"mcp:{user_id}:{model}:{operation}:{key_hash}"


def cache_get(cache_key):
    """
    Get a value from cache.
    Returns (hit: bool, data: any).
    """
    with _cache_lock:
        entry = _cache_store.get(cache_key)
        if entry is None:
            return False, None
        data, expiry = entry
        if time.time() > expiry:
            del _cache_store[cache_key]
            return False, None
        return True, data


def cache_set(cache_key, data, ttl):
    """Store a value in cache with TTL in seconds."""
    if ttl <= 0:
        return
    with _cache_lock:
        # Evict oldest entries if cache is full
        if len(_cache_store) >= MAX_CACHE_ENTRIES:
            _evict_expired()
            if len(_cache_store) >= MAX_CACHE_ENTRIES:
                _evict_oldest(MAX_CACHE_ENTRIES // 4)
        _cache_store[cache_key] = (data, time.time() + ttl)


def cache_invalidate_model(model):
    """Invalidate all cache entries for a specific model."""
    with _cache_lock:
        keys_to_delete = [
            k for k in _cache_store if f":{model}:" in k
        ]
        for k in keys_to_delete:
            del _cache_store[k]
        if keys_to_delete:
            _logger.debug("MCP cache invalidated %d entries for model %s", len(keys_to_delete), model)


def cache_clear():
    """Clear the entire cache."""
    with _cache_lock:
        _cache_store.clear()
    _logger.info("MCP cache cleared.")


def _evict_expired():
    """Remove all expired entries. Must be called within lock."""
    now = time.time()
    keys_to_delete = [
        k for k, (_, expiry) in _cache_store.items() if now > expiry
    ]
    for k in keys_to_delete:
        del _cache_store[k]


def _evict_oldest(count):
    """Remove the oldest N entries. Must be called within lock."""
    sorted_keys = sorted(
        _cache_store.keys(),
        key=lambda k: _cache_store[k][1]
    )
    for k in sorted_keys[:count]:
        del _cache_store[k]

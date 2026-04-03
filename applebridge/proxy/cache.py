"""
Image Cache for Web Proxy
==========================

Caches optimized images with TTL and LRU eviction.
Uses PRIVATE state (not shared globally).
"""

import time
import threading
import logging

# PRIVATE state (isolated from other modules)
_image_cache = {}  # {url: (image_data, content_type, timestamp)}
_cache_lock = threading.Lock()

MAX_CACHE_ENTRIES = 100
CACHE_TTL_SECONDS = 3600  # 1 hour


def get_cached_image(url):
    """Get cached image if available and not expired.

    Args:
        url: Image URL

    Returns:
        Tuple of (image_data, content_type, None) if cached and fresh
        None if not cached or expired
    """
    with _cache_lock:
        if url in _image_cache:
            cached_data, cached_type, cached_time = _image_cache[url]
            age = time.time() - cached_time
            if age < CACHE_TTL_SECONDS:
                logging.debug(f"Image cache HIT: {url} (age: {age:.0f}s)")
                return cached_data, cached_type, None
            else:
                # Expired, remove
                del _image_cache[url]
                logging.debug(f"Image cache EXPIRED: {url}")
    return None


def cache_image(url, data, content_type):
    """Store image in cache with LRU eviction.

    Args:
        url: Image URL
        data: Image binary data
        content_type: MIME type
    """
    with _cache_lock:
        # Evict oldest if full (LRU)
        if len(_image_cache) >= MAX_CACHE_ENTRIES:
            oldest_url = min(_image_cache.keys(), key=lambda k: _image_cache[k][2])
            del _image_cache[oldest_url]
            logging.debug(f"Image cache EVICT: {oldest_url}")

        _image_cache[url] = (data, content_type, time.time())
        logging.debug(f"Image cache STORE: {url} ({len(data)/1024:.1f} KB)")


def clear_cache():
    """Clear entire image cache."""
    with _cache_lock:
        count = len(_image_cache)
        _image_cache.clear()
        logging.info(f"Image cache cleared ({count} entries)")


def get_cache_stats():
    """Get cache statistics.

    Returns:
        Dict with 'size' (number of entries) and 'memory_kb' (approximate memory usage)
    """
    with _cache_lock:
        size = len(_image_cache)
        memory_bytes = sum(len(data) for data, _, _ in _image_cache.values())
        return {
            "size": size,
            "memory_kb": memory_bytes / 1024
        }

"""
Rate Limiting for Web Proxy
============================

Prevents HTTP 429 errors by limiting request frequency to each domain.
Uses PRIVATE state (not shared globally).
"""

import time
import threading
import logging
from urllib.parse import urlparse

# PRIVATE state (isolated from other modules)
_domain_request_times = {}  # {domain: last_request_timestamp}
_rate_lock = threading.Lock()

MIN_REQUEST_INTERVAL = 2.0  # seconds between requests to same domain


def wait_for_rate_limit(url):
    """Wait if necessary to respect rate limit for domain.

    Args:
        url: Full URL to check rate limit for

    Implements human-like browsing speed (2s between requests to same domain).
    """
    domain = urlparse(url).netloc

    with _rate_lock:
        if domain in _domain_request_times:
            time_since_last = time.time() - _domain_request_times[domain]
            if time_since_last < MIN_REQUEST_INTERVAL:
                wait_time = MIN_REQUEST_INTERVAL - time_since_last
                logging.debug(f"Rate limit: waiting {wait_time:.2f}s for {domain}")
                time.sleep(wait_time)
        _domain_request_times[domain] = time.time()


def reset_domain_timer(domain):
    """Reset rate limit timer for a domain.

    Useful after receiving 429 error to force a longer wait.
    """
    with _rate_lock:
        if domain in _domain_request_times:
            del _domain_request_times[domain]

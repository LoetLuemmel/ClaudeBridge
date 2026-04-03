"""
Claude API Client
=================

Handles communication with the Anthropic Claude API.
"""

import json
import urllib.request
import urllib.error
from applebridge.config import CONFIG


def call_claude(api_key, prompt, system_prompt=""):
    """Call Claude API and return response text.

    Args:
        api_key: Anthropic API key
        prompt: User prompt
        system_prompt: Optional system prompt for role/context

    Returns:
        Response text from Claude or error message
    """
    headers = {
        "Content-Type": "application/json",
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01"
    }
    body = {
        "model": CONFIG["claude"]["model"],
        "max_tokens": CONFIG["claude"]["max_tokens"],
        "messages": [{"role": "user", "content": prompt}]
    }
    if system_prompt:
        body["system"] = system_prompt
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=data, headers=headers, method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            return result["content"][0]["text"]
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8", errors="replace")
        return f"[API Error {e.code}]: {error_body}"
    except Exception as e:
        return f"[Error]: {str(e)}"

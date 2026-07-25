"""
Job Queue Management
====================

Manages background jobs for Claude API calls.
Uses PRIVATE state (not shared globally).
"""

import threading
import time
import logging
import os

from applebridge.claude.api import call_claude
from applebridge.claude.history import add_to_history, add_to_chat_history, get_chat_context, get_code_context
from applebridge.config import CONFIG

# PRIVATE state (isolated from other modules)
_jobs = {}
_job_counter = 0
_job_lock = threading.Lock()


def create_job(mode, prompt, system_prompt, is_chat=False, display_prompt=None):
    """Create a background job for Claude API call.

    Args:
        mode: Mode string ('Code', 'Rez', 'Ask', 'Chat')
        prompt: User prompt (full text sent to Claude)
        system_prompt: System prompt for role/context
        is_chat: True for chat mode (includes history context)
        display_prompt: Optional shorter prompt for display (defaults to prompt)

    Returns:
        job_id: String ID for tracking the job
    """
    global _job_counter
    with _job_lock:
        _job_counter += 1
        job_id = str(_job_counter)
    _jobs[job_id] = {
        "status": "working",
        "mode": mode,
        "prompt": prompt,  # Store full prompt for Claude API
        "display_prompt": display_prompt or prompt,  # Short version for display
        "answer": None,
        "started": time.time(),
        "error": None,
        "is_chat": is_chat
    }
    logging.info(f"Job {job_id} created: {mode} - {prompt[:50]}...")

    def run():
        try:
            api_key = os.environ.get("ANTHROPIC_API_KEY", "")
            logging.debug(f"Job {job_id}: Calling Claude API...")

            # Add context from history
            actual_prompt = prompt
            if is_chat:
                # Chat mode: always include chat history
                context = get_chat_context()
                if context:
                    actual_prompt = context + f"\nNew message:\n{prompt}"
            elif mode == "Code":
                # Code mode: include context only for follow-up questions (not when reference code is provided)
                # If display_prompt is set, it means reference code was pasted, so skip history
                has_reference_code = "display_prompt" in _jobs[job_id] and _jobs[job_id]["display_prompt"] != prompt
                if not has_reference_code:
                    context = get_code_context()
                    if context:
                        actual_prompt = context + f"\nNew request:\n{prompt}"

            answer = call_claude(api_key, actual_prompt, system_prompt)
            with _job_lock:
                if job_id in _jobs:  # Job might have been cleaned up
                    _jobs[job_id]["answer"] = answer
                    _jobs[job_id]["status"] = "done"

                    # Add to appropriate history
                    if is_chat:
                        add_to_chat_history(prompt, answer)
                    else:
                        # Use display_prompt for history (shorter version without full code)
                        display_text = _jobs[job_id].get("display_prompt", _jobs[job_id]["prompt"])
                        add_to_history(mode, display_text, answer)

                    elapsed = time.time() - _jobs[job_id]["started"]
                    logging.info(f"Job {job_id} completed in {elapsed:.1f}s")
        except Exception as e:
            # Ensure job is marked as failed even if something goes wrong
            logging.error(f"Job {job_id} failed: {str(e)}")
            with _job_lock:
                if job_id in _jobs:
                    _jobs[job_id]["answer"] = f"[Interner Fehler]: {str(e)}"
                    _jobs[job_id]["status"] = "error"
                    _jobs[job_id]["error"] = str(e)
    t = threading.Thread(target=run, daemon=True)
    t.start()
    return job_id


def get_job(job_id):
    """Get job status and result.

    Returns:
        Job dict or None if not found
    """
    with _job_lock:
        return _jobs.get(job_id)


def check_job_timeout(job_id):
    """Check if job has timed out.

    Returns:
        True if job timed out, False otherwise
    """
    with _job_lock:
        if job_id not in _jobs:
            return False
        job = _jobs[job_id]
        if job["status"] == "working":
            elapsed = time.time() - job["started"]
            timeout = CONFIG["jobs"]["timeout"]
            if elapsed > timeout:
                job["status"] = "timeout"
                job["error"] = f"Request timed out after {timeout}s"
                logging.warning(f"Job {job_id} timed out after {elapsed:.1f}s")
                return True
    return False


def cleanup_old_jobs():
    """Remove old completed jobs to prevent memory leak."""
    with _job_lock:
        if len(_jobs) > CONFIG["jobs"]["max_history"]:
            # Find oldest completed/error/timeout jobs
            completed = [(jid, j["started"]) for jid, j in _jobs.items()
                        if j["status"] in ["done", "error", "timeout"]]
            completed.sort(key=lambda x: x[1])  # Sort by started time
            # Remove oldest
            for jid, _ in completed[:len(completed)//2]:
                del _jobs[jid]
                logging.debug(f"Cleaned up job {jid}")

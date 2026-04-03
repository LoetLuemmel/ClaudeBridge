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
from applebridge.claude.history import add_to_history, add_to_chat_history, get_chat_context
from applebridge.config import CONFIG

# PRIVATE state (isolated from other modules)
_jobs = {}
_job_counter = 0
_job_lock = threading.Lock()


def create_job(mode, prompt, system_prompt, is_chat=False):
    """Create a background job for Claude API call.

    Args:
        mode: Mode string ('Code', 'Rez', 'Ask', 'Chat')
        prompt: User prompt
        system_prompt: System prompt for role/context
        is_chat: True for chat mode (includes history context)

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
        "prompt": prompt,  # Store full prompt for context
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

            # Add context from history for chat only
            # Code mode: user provides code directly, no need for conversation context
            actual_prompt = prompt
            if is_chat:
                context = get_chat_context()
                if context:
                    actual_prompt = context + f"\nNew message:\n{prompt}"

            answer = call_claude(api_key, actual_prompt, system_prompt)
            with _job_lock:
                if job_id in _jobs:  # Job might have been cleaned up
                    _jobs[job_id]["answer"] = answer
                    _jobs[job_id]["status"] = "done"

                    # Add to appropriate history
                    if is_chat:
                        add_to_chat_history(prompt, answer)
                    else:
                        add_to_history(mode, _jobs[job_id]["prompt"], answer)

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

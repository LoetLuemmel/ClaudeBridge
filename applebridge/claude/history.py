"""
Conversation History Management
================================

Manages conversation history for Code Assistant and Chat modes.
Uses PRIVATE state (not shared globally).
Supports persistent storage to JSON file.
"""

import time
import threading
import json
from pathlib import Path

# PRIVATE state (isolated from other modules)
_conversation_history = []
_chat_history = []
_history_lock = threading.Lock()

MAX_HISTORY = 20
MAX_CHAT_HISTORY = 10

# Persistent storage
HISTORY_FILE = Path.home() / ".config" / "applebridge" / "history.json"


def add_to_history(mode, question, answer):
    """Add an entry to conversation history (Code/Rez/Ask modes)."""
    with _history_lock:
        _conversation_history.append({
            "time": time.strftime("%H:%M:%S"),
            "mode": mode,
            "question": question,  # Store full question (not truncated)
            "answer": answer       # Store full answer (not truncated)
        })
        if len(_conversation_history) > MAX_HISTORY:
            _conversation_history.pop(0)
    _save_history()  # Save to disk after each addition


def get_code_context():
    """Get recent Code Assistant history as context for Claude."""
    with _history_lock:
        if not _conversation_history:
            return ""

        # Filter for Code mode only, get last 2 exchanges
        code_history = [entry for entry in _conversation_history if entry['mode'] == 'Code']
        if not code_history:
            return ""

        context = "Previous code conversation (for reference):\n\n"
        for entry in code_history[-2:]:  # Last 2 code exchanges for context
            context += f"User request: {entry['question'][:300]}\n"
            context += f"Your previous code: {entry['answer'][:800]}\n\n"
        return context


def add_to_chat_history(question, answer):
    """Add a chat message pair to history."""
    with _history_lock:
        _chat_history.append({
            "time": time.strftime("%H:%M:%S"),
            "question": question,
            "answer": answer
        })
        if len(_chat_history) > MAX_CHAT_HISTORY:
            _chat_history.pop(0)
    _save_history()  # Save to disk after each addition


def get_chat_context():
    """Get recent chat history as context for Claude."""
    with _history_lock:
        if not _chat_history:
            return ""

        context = "Previous conversation:\n\n"
        for entry in _chat_history[-5:]:  # Last 5 messages for context
            context += f"User: {entry['question'][:200]}\n"
            context += f"Claude: {entry['answer'][:200]}\n\n"
        return context


def get_all_history():
    """Get all conversation history (for history page)."""
    with _history_lock:
        return list(_conversation_history)  # Return copy


def get_all_chat_history():
    """Get all chat history (for history page)."""
    with _history_lock:
        return list(_chat_history)  # Return copy


def clear_chat_history():
    """Clear all chat history."""
    with _history_lock:
        _chat_history.clear()
    _save_history()  # Save to disk after clearing


def _save_history():
    """Save history to disk (internal function)."""
    try:
        HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
        with _history_lock:
            data = {
                "conversation_history": _conversation_history,
                "chat_history": _chat_history
            }
        with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        # Silently fail - don't crash server if can't save history
        print(f"Warning: Could not save history: {e}")


def load_history():
    """Load history from disk on server startup."""
    global _conversation_history, _chat_history
    try:
        if HISTORY_FILE.exists():
            with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
            with _history_lock:
                _conversation_history = data.get("conversation_history", [])[-MAX_HISTORY:]
                _chat_history = data.get("chat_history", [])[-MAX_CHAT_HISTORY:]
            print(f"Loaded {len(_conversation_history)} conversation entries and {len(_chat_history)} chat entries from history")
    except Exception as e:
        print(f"Warning: Could not load history: {e}")
        # Start with empty history if load fails

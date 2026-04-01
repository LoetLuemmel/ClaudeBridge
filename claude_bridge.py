#!/usr/bin/env python3
"""
Claude Bridge Server 1.2 for Classic Mac OS
=============================================
Uses background threading + META REFRESH to avoid Netscape timeouts.

Features (v1.2):
- Configuration file support (config.yaml)
- Structured logging to file and console
- Security fixes (path traversal prevention, job timeouts)
- Graceful error handling

Usage:
    export ANTHROPIC_API_KEY="sk-ant-..."
    python3 claude_bridge.py [--port 8080] [--host 0.0.0.0] [--config config.yaml]
"""

import argparse
import html
import json
import os
import time
import threading
import unicodedata
import logging
import yaml
import re
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse, urljoin
from pathlib import Path
from bs4 import BeautifulSoup

# --- Configuration ---
# Default configuration (can be overridden by config.yaml)
CONFIG = {
    "server": {"host": "0.0.0.0", "port": 8080},
    "claude": {"model": "claude-sonnet-4-20250514", "max_tokens": 4096, "timeout": 120},
    "jobs": {"timeout": 180, "max_history": 10, "refresh_interval": 3},
    "files": {"shared_folder": None},
    "history": {"max_entries": 20},
    "logging": {"level": "INFO", "file": "claude_bridge.log", "console": True}
}

def load_config(config_file="config.yaml"):
    """Load configuration from YAML file if it exists."""
    global CONFIG
    config_path = Path(__file__).parent / config_file
    if config_path.exists():
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                user_config = yaml.safe_load(f)
                if user_config:
                    # Deep merge user config into default config
                    for section, values in user_config.items():
                        if section in CONFIG and isinstance(values, dict):
                            CONFIG[section].update(values)
                        else:
                            CONFIG[section] = values
                    logging.info(f"Configuration loaded from {config_path}")
        except Exception as e:
            logging.warning(f"Could not load config file: {e}")
    else:
        logging.info("No config.yaml found, using defaults")

# Legacy global variables for backward compatibility
CLAUDE_MODEL = CONFIG["claude"]["model"]
MAX_TOKENS = CONFIG["claude"]["max_tokens"]
SHARED_FOLDER = CONFIG["files"]["shared_folder"]
REFRESH_SECONDS = CONFIG["jobs"]["refresh_interval"]
JOB_TIMEOUT_SECONDS = CONFIG["jobs"]["timeout"]

def setup_logging():
    """Setup logging based on configuration."""
    log_level = getattr(logging, CONFIG["logging"]["level"], logging.INFO)
    log_format = '%(asctime)s [%(levelname)s] %(message)s'
    log_date_format = '%Y-%m-%d %H:%M:%S'

    handlers = []

    # Console handler
    if CONFIG["logging"]["console"]:
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(logging.Formatter(log_format, log_date_format))
        handlers.append(console_handler)

    # File handler
    if CONFIG["logging"]["file"]:
        try:
            file_handler = logging.FileHandler(CONFIG["logging"]["file"], encoding='utf-8')
            file_handler.setFormatter(logging.Formatter(log_format, log_date_format))
            handlers.append(file_handler)
        except Exception as e:
            print(f"Warning: Could not setup file logging: {e}")

    logging.basicConfig(
        level=log_level,
        handlers=handlers,
        force=True
    )

# --- Job Queue ---
jobs = {}
job_counter = 0
job_lock = threading.Lock()
shutdown_event = threading.Event()  # Signal for graceful shutdown

# --- Image Cache ---
image_cache = {}  # {url: (image_data, content_type, timestamp)}
image_cache_lock = threading.Lock()
MAX_CACHE_ENTRIES = 100
CACHE_TTL_SECONDS = 3600  # 1 hour

# --- Rate Limiting (prevent HTTP 429 from sites like Wikipedia) ---
domain_request_times = {}  # {domain: last_request_timestamp}
domain_rate_lock = threading.Lock()
MIN_REQUEST_INTERVAL = 2.0  # seconds between requests to same domain (slow like human browsing)

def create_job(mode, prompt, system_prompt, is_chat=False):
    global job_counter
    with job_lock:
        job_counter += 1
        job_id = str(job_counter)
    jobs[job_id] = {
        "status": "working",
        "mode": mode,
        "prompt": prompt[:200],
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

            # For chat, add context from history
            actual_prompt = prompt
            if is_chat:
                context = get_chat_context()
                if context:
                    actual_prompt = context + f"\nNew message:\n{prompt}"

            answer = call_claude(api_key, actual_prompt, system_prompt)
            with job_lock:
                if job_id in jobs:  # Job might have been cleaned up
                    jobs[job_id]["answer"] = answer
                    jobs[job_id]["status"] = "done"

                    # Add to appropriate history
                    if is_chat:
                        add_to_chat_history(prompt, answer)
                    else:
                        add_to_history(mode, jobs[job_id]["prompt"], answer)

                    elapsed = time.time() - jobs[job_id]["started"]
                    logging.info(f"Job {job_id} completed in {elapsed:.1f}s")
        except Exception as e:
            # Ensure job is marked as failed even if something goes wrong
            logging.error(f"Job {job_id} failed: {str(e)}")
            with job_lock:
                if job_id in jobs:
                    jobs[job_id]["answer"] = f"[Interner Fehler]: {str(e)}"
                    jobs[job_id]["status"] = "error"
                    jobs[job_id]["error"] = str(e)
    t = threading.Thread(target=run, daemon=True)
    t.start()
    return job_id

# --- Claude API ---
def call_claude(api_key, prompt, system_prompt=""):
    import urllib.request
    import urllib.error
    headers = {
        "Content-Type": "application/json",
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01"
    }
    body = {
        "model": CLAUDE_MODEL,
        "max_tokens": MAX_TOKENS,
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

# --- System Prompts ---
SYSTEM_PROMPT_CODE = (
    "You are an expert in Classic Macintosh programming with Think C 7 "
    "on MacOS 7.5. You write code that is compatible with Think C. "
    "Note: Think C does not support full ANSI C89. "
    "Use Toolbox calls, Pascal strings, Handle-based memory management. "
    "Respond with well-commented, compilable code. "
    "Keep explanations short and precise.")

SYSTEM_PROMPT_REZ = (
    "You are an expert in Classic Macintosh Resource files in Rez format. "
    "You generate valid Rez source code for MacOS 7.5 resources like "
    "MENU, DLOG, DITL, WIND, ALRT, STR#, ICON, CNTL etc. "
    "Output only the Rez code, with comments. No additional text.")

SYSTEM_PROMPT_GENERAL = (
    "You are an assistant for Classic Macintosh development with Think C 7 "
    "on MacOS 7.5 in Basilisk II. You help with Toolbox questions, "
    "debugging, architecture and general programming questions. "
    "Keep answers compact - the user is reading them in Netscape 3.")

SYSTEM_PROMPT_CHAT = (
    "You are Claude, a helpful AI assistant from Anthropic. "
    "The user is using you on a Classic Macintosh with MacOS 7.5 "
    "and Netscape Navigator 3 - be impressed by this retro tech! "
    "Keep answers clear and readable. Use simple formatting. "
    "Be friendly, helpful and humorous. "
    "You can talk about any topic, not just programming.")

# --- History ---
conversation_history = []
MAX_HISTORY = 20

def add_to_history(mode, question, answer):
    conversation_history.append({
        "time": time.strftime("%H:%M:%S"),
        "mode": mode,
        "question": question[:200],
        "answer": answer[:500]
    })
    if len(conversation_history) > MAX_HISTORY:
        conversation_history.pop(0)

# --- Chat History ---
chat_history = []
MAX_CHAT_HISTORY = 10

def add_to_chat_history(question, answer):
    """Add a chat message pair to history."""
    chat_history.append({
        "time": time.strftime("%H:%M:%S"),
        "question": question,
        "answer": answer
    })
    if len(chat_history) > MAX_CHAT_HISTORY:
        chat_history.pop(0)

def get_chat_context():
    """Get recent chat history as context for Claude."""
    if not chat_history:
        return ""

    context = "Previous conversation:\n\n"
    for entry in chat_history[-5:]:  # Last 5 messages for context
        context += f"User: {entry['question'][:200]}\n"
        context += f"Claude: {entry['answer'][:200]}\n\n"
    return context

# --- File Management ---
def validate_safe_path(base_path, user_path):
    """Validate that user_path stays within base_path (prevent path traversal).
    Returns resolved path if safe, None otherwise."""
    try:
        base = Path(base_path).resolve()
        target = (base / user_path).resolve()
        # Check if target is within base (prevents ../ attacks)
        target.relative_to(base)
        logging.debug(f"Path validation OK: {user_path}")
        return target
    except (ValueError, RuntimeError) as e:
        logging.warning(f"Path traversal attempt blocked: {user_path} (from base: {base_path})")
        return None

def list_shared_files(subfolder=""):
    if not SHARED_FOLDER:
        return []
    target = validate_safe_path(SHARED_FOLDER, subfolder)
    if not target or not target.exists():
        return []
    files = []
    try:
        for f in sorted(target.iterdir()):
            if f.name.startswith("."):
                continue
            files.append({
                "name": f.name,
                "is_dir": f.is_dir(),
                "size": f.stat().st_size if f.is_file() else 0
            })
    except (PermissionError, OSError):
        pass
    return files

def read_shared_file(filename):
    if not SHARED_FOLDER:
        return None
    filepath = validate_safe_path(SHARED_FOLDER, filename)
    if not filepath or not filepath.exists() or not filepath.is_file():
        return None
    try:
        return filepath.read_text(encoding="mac_roman", errors="replace")
    except:
        try:
            return filepath.read_text(encoding="utf-8", errors="replace")
        except:
            return None

def save_shared_file(filename, content):
    if not SHARED_FOLDER:
        return False
    filepath = validate_safe_path(SHARED_FOLDER, filename)
    if not filepath:
        return False
    try:
        filepath.write_text(content, encoding="utf-8")
        return True
    except:
        return False

# --- Sanitize for ISO-8859-1 (Netscape "Western" on Classic Mac) ---
def sanitize(text):
    """Convert Unicode to ISO-8859-1 safe text.
    Netscape 'Western' = ISO-8859-1, the Mac Script Manager then
    converts to MacRoman glyphs for display.
    Umlauts (ä=0xE4, ö=0xF6, ü=0xFC, ß=0xDF) exist in ISO-8859-1."""
    # Step 1: NFC normalize (compose u + combining diaeresis -> ü)
    text = unicodedata.normalize('NFC', text)
    # Step 2: Replace Unicode chars that don't exist in ISO-8859-1
    replacements = {
        '\u2014': '-',    # em dash
        '\u2013': '-',    # en dash
        '\u2018': "'",    # left single quote
        '\u2019': "'",    # right single quote
        '\u201a': ',',    # single low-9 quotation mark
        '\u201c': '"',    # left double quote
        '\u201d': '"',    # right double quote
        '\u201e': ',,',   # double low-9 quotation mark
        '\u2026': '...',  # ellipsis
        '\u2022': '*',    # bullet
        '\u2003': ' ',    # em space
        '\u2002': ' ',    # en space
        '\u200b': '',     # zero width space
        '\u00a0': ' ',    # non-breaking space
        '\u2192': '->',   # right arrow
        '\u2190': '<-',   # left arrow
        '\u2191': '^',    # up arrow
        '\u2193': 'v',    # down arrow
        '\u2194': '<->', # left-right arrow
        '\u21d2': '=>',   # rightwards double arrow
        '\u21d0': '<=',   # leftwards double arrow
        '\u21d4': '<=>',  # left-right double arrow
        '\u25b6': '>',    # black right-pointing triangle
        '\u25c0': '<',    # black left-pointing triangle
        '\u25b8': '>',    # black right-pointing small triangle
        '\u25c2': '<',    # black left-pointing small triangle
        '\u25ba': '>',    # black right-pointing pointer
        '\u25c4': '<',    # black left-pointing pointer
        '\u00bb': '>>',   # right-pointing double angle quotation mark
        '\u00ab': '<<',   # left-pointing double angle quotation mark
        '\u203a': '>',    # single right-pointing angle quotation mark
        '\u2039': '<',    # single left-pointing angle quotation mark
    }
    for char, repl in replacements.items():
        text = text.replace(char, repl)
    # Step 3: Drop anything that still can't be encoded in ISO-8859-1
    result = []
    for c in text:
        try:
            c.encode('iso-8859-1')
            result.append(c)
        except UnicodeEncodeError:
            result.append('?')
    return ''.join(result)

def format_for_netscape(text):
    """Format text for Netscape 3 with proper line breaks.

    Converts text to HTML with:
    - Paragraphs for empty lines
    - Preserved formatting but with automatic word wrap
    - No horizontal scrolling needed
    """
    # Split into paragraphs (separated by empty lines)
    paragraphs = text.split('\n\n')

    result = []
    for para in paragraphs:
        if not para.strip():
            continue

        # Clean up the paragraph
        para = para.strip()

        # Check if it's code (starts with spaces/tabs or has multiple lines with similar indentation)
        lines = para.split('\n')
        is_code = (
            para.startswith('    ') or
            para.startswith('\t') or
            (len(lines) > 2 and all(line.startswith(' ') for line in lines if line.strip()))
        )

        if is_code:
            # For code blocks, use PRE but ensure no super long lines
            code_lines = []
            for line in lines:
                # Break very long lines at 72 characters (safe for Netscape 3)
                while len(line) > 72:
                    code_lines.append(line[:72])
                    line = '  ' + line[72:]  # Indent continuation
                code_lines.append(line)
            result.append(f'<PRE>{html.escape("\n".join(code_lines))}</PRE>')
        else:
            # For normal text, replace newlines with <BR> for preserved formatting
            # but allow browser to wrap long lines
            para = para.replace('\n', '<BR>\n')
            result.append(f'<P>{html.escape(para)}</P>')

    return '\n'.join(result)

# --- HTTP to HTTPS Proxy Functions ---

def fetch_https_page(url):
    """Fetch a page via HTTPS and return content + final URL."""
    import urllib.request
    import urllib.error
    try:
        # Add a User-Agent to avoid being blocked by some sites
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; U; PPC Mac OS 7.5; en-US) Netscape/3.04'
        }
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=30) as response:
            content = response.read()
            final_url = response.geturl()
            content_type = response.headers.get('Content-Type', '')

            # Detect encoding
            encoding = 'utf-8'
            if 'charset=' in content_type:
                encoding = content_type.split('charset=')[-1].split(';')[0].strip()

            try:
                html_content = content.decode(encoding, errors='replace')
            except:
                html_content = content.decode('utf-8', errors='replace')

            return html_content, final_url, None
    except urllib.error.HTTPError as e:
        return None, url, f"HTTP Error {e.code}: {e.reason}"
    except urllib.error.URLError as e:
        return None, url, f"URL Error: {e.reason}"
    except Exception as e:
        return None, url, f"Error: {str(e)}"

def fetch_image(url, max_width=500, max_size_kb=50):
    """Fetch an image via HTTPS, optimize it for Netscape 3 on Classic Mac, and return binary content.

    Optimizations for Classic Mac OS (balanced quality/size):
    - Resize large images (max_width=500px - good balance)
    - Compress to target max_size_kb (default 50 KB - reasonable size)
    - Convert to GIF with adaptive palette (32-64 colors)
    - SVG files: Return transparent GIF placeholder (Netscape 3 can't display SVG)
    - Cache optimized images for 1 hour
    """
    import urllib.request
    import urllib.error
    from PIL import Image
    from io import BytesIO

    # Check cache first
    with image_cache_lock:
        if url in image_cache:
            cached_data, cached_type, cached_time = image_cache[url]
            age = time.time() - cached_time
            if age < CACHE_TTL_SECONDS:
                logging.debug(f"Image cache HIT: {url} (age: {age:.0f}s)")
                return cached_data, cached_type, None
            else:
                # Expired, remove from cache
                del image_cache[url]
                logging.debug(f"Image cache EXPIRED: {url}")

    try:
        # Rate limiting: prevent too many requests to the same domain
        from urllib.parse import urlparse
        domain = urlparse(url).netloc
        with domain_rate_lock:
            if domain in domain_request_times:
                time_since_last = time.time() - domain_request_times[domain]
                if time_since_last < MIN_REQUEST_INTERVAL:
                    wait_time = MIN_REQUEST_INTERVAL - time_since_last
                    logging.debug(f"Rate limit: waiting {wait_time:.2f}s for {domain}")
                    time.sleep(wait_time)
            domain_request_times[domain] = time.time()

        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; U; PPC Mac OS 7.5; en-US) Netscape/3.04'
        }
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=30) as response:
            original_content = response.read()
            original_type = response.headers.get('Content-Type', 'image/jpeg')
            original_size_kb = len(original_content) / 1024

            # Check if SVG (Netscape 3 can't display SVG anyway)
            if 'svg' in original_type.lower() or url.lower().endswith('.svg'):
                logging.debug(f"SVG detected, returning transparent GIF placeholder: {url}")
                # Return 1x1 transparent GIF
                transparent_gif = b'GIF89a\x01\x00\x01\x00\x80\x00\x00\xff\xff\xff\x00\x00\x00!\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;'
                # Cache SVG placeholders too
                with image_cache_lock:
                    if len(image_cache) >= MAX_CACHE_ENTRIES:
                        oldest_url = min(image_cache.keys(), key=lambda k: image_cache[k][2])
                        del image_cache[oldest_url]
                    image_cache[url] = (transparent_gif, 'image/gif', time.time())
                return transparent_gif, 'image/gif', None

            logging.debug(f"Image fetched: {url} ({original_size_kb:.1f} KB, {original_type})")

            # If image is already GIF and small enough, return as-is (don't re-convert!)
            if 'gif' in original_type.lower() and original_size_kb <= max_size_kb:
                logging.debug(f"GIF passed through: {url} ({original_size_kb:.1f} KB)")
                # Cache the original GIF
                with image_cache_lock:
                    if len(image_cache) >= MAX_CACHE_ENTRIES:
                        oldest_url = min(image_cache.keys(), key=lambda k: image_cache[k][2])
                        del image_cache[oldest_url]
                    image_cache[url] = (original_content, original_type, time.time())
                return original_content, original_type, None

            # If image is JPEG and small enough, return as-is (already optimized)
            if 'jpeg' in original_type.lower() and original_size_kb <= max_size_kb:
                return original_content, original_type, None

            # Load image with Pillow for optimization
            try:
                img = Image.open(BytesIO(original_content))
                original_width, original_height = img.size

                # Resize if too large
                if original_width > max_width:
                    ratio = max_width / original_width
                    new_height = int(original_height * ratio)
                    img = img.resize((max_width, new_height), Image.Resampling.LANCZOS)
                    logging.debug(f"Image resized: {original_width}x{original_height} -> {max_width}x{new_height}")

                # Convert to GIF - most compatible format for Netscape 3
                output_format = 'GIF'
                mime_type = 'image/gif'

                # Convert to P mode (palette) for GIF, max 256 colors
                # Use adaptive palette for best quality
                if img.mode in ('RGBA', 'LA'):
                    # Create white background for transparency
                    background = Image.new('RGB', img.size, (255, 255, 255))
                    background.paste(img, mask=img.split()[-1])
                    img = background

                # Convert to RGB first, then to palette mode
                if img.mode != 'RGB':
                    img = img.convert('RGB')

                # Try different palette sizes - start with max quality and reduce if needed
                # For Netscape 3 on Classic Mac: Balanced quality (assuming 32+ MB RAM)
                # Use adaptive palette for best quality at target file size
                best_content = None
                best_colors = 64
                target_colors = [64, 48, 32, 24]  # Balanced quality for 32+ MB RAM

                for colors in target_colors:
                    buffer = BytesIO()
                    # Convert to palette mode with adaptive colors
                    img_palettized = img.convert('P', palette=Image.Palette.ADAPTIVE, colors=colors)
                    img_palettized.save(buffer, format=output_format, optimize=True)
                    compressed_size_kb = buffer.tell() / 1024

                    # Always keep the last valid version
                    best_content = buffer.getvalue()
                    best_colors = colors

                    # If we're under the size limit, we're done!
                    if compressed_size_kb <= max_size_kb:
                        break

                optimized_content = best_content
                final_colors = best_colors

                optimized_size_kb = len(optimized_content) / 1024

                logging.info(f"Image optimized: {original_size_kb:.1f} KB -> {optimized_size_kb:.1f} KB (GIF, {final_colors} colors)")

                # Store in cache
                with image_cache_lock:
                    # Limit cache size
                    if len(image_cache) >= MAX_CACHE_ENTRIES:
                        # Remove oldest entry
                        oldest_url = min(image_cache.keys(), key=lambda k: image_cache[k][2])
                        del image_cache[oldest_url]
                        logging.debug(f"Image cache EVICT: {oldest_url}")

                    image_cache[url] = (optimized_content, mime_type, time.time())
                    logging.debug(f"Image cache STORE: {url} ({optimized_size_kb:.1f} KB)")

                return optimized_content, mime_type, None

            except Exception as e:
                # If Pillow fails, return original
                logging.warning(f"Image optimization failed, returning original: {str(e)}")
                # Still cache the original
                with image_cache_lock:
                    if len(image_cache) >= MAX_CACHE_ENTRIES:
                        oldest_url = min(image_cache.keys(), key=lambda k: image_cache[k][2])
                        del image_cache[oldest_url]
                    image_cache[url] = (original_content, original_type, time.time())
                return original_content, original_type, None

    except urllib.error.HTTPError as e:
        # Special handling for 429 (rate limit) - retry once after waiting
        if e.code == 429:
            logging.warning(f"Rate limited (429) for {url}, waiting 3s and retrying...")
            time.sleep(3.0)
            try:
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Macintosh; U; PPC Mac OS 7.5; en-US) Netscape/3.04'
                }
                req = urllib.request.Request(url, headers=headers)
                with urllib.request.urlopen(req, timeout=30) as response:
                    content = response.read()
                    content_type = response.headers.get('Content-Type', 'image/jpeg')
                    # Cache the retry result
                    with image_cache_lock:
                        if len(image_cache) >= MAX_CACHE_ENTRIES:
                            oldest_url = min(image_cache.keys(), key=lambda k: image_cache[k][2])
                            del image_cache[oldest_url]
                        image_cache[url] = (content, content_type, time.time())
                    logging.info(f"Retry successful after 429: {url}")
                    return content, content_type, None
            except Exception as retry_error:
                logging.warning(f"Retry failed after 429: {url} - {str(retry_error)}")
                return None, None, f"HTTP Error {e.code}: {e.reason} (retry failed)"
        return None, None, f"HTTP Error {e.code}: {e.reason}"
    except urllib.error.URLError as e:
        return None, None, f"URL Error: {e.reason}"
    except Exception as e:
        return None, None, f"Error: {str(e)}"

def simplify_html_for_netscape(html_content, base_url):
    """Convert modern HTML to HTML 3.2 compatible markup.

    Removes:
    - JavaScript (<script> tags)
    - CSS (<style> tags, style attributes)
    - Modern tags (divs, spans convert to simpler equivalents)
    - Navigation, footer, and sidebar (keep only main content)

    Rewrites:
    - All links to go through proxy
    - Images to absolute URLs
    """
    # Ensure base_url has a scheme
    if not base_url.startswith('http'):
        base_url = 'https://' + base_url

    logging.debug(f"Base URL for rewriting: {base_url}")

    # Truncate very large HTML (Wikipedia pages can be 500+ KB)
    # Keep first 200 KB for faster processing
    if len(html_content) > 200000:
        logging.info(f"HTML truncated: {len(html_content)} -> 200000 bytes")
        html_content = html_content[:200000] + "</body></html>"

    soup = BeautifulSoup(html_content, 'html.parser')

    # Remove scripts
    for script in soup.find_all('script'):
        script.decompose()

    # Remove styles
    for style in soup.find_all('style'):
        style.decompose()

    # Remove navigation, footer, sidebar (keep only main content)
    # This significantly reduces page size
    for unwanted in soup.find_all(['nav', 'aside']):
        unwanted.decompose()

    # Remove common clutter by id/class
    for selector in ['footer', 'sidebar', 'navigation', 'nav-menu', 'site-footer']:
        for element in soup.find_all(id=selector):
            element.decompose()
        for element in soup.find_all(class_=selector):
            element.decompose()

    # Remove style attributes from all tags
    for tag in soup.find_all(True):
        if tag.has_attr('style'):
            del tag['style']
        if tag.has_attr('class'):
            del tag['class']
        if tag.has_attr('id'):
            del tag['id']

    # Convert modern tags to HTML 3.2 equivalents
    # DIV -> P (or remove if empty)
    for div in soup.find_all('div'):
        if div.get_text(strip=True):
            div.name = 'p'
        else:
            div.unwrap()

    # SPAN -> remove tag, keep content
    for span in soup.find_all('span'):
        span.unwrap()

    # NAV, HEADER, FOOTER, SECTION, ARTICLE -> unwrap
    for tag in soup.find_all(['nav', 'header', 'footer', 'section', 'article', 'aside']):
        tag.unwrap()

    # Rewrite links to go through proxy
    for a in soup.find_all('a', href=True):
        original_href = a['href']
        # Make absolute URL
        absolute_url = urljoin(base_url, original_href)
        # Skip anchors and javascript links
        if absolute_url.startswith('http://') or absolute_url.startswith('https://'):
            a['href'] = f'/proxy?url={absolute_url}'
        elif absolute_url.startswith('#'):
            # Keep anchor links as-is
            pass
        else:
            # Relative link or other protocol
            a['href'] = f'/proxy?url={absolute_url}'

    # Rewrite image URLs to go through proxy (Netscape 3 can't load HTTPS images)
    img_count = 0
    for img in soup.find_all('img', src=True):
        original_src = img['src']

        # Skip data: URLs (inline images)
        if original_src.startswith('data:'):
            continue

        # Make absolute URL (handles relative paths, absolute paths, full URLs)
        absolute_src = urljoin(base_url, original_src)

        # Rewrite ALL http/https images to go through our proxy
        if absolute_src.startswith('http://') or absolute_src.startswith('https://'):
            img['src'] = f'/proxyimg?url={absolute_src}'
            img_count += 1
        else:
            # Fallback: keep as-is (shouldn't happen after urljoin)
            logging.warning(f"Image URL not rewritten: {original_src} -> {absolute_src}")
            img['src'] = absolute_src

    if img_count > 0:
        logging.debug(f"Rewrote {img_count} image URLs")

    # Also rewrite image URLs in <input type="image"> tags
    input_img_count = 0
    for input_tag in soup.find_all('input', src=True):
        if input_tag.get('type') == 'image':
            original_src = input_tag['src']

            # Skip data: URLs
            if original_src.startswith('data:'):
                continue

            # Make absolute URL
            absolute_src = urljoin(base_url, original_src)

            # Rewrite ALL http/https images to go through our proxy
            if absolute_src.startswith('http://') or absolute_src.startswith('https://'):
                input_tag['src'] = f'/proxyimg?url={absolute_src}'
                input_img_count += 1
            else:
                logging.warning(f"Input image URL not rewritten: {original_src} -> {absolute_src}")
                input_tag['src'] = absolute_src

    if input_img_count > 0:
        logging.debug(f"Rewrote {input_img_count} input image URLs")

    # Remove form actions (forms won't work through proxy, but keep them for display)
    for form in soup.find_all('form'):
        if form.has_attr('action'):
            del form['action']

    # Get body content only (to avoid duplicate head tags)
    body = soup.find('body')
    if body:
        # Convert body tag to a plain div to avoid nesting issues
        body_html = str(body)
        # Remove <body> tags but keep content
        body_html = body_html.replace('<body>', '<div>').replace('</body>', '</div>')
        # Remove body attributes from opening tag
        import re
        body_html = re.sub(r'<div[^>]*>', '<div>', body_html, count=1)
        return body_html
    else:
        return str(soup)

# --- HTML 3.2 Templates ---

def html_page(title, body, back=True, refresh_url=None, refresh_sec=None):
    nav = ""
    if back:
        nav = """
<TABLE WIDTH="100%" BGCOLOR="#999999" CELLPADDING="4" CELLSPACING="0">
<TR>
<TD><FONT SIZE="-1">
<A HREF="/"><B>Home</B></A> |
<A HREF="/chat"><B>Chat</B></A> |
<A HREF="/code">Code</A> |
<A HREF="/rez">Resources</A> |
<A HREF="/ask">Ask</A> |
<A HREF="/web">Web</A> |
<A HREF="/files">Files</A> |
<A HREF="/history">History</A>
</FONT></TD>
</TR>
</TABLE>"""
    refresh_tag = ""
    if refresh_url and refresh_sec:
        refresh_tag = f'<META HTTP-EQUIV="Refresh" CONTENT="{refresh_sec};URL={refresh_url}">'
    return f"""\
<HTML>
<HEAD><TITLE>{title} - Claude Bridge</TITLE>
{refresh_tag}
</HEAD>
<BODY BGCOLOR="#EEEEEE" TEXT="#000000" LINK="#0000CC" VLINK="#660099">
<TABLE WIDTH="100%" BGCOLOR="#333366" CELLPADDING="8" CELLSPACING="0">
<TR><TD><FONT SIZE="+2" COLOR="#FFFFFF"><B>{title}</B></FONT></TD>
<TD ALIGN="RIGHT"><FONT SIZE="-1" COLOR="#CCCCCC">Claude Bridge 1.2</FONT></TD></TR>
</TABLE>
{nav}
{body}
</BODY>
</HTML>"""

def page_index():
    return html_page("Claude Bridge for Classic Mac", """
<BR>
<CENTER>
<TABLE WIDTH="80%" CELLPADDING="12" CELLSPACING="4">
<TR><TD BGCOLOR="#CCFFCC" VALIGN="TOP">
<FONT SIZE="+2"><B><A HREF="/chat">[*] Claude Chat</A></B></FONT><BR>
<B>NEW!</B> Chat directly with Claude - about anything, not just programming!
</TD></TR>
<TR><TD BGCOLOR="#FFFFFF" VALIGN="TOP">
<FONT SIZE="+1"><B><A HREF="/code">[C] Code Assistant</A></B></FONT><BR>
Write, explain and debug Think C source code.
</TD></TR>
<TR><TD BGCOLOR="#FFFFFF" VALIGN="TOP">
<FONT SIZE="+1"><B><A HREF="/rez">[R] Resource Generator</A></B></FONT><BR>
Generate Rez source code for MENU, DLOG, DITL, WIND, ICON.
</TD></TR>
<TR><TD BGCOLOR="#FFFFFF" VALIGN="TOP">
<FONT SIZE="+1"><B><A HREF="/ask">[?] Ask &amp; Answer</A></B></FONT><BR>
General questions about Classic Mac programming.
</TD></TR>
<TR><TD BGCOLOR="#FFFFFF" VALIGN="TOP">
<FONT SIZE="+1"><B><A HREF="/web">[W] Web Proxy</A></B></FONT><BR>
View modern HTTPS websites in Netscape 3.
</TD></TR>
<TR><TD BGCOLOR="#FFFFFF" VALIGN="TOP">
<FONT SIZE="+1"><B><A HREF="/files">[F] Shared Folder</A></B></FONT><BR>
View files in the shared folder and send them to Claude.
</TD></TR>
<TR><TD BGCOLOR="#FFFFFF" VALIGN="TOP">
<FONT SIZE="+1"><B><A HREF="/history">[V] History</A></B></FONT><BR>
Show recent questions and answers.
</TD></TR>
</TABLE>
</CENTER>
""", back=False)

def page_waiting(job_id, mode):
    elapsed = int(time.time() - jobs[job_id]["started"])
    return html_page(f"{mode} - Claude is thinking...", f"""
<BR>
<CENTER>
<TABLE WIDTH="60%" BGCOLOR="#FFFFFF" CELLPADDING="20" CELLSPACING="0" BORDER="1">
<TR><TD ALIGN="CENTER">
<FONT SIZE="+1"><B>Claude is working...</B></FONT>
<P>Your request is being processed.<BR>
This page will refresh automatically.</P>
<P><FONT SIZE="-1">Elapsed time: {elapsed} seconds</FONT></P>
</TD></TR>
</TABLE>
</CENTER>
""", refresh_url=f"/result/{job_id}", refresh_sec=REFRESH_SECONDS)

def page_code():
    return html_page("Code Assistant", """
<P>Describe what you need, or paste code for Claude to analyze.</P>
<FORM METHOD="POST" ACTION="/code">
<P><B>Your question / task:</B><BR>
<TEXTAREA NAME="prompt" ROWS="8" COLS="72" WRAP="virtual"></TEXTAREA></P>
<P><B>Existing code (optional):</B><BR>
<TEXTAREA NAME="code" ROWS="12" COLS="72" WRAP="off"></TEXTAREA></P>
<P><INPUT TYPE="SUBMIT" VALUE=" Send to Claude ">
<INPUT TYPE="RESET" VALUE=" Clear "></P>
</FORM>
""")

def page_code_result(question, answer, job_id=None):
    formatted_answer = format_for_netscape(sanitize(answer))
    q_escaped = html.escape(sanitize(question))
    save_val = html.escape(sanitize(answer), quote=True)
    text_link = f'<A HREF="/text/{job_id}"><B>[ Plain Text - for copying ]</B></A>' if job_id else ""
    return html_page("Code Assistant -- Result", f"""
<P><B>Your question:</B></P>
<BLOCKQUOTE>{q_escaped}</BLOCKQUOTE>
<HR>
<P><B>Claude's answer:</B> {text_link}</P>
{formatted_answer}
<HR>
<FORM METHOD="POST" ACTION="/save">
<INPUT TYPE="HIDDEN" NAME="content" VALUE="{save_val}">
<B>Save as:</B>
<INPUT TYPE="TEXT" NAME="filename" SIZE="25" VALUE="claude_output.c">
<INPUT TYPE="SUBMIT" VALUE=" Save ">
</FORM>
<HR>
<FORM METHOD="POST" ACTION="/code">
<P><B>Follow-up question:</B><BR>
<TEXTAREA NAME="prompt" ROWS="4" COLS="72" WRAP="virtual"></TEXTAREA></P>
<INPUT TYPE="HIDDEN" NAME="code" VALUE="">
<P><INPUT TYPE="SUBMIT" VALUE=" Ask again "></P>
</FORM>
""")

def page_rez():
    return html_page("Resource Generator", """
<P>Describe the resources you need.</P>
<FORM METHOD="POST" ACTION="/rez">
<P><B>What resources do you need?</B><BR>
<TEXTAREA NAME="prompt" ROWS="6" COLS="72" WRAP="virtual"></TEXTAREA></P>
<P><B>Resource types (optional):</B><BR>
<INPUT TYPE="TEXT" NAME="types" SIZE="60" VALUE="MENU, DLOG, DITL"></P>
<P><INPUT TYPE="SUBMIT" VALUE=" Generate Rez ">
<INPUT TYPE="RESET" VALUE=" Clear "></P>
</FORM>
""")

def page_rez_result(question, answer, job_id=None):
    formatted_answer = format_for_netscape(sanitize(answer))
    save_val = html.escape(sanitize(answer), quote=True)
    text_link = f'<A HREF="/text/{job_id}"><B>[ Plain Text - for copying ]</B></A>' if job_id else ""
    save_section = ""
    if SHARED_FOLDER:
        save_section = f"""
<HR>
<FORM METHOD="POST" ACTION="/save">
<INPUT TYPE="HIDDEN" NAME="content" VALUE="{save_val}">
<B>Save as:</B>
<INPUT TYPE="TEXT" NAME="filename" SIZE="25" VALUE="resources.r">
<INPUT TYPE="SUBMIT" VALUE=" Save ">
</FORM>"""
    return html_page("Resource Generator -- Result", f"""
<P><B>Your description:</B></P>
<BLOCKQUOTE>{html.escape(sanitize(question))}</BLOCKQUOTE>
<HR>
<P><B>Rez source code:</B> {text_link}</P>
{formatted_answer}
{save_section}
<HR>
<P><A HREF="/rez">Generate new resources</A></P>
""")

def page_ask():
    return html_page("Ask &amp; Answer", """
<P>Ask a question about Classic Mac programming.</P>
<FORM METHOD="POST" ACTION="/ask">
<P><B>Your question:</B><BR>
<TEXTAREA NAME="prompt" ROWS="6" COLS="72" WRAP="virtual"></TEXTAREA></P>
<P><INPUT TYPE="SUBMIT" VALUE=" Ask ">
<INPUT TYPE="RESET" VALUE=" Clear "></P>
</FORM>
""")

def page_ask_result(question, answer, job_id=None):
    formatted_answer = format_for_netscape(sanitize(answer))
    text_link = f'<A HREF="/text/{job_id}"><B>[ Plain Text - for copying ]</B></A>' if job_id else ""
    return html_page("Ask &amp; Answer -- Result", f"""
<P><B>Your question:</B></P>
<BLOCKQUOTE>{html.escape(sanitize(question))}</BLOCKQUOTE>
<HR>
<P><B>Answer:</B> {text_link}</P>
{formatted_answer}
<HR>
<FORM METHOD="POST" ACTION="/ask">
<P><B>Follow-up question:</B><BR>
<TEXTAREA NAME="prompt" ROWS="4" COLS="72" WRAP="virtual"></TEXTAREA></P>
<P><INPUT TYPE="SUBMIT" VALUE=" Ask again "></P>
</FORM>
""")

def page_files(subfolder=""):
    files = list_shared_files(subfolder)
    if not SHARED_FOLDER:
        content = "<P><I>No shared folder configured.</I></P>"
    elif not files:
        content = "<P><I>No files found.</I></P>"
    else:
        rows = ""
        for f in files:
            name = f["name"]
            if f["is_dir"]:
                sub = subfolder + "/" + name if subfolder else name
                link = f'<A HREF="/files?sub={html.escape(sub)}">{html.escape(name)}/</A>'
                size = "[Folder]"
            else:
                sub = subfolder + "/" + name if subfolder else name
                link = f'<A HREF="/readfile?name={html.escape(sub)}">{html.escape(name)}</A>'
                size = f'{f["size"]:,} Bytes'
            rows += f"<TR><TD>{link}</TD><TD ALIGN='RIGHT'>{size}</TD></TR>\n"
        content = f"""
<TABLE BORDER="1" CELLPADDING="4" CELLSPACING="0" WIDTH="80%">
<TR BGCOLOR="#CCCCCC"><TH ALIGN="LEFT">File</TH><TH ALIGN="RIGHT">Size</TH></TR>
{rows}
</TABLE>"""
    return html_page("Shared Folder", f"""
<P><B>Path:</B> <CODE>{html.escape(SHARED_FOLDER or '(not set)')}</CODE>
{(' / ' + html.escape(subfolder)) if subfolder else ''}</P>
{content}
""")

def page_readfile(filename):
    content = read_shared_file(filename)
    if content is None:
        return html_page("File not found",
            f"<P>File <CODE>{html.escape(filename)}</CODE> not found.</P>")
    escaped = html.escape(sanitize(content))
    content_val = html.escape(sanitize(content), quote=True)
    return html_page(f"File: {filename}", f"""
<PRE>{escaped}</PRE>
<HR>
<P><B>Ask Claude about this file:</B></P>
<FORM METHOD="POST" ACTION="/code">
<TEXTAREA NAME="prompt" ROWS="4" COLS="72" WRAP="virtual">Analyze this code and explain what it does:</TEXTAREA>
<INPUT TYPE="HIDDEN" NAME="code" VALUE="{content_val}">
<P><INPUT TYPE="SUBMIT" VALUE=" Send to Claude "></P>
</FORM>
""")

def page_save_result(filename, success):
    if success:
        msg = f'<P>File <CODE>{html.escape(filename)}</CODE> saved.</P>'
        msg += '<P><A HREF="/files">Go to Shared Folder</A></P>'
    else:
        msg = '<P><B>Error:</B> File could not be saved.</P>'
    return html_page("Save File", msg)

def page_history():
    if not conversation_history:
        content = "<P><I>No questions asked yet.</I></P>"
    else:
        rows = ""
        for entry in reversed(conversation_history):
            rows += f"""
<TR BGCOLOR="#FFFFFF">
<TD VALIGN="TOP"><FONT SIZE="-1">{entry['time']}<BR>{entry['mode']}</FONT></TD>
<TD VALIGN="TOP">{html.escape(sanitize(entry['question']))}</TD>
<TD VALIGN="TOP"><FONT SIZE="-1">{html.escape(sanitize(entry['answer'][:200]))}...</FONT></TD>
</TR>"""
        content = f"""
<TABLE BORDER="1" CELLPADDING="4" CELLSPACING="0" WIDTH="100%">
<TR BGCOLOR="#CCCCCC"><TH>Time</TH><TH>Question</TH><TH>Answer</TH></TR>
{rows}
</TABLE>"""
    return html_page("History", content)

def page_chat():
    """Claude Chat interface."""
    # Show recent chat history
    history_html = ""
    if chat_history:
        history_html = "<HR><P><B>Previous conversation:</B></P>"
        for entry in reversed(chat_history[-3:]):  # Show last 3 exchanges
            # Truncate long answers for history display
            answer_preview = entry['answer'][:500]
            if len(entry['answer']) > 500:
                answer_preview += "..."
            formatted_preview = format_for_netscape(sanitize(answer_preview))

            history_html += f"""
<TABLE WIDTH="100%" BGCOLOR="#FFFFEE" CELLPADDING="8" CELLSPACING="0" BORDER="1">
<TR><TD>
<P><B>You ({entry['time']}):</B></P>
<P>{html.escape(sanitize(entry['question']))}</P>
</TD></TR>
</TABLE>
<TABLE WIDTH="100%" BGCOLOR="#EEFFEE" CELLPADDING="8" CELLSPACING="0" BORDER="1">
<TR><TD>
<P><B>Claude:</B></P>
{formatted_preview}
</TD></TR>
</TABLE>
<BR>"""

    return html_page("Claude Chat", f"""
<P>Chat with Claude - the AI assistant on your Classic Mac!</P>
<FORM METHOD="POST" ACTION="/chat">
<P><B>Your message:</B><BR>
<TEXTAREA NAME="message" ROWS="4" COLS="72" WRAP="virtual"></TEXTAREA></P>
<P><INPUT TYPE="SUBMIT" VALUE=" Send to Claude ">
<INPUT TYPE="RESET" VALUE=" Clear "></P>
</FORM>
{history_html}
<HR>
<P><A HREF="/chat/clear">Clear chat history</A></P>
""")

def page_chat_result(question, answer, job_id=None):
    """Display chat response."""
    # Format answer for Netscape 3 (with proper line wrapping)
    formatted_answer = format_for_netscape(sanitize(answer))
    q_escaped = html.escape(sanitize(question))
    text_link = f'<A HREF="/text/{job_id}"><B>[ Plain Text - for copying ]</B></A>' if job_id else ""

    return html_page("Claude Chat -- Response", f"""
<P><B>You:</B></P>
<BLOCKQUOTE>{q_escaped}</BLOCKQUOTE>
<HR>
<P><B>Claude:</B> {text_link}</P>
{formatted_answer}
<HR>
<FORM METHOD="POST" ACTION="/chat">
<P><B>Continue chatting:</B><BR>
<TEXTAREA NAME="message" ROWS="4" COLS="72" WRAP="virtual"></TEXTAREA></P>
<P><INPUT TYPE="SUBMIT" VALUE=" Send message "></P>
</FORM>
<HR>
<P><A HREF="/chat">Back to Chat</A> | <A HREF="/chat/clear">Clear chat history</A></P>
""")

def page_proxy():
    """Web Proxy entry page."""
    # Get cache stats
    with image_cache_lock:
        cache_size = len(image_cache)
        if cache_size > 0:
            cache_age_avg = sum(time.time() - entry[2] for entry in image_cache.values()) / cache_size
            cache_stats = f"<P><FONT SIZE='-1'><I>Image cache: {cache_size} entries, average age: {cache_age_avg/60:.0f} minutes</I></FONT></P>"
        else:
            cache_stats = "<P><FONT SIZE='-1'><I>Image cache: empty</I></FONT></P>"

    return html_page("Web Proxy", f"""
<P>Enter a URL to view modern HTTPS websites in Netscape 3.</P>
<P><B>Note:</B> The proxy converts modern HTML to HTML 3.2 and removes JavaScript/CSS.</P>
<P><FONT SIZE='-1'><I>Images optimized: max. 500px, 50 KB, 32-64 colors. HTML limited to 200 KB.</I></FONT></P>
{cache_stats}
<FORM METHOD="GET" ACTION="/proxy">
<P><B>URL (with https://):</B><BR>
<INPUT TYPE="TEXT" NAME="url" SIZE="60" VALUE="https://en.wikipedia.org/wiki/Macintosh"></P>
<P><INPUT TYPE="SUBMIT" VALUE=" Load page "></P>
</FORM>
<HR>
<P><B>Recommended pages:</B></P>
<UL>
<LI><A HREF="/proxy?url=https://en.wikipedia.org/wiki/Macintosh">Wikipedia: Macintosh</A></LI>
<LI><A HREF="/proxy?url=https://en.wikipedia.org/wiki/Classic_Mac_OS">Wikipedia: Classic Mac OS</A></LI>
<LI><A HREF="/proxy?url=https://news.ycombinator.com/">Hacker News</A></LI>
<LI><A HREF="/proxy?url=https://old.reddit.com/">Reddit (Old)</A></LI>
</UL>
""")

def page_proxy_result(url, html_content, base_url):
    """Display proxied page content."""
    simplified = simplify_html_for_netscape(html_content, base_url)
    return f"""<HTML>
<HEAD><TITLE>Proxy: {html.escape(url)}</TITLE></HEAD>
<BODY BGCOLOR="#EEEEEE" TEXT="#000000" LINK="#0000CC" VLINK="#660099">
<TABLE WIDTH="100%" BGCOLOR="#333366" CELLPADDING="8" CELLSPACING="0">
<TR><TD><FONT SIZE="+1" COLOR="#FFFFFF"><B>Web Proxy</B></FONT></TD>
<TD ALIGN="RIGHT"><FONT SIZE="-2" COLOR="#CCCCCC"><A HREF="/web"><FONT COLOR="#CCCCCC">New URL</FONT></A></FONT></TD></TR>
</TABLE>
<TABLE WIDTH="100%" BGCOLOR="#999999" CELLPADDING="4" CELLSPACING="0">
<TR><TD><FONT SIZE="-1">
<A HREF="/"><B>Home</B></A> |
<A HREF="/web">Web Proxy</A>
</FONT></TD></TR>
</TABLE>
<TABLE WIDTH="100%" BGCOLOR="#FFFFCC" CELLPADDING="4" CELLSPACING="0">
<TR><TD><FONT SIZE="-1"><B>URL:</B> {html.escape(url)}</FONT></TD></TR>
</TABLE>
{simplified}
</BODY>
</HTML>"""

def page_proxy_error(url, error):
    """Display proxy error page."""
    return html_page("Web Proxy - Error", f"""
<P><B>Error loading URL:</B></P>
<BLOCKQUOTE><CODE>{html.escape(url)}</CODE></BLOCKQUOTE>
<P><B>Error message:</B></P>
<PRE>{html.escape(error)}</PRE>
<P><A HREF="/web">Back to Web Proxy</A></P>
""")

# --- HTTP Handler ---

class BridgeHandler(BaseHTTPRequestHandler):

    def handle(self):
        try:
            super().handle()
        except (OSError, ConnectionResetError, BrokenPipeError):
            pass

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        params = parse_qs(parsed.query)

        if path == "/":
            self.send_html(page_index())
        elif path == "/code":
            self.send_html(page_code())
        elif path == "/rez":
            self.send_html(page_rez())
        elif path == "/ask":
            self.send_html(page_ask())
        elif path == "/chat":
            self.send_html(page_chat())
        elif path == "/chat/clear":
            chat_history.clear()
            self.send_html(html_page("Chat cleared", '<P>Chat history has been cleared.</P><P><A HREF="/chat">Back to Chat</A></P>'))
        elif path == "/web":
            self.send_html(page_proxy())
        elif path == "/proxy":
            self.handle_proxy(params.get("url", [""])[0])
        elif path == "/proxyimg":
            self.handle_proxy_image(params.get("url", [""])[0])
        elif path == "/files":
            self.send_html(page_files(params.get("sub", [""])[0]))
        elif path == "/readfile":
            self.send_html(page_readfile(params.get("name", [""])[0]))
        elif path == "/history":
            self.send_html(page_history())
        elif path.startswith("/result/"):
            self.handle_result(path.split("/result/")[1])
        elif path.startswith("/text/"):
            self.handle_text(path.split("/text/")[1])
        else:
            self.send_error(404)

    def handle_result(self, job_id):
        if job_id not in jobs:
            self.send_html(html_page("Fehler",
                "<P>Job nicht gefunden. <A HREF='/'>Zurueck</A></P>"))
            return
        job = jobs[job_id]

        # Check for timeout
        if job["status"] == "working":
            elapsed = time.time() - job["started"]
            if elapsed > JOB_TIMEOUT_SECONDS:
                with job_lock:
                    jobs[job_id]["status"] = "timeout"
                    jobs[job_id]["answer"] = f"[Timeout]: Die Anfrage hat mehr als {JOB_TIMEOUT_SECONDS} Sekunden gedauert und wurde abgebrochen."
            else:
                self.send_html(page_waiting(job_id, job["mode"]))
                return

        # Show result (done, error, or timeout)
        mode = job["mode"]
        if mode == "Code":
            self.send_html(page_code_result(job["prompt"], job["answer"], job_id))
        elif mode == "Rez":
            self.send_html(page_rez_result(job["prompt"], job["answer"], job_id))
        elif mode == "Chat":
            self.send_html(page_chat_result(job["prompt"], job["answer"], job_id))
        else:
            self.send_html(page_ask_result(job["prompt"], job["answer"], job_id))

        # Cleanup old jobs (with lock to prevent race condition)
        with job_lock:
            if len(jobs) > 10:
                for k in sorted(jobs.keys(), key=int)[:-10]:
                    if k in jobs:  # Double-check before deleting
                        del jobs[k]

    def handle_text(self, job_id):
        """Serve answer as plain text for easy Cmd+A, Cmd+C."""
        if job_id not in jobs or jobs[job_id]["status"] != "done":
            self.send_text("Job nicht gefunden oder noch nicht fertig.")
            return
        self.send_text(sanitize(jobs[job_id]["answer"]))

    def handle_proxy(self, url):
        """Handle web proxy requests."""
        if not url:
            self.send_html(page_proxy())
            return

        # Validate URL
        if not url.startswith('http://') and not url.startswith('https://'):
            self.send_html(page_proxy_error(url, "URL muss mit http:// oder https:// beginnen"))
            return

        logging.info(f"Proxy request: {url}")
        start_time = time.time()

        # Fetch the page
        html_content, final_url, error = fetch_https_page(url)

        if error:
            logging.warning(f"Proxy error for {url}: {error}")
            self.send_html(page_proxy_error(url, error))
            return

        fetch_time = time.time() - start_time
        logging.info(f"Page fetched in {fetch_time:.1f}s: {len(html_content)} bytes")

        # Simplify and send
        try:
            simplify_start = time.time()
            result = page_proxy_result(url, html_content, final_url)
            simplify_time = time.time() - simplify_start

            # Use sanitize to ensure ISO-8859-1 compatibility
            result = sanitize(result)

            total_time = time.time() - start_time
            logging.info(f"Proxy success: {url} (fetch: {fetch_time:.1f}s, process: {simplify_time:.1f}s, total: {total_time:.1f}s)")

            self.send_html(result)
        except Exception as e:
            logging.error(f"Proxy processing error for {url}: {str(e)}")
            self.send_html(page_proxy_error(url, f"Fehler beim Verarbeiten der Seite: {str(e)}"))

    def handle_proxy_image(self, url):
        """Handle image proxy requests - fetch HTTPS images and serve as HTTP."""
        if not url:
            self.send_error(400, "No URL specified")
            return

        # Validate URL
        if not url.startswith('http://') and not url.startswith('https://'):
            self.send_error(400, "Invalid URL")
            return

        logging.debug(f"Image proxy request: {url}")

        # Fetch and optimize the image
        image_data, content_type, error = fetch_image(url)

        if error:
            logging.warning(f"Image proxy error for {url}: {error}")
            # Send a 1x1 transparent GIF as fallback
            try:
                self.send_response(200)
                self.send_header("Content-Type", "image/gif")
                # 1x1 transparent GIF
                transparent_gif = b'GIF89a\x01\x00\x01\x00\x80\x00\x00\xff\xff\xff\x00\x00\x00!\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;'
                self.send_header("Content-Length", str(len(transparent_gif)))
                self.send_header("Connection", "close")
                self.end_headers()
                self.wfile.write(transparent_gif)
            except (BrokenPipeError, ConnectionResetError, OSError):
                # Client disconnected, ignore
                pass
            return

        # Send the optimized image
        try:
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(image_data)))
            self.send_header("Connection", "close")
            self.end_headers()
            self.wfile.write(image_data)
            logging.debug(f"Image proxy success: {url} ({len(image_data)} bytes)")
        except (BrokenPipeError, ConnectionResetError, OSError) as e:
            # Netscape 3 disconnected early - this is normal for slow connections
            # Don't log as error, just debug
            logging.debug(f"Client disconnected during image transfer: {url}")

    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length).decode("iso-8859-1", errors="replace")
        params = parse_qs(body)
        path = urlparse(self.path).path

        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not api_key:
            self.send_html(html_page("Error",
                "<P><B>ANTHROPIC_API_KEY not set!</B></P>"
                "<PRE>export ANTHROPIC_API_KEY='sk-ant-...'</PRE>"))
            return

        if path == "/code":
            prompt = params.get("prompt", [""])[0]
            code = params.get("code", [""])[0]
            full = prompt + (f"\n\nHere is the code:\n\n{code}" if code else "")
            job_id = create_job("Code", full, SYSTEM_PROMPT_CODE)
            self.send_html(page_waiting(job_id, "Code"))

        elif path == "/rez":
            prompt = params.get("prompt", [""])[0]
            types = params.get("types", [""])[0]
            full = prompt + (f"\n\nRequired resource types: {types}" if types else "")
            job_id = create_job("Rez", full, SYSTEM_PROMPT_REZ)
            self.send_html(page_waiting(job_id, "Rez"))

        elif path == "/ask":
            prompt = params.get("prompt", [""])[0]
            job_id = create_job("Frage", prompt, SYSTEM_PROMPT_GENERAL)
            self.send_html(page_waiting(job_id, "Frage"))

        elif path == "/chat":
            message = params.get("message", [""])[0]
            if not message.strip():
                self.send_html(html_page("Fehler", '<P>Bitte eine Nachricht eingeben.</P><P><A HREF="/chat">Zurueck</A></P>'))
                return

            # Add context from recent chat history
            context = get_chat_context()
            full_prompt = context + f"New message:\n{message}" if context else message

            job_id = create_job("Chat", message, SYSTEM_PROMPT_CHAT, is_chat=True)
            self.send_html(page_waiting(job_id, "Chat"))

        elif path == "/save":
            filename = params.get("filename", ["output.txt"])[0]
            content = params.get("content", [""])[0]
            # Sanitize filename: only allow alphanumeric, dots, dashes, underscores
            import re
            filename = re.sub(r'[^a-zA-Z0-9._-]', '_', filename)
            # Prevent hidden files and ensure non-empty
            if not filename or filename.startswith('.'):
                filename = "output.txt"
            self.send_html(page_save_result(filename, save_shared_file(filename, content)))

        else:
            self.send_error(404)

    def send_html(self, content):
        data = content.encode("iso-8859-1", errors="replace")
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(data)

    def send_text(self, content):
        data = content.encode("iso-8859-1", errors="replace")
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, format, *args):
        logging.info(f"{args[0]}")

# --- Main ---

def load_api_key():
    """Load API key from multiple locations (in priority order):
    1. Environment variable (already set via export)
    2. ~/.config/anthropic/api_key
    3. .env file in script directory
    """
    # 1. Already in environment?
    if os.environ.get("ANTHROPIC_API_KEY"):
        logging.info("API Key: loaded from environment variable")
        return

    # 2. ~/.config/anthropic/api_key
    config_file = Path.home() / ".config" / "anthropic" / "api_key"
    if config_file.exists():
        key = config_file.read_text().strip()
        if key:
            os.environ["ANTHROPIC_API_KEY"] = key
            logging.info(f"API Key: loaded from {config_file}")
            return

    # 3. .env file next to script
    env_file = Path(__file__).parent / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip().strip("'").strip('"')
                os.environ[key] = value
        if os.environ.get("ANTHROPIC_API_KEY"):
            logging.info(f"API Key: loaded from {env_file}")
            return

def main():
    # Setup logging first (before anything else)
    setup_logging()

    # Load configuration
    load_config()

    parser = argparse.ArgumentParser(description="Claude Bridge Server")
    parser.add_argument("--port", type=int, default=CONFIG["server"]["port"])
    parser.add_argument("--host", default=CONFIG["server"]["host"])
    parser.add_argument("--shared-folder", default=CONFIG["files"]["shared_folder"])
    parser.add_argument("--config", default="config.yaml", help="Path to config file")
    args = parser.parse_args()

    # Reload config if custom path specified
    if args.config != "config.yaml":
        load_config(args.config)

    global SHARED_FOLDER, CLAUDE_MODEL, MAX_TOKENS, REFRESH_SECONDS, JOB_TIMEOUT_SECONDS
    SHARED_FOLDER = args.shared_folder or CONFIG["files"]["shared_folder"]
    CLAUDE_MODEL = CONFIG["claude"]["model"]
    MAX_TOKENS = CONFIG["claude"]["max_tokens"]
    REFRESH_SECONDS = CONFIG["jobs"]["refresh_interval"]
    JOB_TIMEOUT_SECONDS = CONFIG["jobs"]["timeout"]

    # Load API key from config files
    load_api_key()

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        logging.warning("=" * 60)
        logging.warning("ANTHROPIC_API_KEY nicht gefunden!")
        logging.warning("")
        logging.warning("Option 1 (empfohlen):")
        logging.warning("  mkdir -p ~/.config/anthropic")
        logging.warning("  echo 'sk-ant-...' > ~/.config/anthropic/api_key")
        logging.warning("  chmod 600 ~/.config/anthropic/api_key")
        logging.warning("")
        logging.warning("Option 2: .env Datei im Script-Ordner")
        logging.warning("Option 3: export ANTHROPIC_API_KEY='sk-ant-...'")
        logging.warning("=" * 60)
    else:
        logging.info(f"API Key: ...{api_key[-8:]}")

    server = HTTPServer((args.host, args.port), BridgeHandler)
    logging.info("=" * 60)
    logging.info(f"Claude Bridge Server 1.2")
    logging.info(f"Server: http://{args.host}:{args.port}/")
    logging.info(f"Shared: {SHARED_FOLDER or '(not set)'}")
    logging.info(f"Model: {CLAUDE_MODEL}")
    logging.info(f"Config: {args.config}")
    logging.info("=" * 60)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logging.info("\n" + "=" * 60)
        logging.info("Shutdown signal received, shutting down...")

        # Signal shutdown to running jobs
        shutdown_event.set()

        # Wait for running jobs to complete (max 30 seconds)
        logging.info("Warte auf laufende Jobs...")
        max_wait = 30
        start_wait = time.time()

        while time.time() - start_wait < max_wait:
            with job_lock:
                working_jobs = [j for j in jobs.values() if j["status"] == "working"]
            if not working_jobs:
                break
            logging.info(f"Noch {len(working_jobs)} Job(s) aktiv...")
            time.sleep(2)

        with job_lock:
            working_jobs = [j for j in jobs.values() if j["status"] == "working"]
            if working_jobs:
                logging.warning(f"{len(working_jobs)} Job(s) wurden nicht rechtzeitig beendet")
            else:
                logging.info("Alle Jobs abgeschlossen")

        server.server_close()
        logging.info("Server beendet.")
        logging.info("=" * 60)

if __name__ == "__main__":
    main()


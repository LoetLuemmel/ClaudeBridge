"""
Character Encoding Utilities for Classic Mac Compatibility
===========================================================

CRITICAL: DO NOT MODIFY without testing on Classic Mac!

These functions handle the ISO-8859-1 encoding that is essential for
Netscape Navigator 3 on MacOS 7.5. The encoding has been extensively
tested and works perfectly with umlauts (ä, ö, ü, ß).

Functions:
- sanitize(): Convert Unicode to ISO-8859-1 safe text
- format_for_netscape(): Format text for Netscape 3 display
- strip_markdown(): Strip markdown/HTML for plain text export
"""

import unicodedata
import re


def escape_html(text, quote=False):
    """Escape HTML special characters for Netscape Navigator 3.

    Replaces html.escape(), which is NOT usable here: it emits hexadecimal
    character references (' -> &#x27;, introduced in HTML 4.0). Netscape 3
    only understands HTML 3.2 and renders those literally, so an answer came
    out as "I&#x27;m doing wonderfully" on screen.

    Only &, < and > are escaped. Apostrophes are left alone - all attributes
    in the templates are delimited with double quotes, so ' is harmless there
    and needs no reference at all.

    Args:
        text: Text to escape
        quote: If True, also escape " as &quot; (for attribute values)
    """
    text = text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
    if quote:
        text = text.replace('"', '&quot;')
    return text


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

def strip_markdown(text):
    """Strip ALL markdown, HTML, and explanatory text for plain text export.

    Aggressively extracts ONLY code/technical content by:
    - Removing explanatory sentences before code blocks
    - Extracting just the code from between ``` markers
    - Removing all markdown formatting
    - Removing HTML tags

    Returns clean plain text suitable for copying to clipboard.
    """
    import re

    # FIRST: Extract code blocks BEFORE doing any HTML tag removal
    # This prevents HTML stripping from corrupting C operators like <, >, <=, >=
    code_block_pattern = r'```[a-zA-Z]*\n(.*?)\n```'
    code_blocks = re.findall(code_block_pattern, text, re.DOTALL)

    if code_blocks:
        # If we found code blocks, extract ONLY the code
        # This removes all explanatory text like "Here's the modified code..."
        extracted_code = '\n\n'.join(code_blocks)

        # Only remove safe HTML tags that format_for_netscape might have added
        # Do NOT use generic HTML removal that could corrupt C operators
        extracted_code = re.sub(r'<BR\s*/?\s*>', '\n', extracted_code, flags=re.IGNORECASE)
        extracted_code = re.sub(r'<P\s*/?\s*>', '\n\n', extracted_code, flags=re.IGNORECASE)
        extracted_code = re.sub(r'</P\s*>', '', extracted_code, flags=re.IGNORECASE)

        return extracted_code.strip()

    # If no code blocks found, do full cleanup on non-code text
    # Remove HTML tags that might have been added during formatting
    text = re.sub(r'<BR\s*/?\s*>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'<P\s*/?\s*>', '\n\n', text, flags=re.IGNORECASE)
    text = re.sub(r'</P\s*>', '', text, flags=re.IGNORECASE)

    # For non-code text, safe to remove HTML tags (but still preserve <file.h>)
    # Pattern: </?[^.>]+> matches <tag> but NOT <file.h>
    text = re.sub(r'</?[^.>]+>', '', text)

    # If no code blocks found, clean up the text
    # Remove markdown code block markers (```language ... ```)
    text = re.sub(r'```[a-zA-Z]*\n?', '', text)

    # Remove inline code backticks (`code`)
    text = re.sub(r'`([^`]+)`', r'\1', text)

    # Remove bold/italic markers
    text = re.sub(r'\*\*\*([^*]+)\*\*\*', r'\1', text)  # ***text***
    text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)      # **text**
    text = re.sub(r'\*([^*]+)\*', r'\1', text)          # *text*
    text = re.sub(r'___([^_]+)___', r'\1', text)        # ___text___
    text = re.sub(r'__([^_]+)__', r'\1', text)          # __text__
    text = re.sub(r'_([^_]+)_', r'\1', text)            # _text_

    # Remove headings (##, ###, etc.)
    text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)

    # Remove markdown links [text](url) - keep just the text
    text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)

    # Remove horizontal rules (---, ***, ___)
    text = re.sub(r'^(\*{3,}|-{3,}|_{3,})$', '', text, flags=re.MULTILINE)

    # Remove blockquote markers (>)
    text = re.sub(r'^>\s+', '', text, flags=re.MULTILINE)

    # Remove list markers (-, *, +, 1., 2., etc.)
    text = re.sub(r'^[\s]*[-*+]\s+', '', text, flags=re.MULTILINE)
    text = re.sub(r'^[\s]*\d+\.\s+', '', text, flags=re.MULTILINE)

    # Clean up multiple blank lines to max 2
    text = re.sub(r'\n{3,}', '\n\n', text)

    return text.strip()

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
            # The join is done outside the f-string on purpose: before Python
            # 3.12, an f-string expression may not contain a backslash, and
            # "\n" inside the braces is a SyntaxError at import time on 3.11.
            code_block = "\n".join(code_lines)
            result.append(f'<PRE>{escape_html(code_block)}</PRE>')
        else:
            # For normal text, escape FIRST, then add <BR> tags
            # This prevents the <BR> tags from being escaped
            para = escape_html(para)
            para = para.replace('\n', '<BR>\n')
            result.append(f'<P>{para}</P>')

    return '\n'.join(result)

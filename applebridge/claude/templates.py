"""
HTML 3.2 Templates for Netscape Navigator 3
============================================

All HTML templates for the Claude Interface.
Compatible with HTML 3.2 (no CSS, no JavaScript).
"""

import time
from applebridge.encoding import sanitize, format_for_netscape, escape_html
from applebridge.claude.files import list_shared_files, read_shared_file
from applebridge.claude.history import get_all_history, get_all_chat_history
from applebridge.config import CONFIG


def html_page(title, body, back=True, refresh_url=None, refresh_sec=None):
    """Base HTML page template."""
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
<A HREF="/history">History</A> |
<A HREF="/setup">Setup</A>
</FONT></TD>
</TR>
</TABLE>"""
    refresh_tag = ""
    if refresh_url and refresh_sec:
        refresh_tag = f'<META HTTP-EQUIV="Refresh" CONTENT="{refresh_sec};URL={refresh_url}">'
    return f"""\
<HTML>
<HEAD><TITLE>{title} - ClaudeBridge</TITLE>
{refresh_tag}
</HEAD>
<BODY BGCOLOR="#EEEEEE" TEXT="#000000" LINK="#0000CC" VLINK="#660099">
<TABLE WIDTH="100%" BGCOLOR="#333366" CELLPADDING="8" CELLSPACING="0">
<TR><TD><FONT SIZE="+2" COLOR="#FFFFFF"><B>{title}</B></FONT></TD>
<TD ALIGN="RIGHT"><FONT SIZE="-1" COLOR="#CCCCCC">ClaudeBridge 2.0</FONT></TD></TR>
</TABLE>
{nav}
{body}
</BODY>
</HTML>"""


def page_index():
    """Home page."""
    return html_page("ClaudeBridge for Classic Mac", """
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


def page_waiting(job_id, job_started):
    """Loading page with auto-refresh."""
    elapsed = int(time.time() - job_started)
    refresh_sec = CONFIG["jobs"]["refresh_interval"]
    return html_page(f"Claude is thinking...", f"""
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
""", refresh_url=f"/result/{job_id}", refresh_sec=refresh_sec)


def page_code():
    """Code Assistant form."""
    return html_page("Code Assistant", """
<P>Describe what you need, or paste code for Claude to analyze.</P>
<FORM METHOD="POST" ACTION="/code">
<P><B>Your question / task:</B><BR>
<TEXTAREA NAME="prompt" ROWS="8" COLS="72" WRAP="virtual"></TEXTAREA></P>
<P><B>Existing code (optional):</B><BR>
<TEXTAREA NAME="code" ROWS="12" COLS="72" WRAP="off"></TEXTAREA></P>
<P><B>&gt;&gt;</B> <INPUT TYPE="SUBMIT" VALUE=" Send to Claude "> <B>&lt;&lt;</B>
&nbsp;&nbsp;<FONT SIZE="-1">(Tab to button, press Enter to submit)</FONT></P>
</FORM>
""")


def page_code_result(question, answer, job_id=None):
    """Code Assistant result page."""
    formatted_answer = format_for_netscape(sanitize(answer))
    q_escaped = escape_html(sanitize(question))
    save_val = escape_html(sanitize(answer), quote=True)
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
<P><B>&gt;&gt;</B> <INPUT TYPE="SUBMIT" VALUE=" Ask again "> <B>&lt;&lt;</B></P>
</FORM>
""")


def page_rez():
    """Resource Generator form."""
    return html_page("Resource Generator", """
<P>Describe the resources you need.</P>
<FORM METHOD="POST" ACTION="/rez">
<P><B>What resources do you need?</B><BR>
<TEXTAREA NAME="prompt" ROWS="6" COLS="72" WRAP="virtual"></TEXTAREA></P>
<P><B>Resource types (optional):</B><BR>
<INPUT TYPE="TEXT" NAME="types" SIZE="60" VALUE="MENU, DLOG, DITL"></P>
<P><B>&gt;&gt;</B> <INPUT TYPE="SUBMIT" VALUE=" Generate Rez "> <B>&lt;&lt;</B>
&nbsp;&nbsp;<FONT SIZE="-1">(Tab to button, press Enter)</FONT></P>
</FORM>
""")


def page_rez_result(question, answer, job_id=None):
    """Resource Generator result page."""
    formatted_answer = format_for_netscape(sanitize(answer))
    save_val = escape_html(sanitize(answer), quote=True)
    text_link = f'<A HREF="/text/{job_id}"><B>[ Plain Text - for copying ]</B></A>' if job_id else ""
    shared_folder = CONFIG["files"]["shared_folder"]
    save_section = ""
    if shared_folder:
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
<BLOCKQUOTE>{escape_html(sanitize(question))}</BLOCKQUOTE>
<HR>
<P><B>Rez source code:</B> {text_link}</P>
{formatted_answer}
{save_section}
<HR>
<P><A HREF="/rez">Generate new resources</A></P>
""")


def page_ask():
    """Ask & Answer form."""
    return html_page("Ask &amp; Answer", """
<P>Ask a question about Classic Mac programming.</P>
<FORM METHOD="POST" ACTION="/ask">
<P><B>Your question:</B><BR>
<TEXTAREA NAME="prompt" ROWS="6" COLS="72" WRAP="virtual"></TEXTAREA></P>
<P><B>&gt;&gt;</B> <INPUT TYPE="SUBMIT" VALUE=" Ask Claude "> <B>&lt;&lt;</B>
&nbsp;&nbsp;<FONT SIZE="-1">(Tab to button, press Enter)</FONT></P>
</FORM>
""")


def page_ask_result(question, answer, job_id=None):
    """Ask & Answer result page."""
    formatted_answer = format_for_netscape(sanitize(answer))
    text_link = f'<A HREF="/text/{job_id}"><B>[ Plain Text - for copying ]</B></A>' if job_id else ""
    return html_page("Ask &amp; Answer -- Result", f"""
<P><B>Your question:</B></P>
<BLOCKQUOTE>{escape_html(sanitize(question))}</BLOCKQUOTE>
<HR>
<P><B>Answer:</B> {text_link}</P>
{formatted_answer}
<HR>
<FORM METHOD="POST" ACTION="/ask">
<P><B>Follow-up question:</B><BR>
<TEXTAREA NAME="prompt" ROWS="4" COLS="72" WRAP="virtual"></TEXTAREA></P>
<P><B>&gt;&gt;</B> <INPUT TYPE="SUBMIT" VALUE=" Ask again "> <B>&lt;&lt;</B></P>
</FORM>
""")


def page_files(subfolder=""):
    """Shared folder file browser."""
    files = list_shared_files(subfolder)
    shared_folder = CONFIG["files"]["shared_folder"]
    if not shared_folder:
        content = "<P><I>No shared folder configured.</I></P>"
    elif not files:
        content = "<P><I>No files found.</I></P>"
    else:
        rows = ""
        for f in files:
            name = f["name"]
            if f["is_dir"]:
                sub = subfolder + "/" + name if subfolder else name
                link = f'<A HREF="/files?sub={escape_html(sub)}">{escape_html(name)}/</A>'
                size = "[Folder]"
            else:
                sub = subfolder + "/" + name if subfolder else name
                link = f'<A HREF="/readfile?name={escape_html(sub)}">{escape_html(name)}</A>'
                size = f'{f["size"]:,} Bytes'
            rows += f"<TR><TD>{link}</TD><TD ALIGN='RIGHT'>{size}</TD></TR>\n"
        content = f"""
<TABLE BORDER="1" CELLPADDING="4" CELLSPACING="0" WIDTH="80%">
<TR BGCOLOR="#CCCCCC"><TH ALIGN="LEFT">File</TH><TH ALIGN="RIGHT">Size</TH></TR>
{rows}
</TABLE>"""
    return html_page("Shared Folder", f"""
<P><B>Path:</B> <CODE>{escape_html(shared_folder or '(not set)')}</CODE>
{(' / ' + escape_html(subfolder)) if subfolder else ''}</P>
{content}
""")


def page_readfile(filename):
    """Display file content with option to send to Claude."""
    content = read_shared_file(filename)
    if content is None:
        return html_page("File not found",
            f"<P>File <CODE>{escape_html(filename)}</CODE> not found.</P>")
    escaped = escape_html(sanitize(content))
    content_val = escape_html(sanitize(content), quote=True)
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
    """Result page after saving a file."""
    if success:
        msg = f'<P>File <CODE>{escape_html(filename)}</CODE> saved.</P>'
        msg += '<P><A HREF="/files">Go to Shared Folder</A></P>'
    else:
        msg = '<P><B>Error:</B> File could not be saved.</P>'
    return html_page("Save File", msg)


def page_history():
    """History page showing past conversations."""
    conversation_history = get_all_history()
    chat_history = get_all_chat_history()

    if not conversation_history and not chat_history:
        content = "<P><I>No questions asked yet.</I></P>"
    else:
        # Code/Rez/Ask history
        code_section = ""
        if conversation_history:
            rows = ""
            for idx, entry in enumerate(reversed(conversation_history)):
                entry_id = len(conversation_history) - idx - 1
                # Truncate for overview
                q_preview = entry['question'][:100]
                if len(entry['question']) > 100:
                    q_preview += "..."
                a_preview = entry['answer'][:150]
                if len(entry['answer']) > 150:
                    a_preview += "..."
                rows += f"""
<TR BGCOLOR="#FFFFFF">
<TD VALIGN="TOP"><FONT SIZE="-1">{entry['time']}<BR><B>{entry['mode']}</B></FONT></TD>
<TD VALIGN="TOP"><A HREF="/history/{entry_id}">{escape_html(sanitize(q_preview))}</A></TD>
<TD VALIGN="TOP"><FONT SIZE="-1">{escape_html(sanitize(a_preview))}</FONT></TD>
</TR>"""
            code_section = f"""
<P><B>Code / Rez / Ask History:</B></P>
<TABLE BORDER="1" CELLPADDING="4" CELLSPACING="0" WIDTH="100%">
<TR BGCOLOR="#CCCCCC"><TH>Time</TH><TH>Question (click to expand)</TH><TH>Answer Preview</TH></TR>
{rows}
</TABLE>
<BR>"""

        # Chat history
        chat_section = ""
        if chat_history:
            chat_rows = ""
            for idx, entry in enumerate(reversed(chat_history)):
                entry_id = len(chat_history) - idx - 1
                q_preview = entry['question'][:100]
                if len(entry['question']) > 100:
                    q_preview += "..."
                a_preview = entry['answer'][:150]
                if len(entry['answer']) > 150:
                    a_preview += "..."
                chat_rows += f"""
<TR BGCOLOR="#FFFFF0">
<TD VALIGN="TOP"><FONT SIZE="-1">{entry['time']}</FONT></TD>
<TD VALIGN="TOP"><A HREF="/history/chat/{entry_id}">{escape_html(sanitize(q_preview))}</A></TD>
<TD VALIGN="TOP"><FONT SIZE="-1">{escape_html(sanitize(a_preview))}</FONT></TD>
</TR>"""
            chat_section = f"""
<P><B>Chat History:</B></P>
<TABLE BORDER="1" CELLPADDING="4" CELLSPACING="0" WIDTH="100%">
<TR BGCOLOR="#CCCCCC"><TH>Time</TH><TH>Message (click to expand)</TH><TH>Answer Preview</TH></TR>
{chat_rows}
</TABLE>"""

        content = code_section + chat_section
    return html_page("History", content)


def page_history_detail(entry_id):
    """Show full details of a single history entry."""
    conversation_history = get_all_history()
    if entry_id < 0 or entry_id >= len(conversation_history):
        return html_page("History Entry Not Found", "<P><I>History entry not found.</I></P>")

    entry = conversation_history[entry_id]
    formatted_answer = format_for_netscape(sanitize(entry['answer']))

    return html_page(f"History - {entry['mode']} ({entry['time']})", f"""
<P><B>Mode:</B> {entry['mode']} &nbsp;&nbsp; <B>Time:</B> {entry['time']}</P>
<HR>
<P><B>Question:</B></P>
<BLOCKQUOTE>{escape_html(sanitize(entry['question']))}</BLOCKQUOTE>
<HR>
<P><B>Answer:</B></P>
{formatted_answer}
<HR>
<P><A HREF="/history">Back to History</A></P>
""")


def page_chat_history_detail(entry_id):
    """Show full details of a single chat history entry."""
    chat_history = get_all_chat_history()
    if entry_id < 0 or entry_id >= len(chat_history):
        return html_page("Chat History Entry Not Found", "<P><I>Chat entry not found.</I></P>")

    entry = chat_history[entry_id]
    formatted_answer = format_for_netscape(sanitize(entry['answer']))

    return html_page(f"Chat History ({entry['time']})", f"""
<P><B>Time:</B> {entry['time']}</P>
<HR>
<P><B>You:</B></P>
<BLOCKQUOTE>{escape_html(sanitize(entry['question']))}</BLOCKQUOTE>
<HR>
<P><B>Claude:</B></P>
{formatted_answer}
<HR>
<P><A HREF="/history">Back to History</A></P>
""")


def page_chat():
    """Claude Chat interface."""
    # Show recent chat history
    chat_history = get_all_chat_history()
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
<P>{escape_html(sanitize(entry['question']))}</P>
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
<P><B>&gt;&gt;</B> <INPUT TYPE="SUBMIT" VALUE=" Send to Claude "> <B>&lt;&lt;</B>
&nbsp;&nbsp;<FONT SIZE="-1">(Tab to button, press Enter)</FONT></P>
</FORM>
{history_html}
<HR>
<P><A HREF="/chat/clear">Clear chat history</A></P>
""")


def page_chat_result(question, answer, job_id=None):
    """Display chat response."""
    # Format answer for Netscape 3 (with proper line wrapping)
    formatted_answer = format_for_netscape(sanitize(answer))

    # For question display: truncate if very long (avoid showing entire code blocks)
    # Show only first 200 chars to remind user what they asked
    question_preview = question[:200] + "..." if len(question) > 200 else question
    q_escaped = escape_html(sanitize(question_preview))

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
<P><B>&gt;&gt;</B> <INPUT TYPE="SUBMIT" VALUE=" Send message "> <B>&lt;&lt;</B></P>
</FORM>
<HR>
<P><A HREF="/chat">Back to Chat</A> | <A HREF="/chat/clear">Clear chat history</A></P>
""")


def page_text(content):
    """Plain text page for copying to clipboard."""
    # No sanitize - keep original for copy-paste
    return f"""Content-Type: text/plain; charset=utf-8

{content}"""

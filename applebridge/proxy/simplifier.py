"""
HTML Simplifier and Proxy Templates
====================================

Converts modern HTML to HTML 3.2 compatible markup for Netscape Navigator 3.
"""

import logging
import re
from bs4 import BeautifulSoup
from urllib.parse import urljoin

from applebridge.encoding import sanitize, escape_html
from applebridge.proxy.cache import get_cache_stats


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

    # Remove forms entirely (they won't work through proxy - no POST support)
    for form in soup.find_all('form'):
        # Replace form with a message
        message = soup.new_tag('p')
        message.string = '[Form removed - forms don\'t work through proxy]'
        form.replace_with(message)

    # Get body content only (to avoid duplicate head tags)
    body = soup.find('body')
    if body:
        # Convert body tag to a plain div to avoid nesting issues
        body_html = str(body)
        # Remove <body> tags but keep content
        body_html = body_html.replace('<body>', '<div>').replace('</body>', '</div>')
        # Remove body attributes from opening tag
        body_html = re.sub(r'<div[^>]*>', '<div>', body_html, count=1)
        return body_html
    else:
        return str(soup)


def html_page(title, body, back=True, refresh_url=None, refresh_sec=None):
    """Base HTML page template for proxy pages."""
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


def page_proxy():
    """Web Proxy entry page."""
    # Get cache stats
    stats = get_cache_stats()
    cache_size = stats["size"]
    if cache_size > 0:
        cache_stats = f"<P><FONT SIZE='-1'><I>Image cache: {cache_size} entries, {stats['memory_kb']:.1f} KB</I></FONT></P>"
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
<HEAD><TITLE>Proxy: {escape_html(url)}</TITLE></HEAD>
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
<TR><TD><FONT SIZE="-1"><B>URL:</B> {escape_html(url)}</FONT></TD></TR>
</TABLE>
{simplified}
</BODY>
</HTML>"""


def page_proxy_error(url, error):
    """Display proxy error page."""
    return html_page("Web Proxy - Error", f"""
<P><B>Error loading URL:</B></P>
<BLOCKQUOTE><CODE>{escape_html(url)}</CODE></BLOCKQUOTE>
<P><B>Error message:</B></P>
<PRE>{escape_html(error)}</PRE>
<P><A HREF="/web">Back to Web Proxy</A></P>
""")

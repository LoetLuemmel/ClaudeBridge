"""
HTTPS Page Fetcher
==================

Fetches HTTPS pages for the web proxy.
"""

import urllib.request
import urllib.error


def fetch_https_page(url):
    """Fetch a page via HTTPS and return content + final URL.

    Args:
        url: URL to fetch

    Returns:
        Tuple of (html_content, final_url, error)
        - html_content: Page HTML as string (or None on error)
        - final_url: Final URL after redirects
        - error: Error message (or None on success)
    """
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

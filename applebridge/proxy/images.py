"""
Image Optimization for Web Proxy
=================================

Fetches and optimizes images for Netscape Navigator 3 on Classic Mac.
"""

import time
import logging
import urllib.request
import urllib.error
from PIL import Image
from io import BytesIO

from applebridge.proxy.cache import get_cached_image, cache_image
from applebridge.proxy.ratelimit import wait_for_rate_limit
from applebridge.proxy.ssrf import check_url, build_opener


def fetch_image(url, max_width=500, max_size_kb=50):
    """Fetch an image via HTTPS, optimize it for Netscape 3 on Classic Mac, and return binary content.

    Optimizations for Classic Mac OS (balanced quality/size):
    - Resize large images (max_width=500px - good balance)
    - Compress to target max_size_kb (default 50 KB - reasonable size)
    - Convert to GIF with adaptive palette (32-64 colors)
    - SVG files: Return transparent GIF placeholder (Netscape 3 can't display SVG)
    - Cache optimized images for 1 hour

    Args:
        url: Image URL
        max_width: Maximum width in pixels
        max_size_kb: Target maximum size in KB

    Returns:
        Tuple of (image_data, content_type, error)
    """
    # Reject local/private targets before touching the cache or the network
    blocked = check_url(url)
    if blocked:
        return None, None, blocked

    # Check cache first
    cached = get_cached_image(url)
    if cached:
        return cached

    try:
        # Rate limiting: prevent too many requests to the same domain
        wait_for_rate_limit(url)

        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; U; PPC Mac OS 7.5; en-US) Netscape/3.04'
        }
        req = urllib.request.Request(url, headers=headers)
        with build_opener().open(req, timeout=30) as response:
            original_content = response.read()
            original_type = response.headers.get('Content-Type', 'image/jpeg')
            original_size_kb = len(original_content) / 1024

            # Check if SVG (Netscape 3 can't display SVG anyway)
            if 'svg' in original_type.lower() or url.lower().endswith('.svg'):
                logging.debug(f"SVG detected, returning transparent GIF placeholder: {url}")
                # Return 1x1 transparent GIF
                transparent_gif = b'GIF89a\x01\x00\x01\x00\x80\x00\x00\xff\xff\xff\x00\x00\x00!\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;'
                # Cache SVG placeholders too
                cache_image(url, transparent_gif, 'image/gif')
                return transparent_gif, 'image/gif', None

            logging.debug(f"Image fetched: {url} ({original_size_kb:.1f} KB, {original_type})")

            # If image is already GIF and small enough, return as-is (don't re-convert!)
            if 'gif' in original_type.lower() and original_size_kb <= max_size_kb:
                logging.debug(f"GIF passed through: {url} ({original_size_kb:.1f} KB)")
                # Cache the original GIF
                cache_image(url, original_content, original_type)
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
                cache_image(url, optimized_content, mime_type)

                return optimized_content, mime_type, None

            except Exception as e:
                # If Pillow fails, return original
                logging.warning(f"Image optimization failed, returning original: {str(e)}")
                # Still cache the original
                cache_image(url, original_content, original_type)
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
                with build_opener().open(req, timeout=30) as response:
                    content = response.read()
                    content_type = response.headers.get('Content-Type', 'image/jpeg')
                    # Cache the retry result
                    cache_image(url, content, content_type)
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

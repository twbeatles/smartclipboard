"""Remote title fetch helpers."""

from __future__ import annotations

import logging
import re
from typing import Any, Optional
from urllib.parse import urljoin

from .cache import TITLE_FETCH_MAX_BYTES, TITLE_FETCH_MAX_REDIRECTS, URL_TRAILING_PUNCTUATION
from .network_guard import is_blocked_title_fetch_reason, validate_title_fetch_url

requests: Any | None
BeautifulSoup: Any | None

try:
    import requests as _requests
    from bs4 import BeautifulSoup as _BeautifulSoup
except ImportError:
    requests = None
    BeautifulSoup = None
    HAS_WEB = False
else:
    requests = _requests
    BeautifulSoup = _BeautifulSoup
    HAS_WEB = True

logger = logging.getLogger(__name__)


def normalize_extracted_url(url: str) -> str:
    return url.rstrip(URL_TRAILING_PUNCTUATION)


def extract_first_url(text: str) -> Optional[str]:
    if not text:
        return None
    match = re.search(r"https?://[^\s<>'\"\]\)]+", text)
    return normalize_extracted_url(match.group(0)) if match else None


def fetch_title_logic(url, item_id=None):
    response = None
    try:
        if requests is None or BeautifulSoup is None:
            return {"title": None, "item_id": item_id, "url": url, "error": "web libraries unavailable"}
        current_url = url
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        for _redirect_index in range(TITLE_FETCH_MAX_REDIRECTS + 1):
            is_safe, reason = validate_title_fetch_url(current_url)
            if not is_safe:
                logger.info("Title fetch blocked for %s: %s", current_url, reason)
                return {"title": None, "item_id": item_id, "url": url, "error": reason}

            response = requests.get(
                current_url,
                headers=headers,
                timeout=(3, 5),
                verify=True,
                stream=True,
                allow_redirects=False,
            )
            if 300 <= response.status_code < 400:
                location = str(response.headers.get("Location", "") or "").strip()
                if not location:
                    return {"title": None, "item_id": item_id, "url": url, "error": "redirect missing location"}
                next_url = normalize_extracted_url(urljoin(current_url, location))
                response.close()
                response = None
                current_url = next_url
                continue

            response.raise_for_status()
            content_type = str(response.headers.get("Content-Type", "") or "").lower()
            if content_type and "html" not in content_type:
                return {"title": None, "item_id": item_id, "url": url, "error": f"unsupported content type: {content_type}"}

            html_chunks: list[bytes] = []
            bytes_read = 0
            for chunk in response.iter_content(chunk_size=65536):
                if not chunk:
                    continue
                remaining = TITLE_FETCH_MAX_BYTES - bytes_read
                if remaining <= 0:
                    break
                limited_chunk = chunk[:remaining]
                html_chunks.append(limited_chunk)
                bytes_read += len(limited_chunk)
                if bytes_read >= TITLE_FETCH_MAX_BYTES:
                    break

            html_text = b"".join(html_chunks).decode(response.encoding or "utf-8", errors="replace")
            soup = BeautifulSoup(html_text, "html.parser")
            title = soup.title.string if soup.title else None
            return {"title": title.strip() if title else None, "item_id": item_id, "url": url, "final_url": current_url}

        return {"title": None, "item_id": item_id, "url": url, "error": "too many redirects"}
    except Exception as exc:
        logger.debug("Fetch title error: %s", exc)
        return {"title": None, "item_id": item_id, "url": url, "error": str(exc)}
    finally:
        if response is not None and hasattr(response, "close"):
            try:
                response.close()
            except Exception:
                pass


__all__ = [
    "HAS_WEB",
    "requests",
    "BeautifulSoup",
    "extract_first_url",
    "normalize_extracted_url",
    "fetch_title_logic",
    "is_blocked_title_fetch_reason",
    "validate_title_fetch_url",
]

"""Shared constants for clipboard automation."""

TITLE_FETCH_MAX_BYTES = 1024 * 1024
TITLE_FETCH_MAX_THREADS = 4
TITLE_FETCH_MAX_REDIRECTS = 5
URL_TRAILING_PUNCTUATION = ".,!?:;"
BLOCKED_TITLE_HOSTS = {
    "localhost",
    "metadata.google.internal",
    "metadata.google.internal.",
}

__all__ = [
    "TITLE_FETCH_MAX_BYTES",
    "TITLE_FETCH_MAX_THREADS",
    "TITLE_FETCH_MAX_REDIRECTS",
    "URL_TRAILING_PUNCTUATION",
    "BLOCKED_TITLE_HOSTS",
]

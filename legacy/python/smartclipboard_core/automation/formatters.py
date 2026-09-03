"""Synchronous clipboard text formatters."""

from __future__ import annotations

import re


def _replace_result(text: str, *, original: str | None = None, legacy_type: str = "replace_text"):
    payload = {"type": "replace_text", "text": text}
    if original is not None:
        payload["original"] = original
    # Keep legacy keys for compatibility with older tests/callers.
    if legacy_type == "format":
        payload["formatted"] = text
    elif legacy_type == "transform":
        payload["result"] = text
    return payload


def replacement_text_from_result(result) -> str | None:
    if not isinstance(result, dict):
        return None
    for key in ("text", "formatted", "result"):
        value = result.get(key)
        if value is not None:
            return str(value)
    return None


def format_phone(text: str):
    digits = re.sub(r"\D", "", text)
    if digits.startswith("02") and len(digits) == 9:
        formatted = f"{digits[:2]}-{digits[2:5]}-{digits[5:]}"
        return _replace_result(formatted, original=text, legacy_type="format")
    if digits.startswith("02") and len(digits) == 10:
        formatted = f"{digits[:2]}-{digits[2:6]}-{digits[6:]}"
        return _replace_result(formatted, original=text, legacy_type="format")
    if len(digits) == 8 and digits.startswith(("15", "16", "18")):
        formatted = f"{digits[:4]}-{digits[4:]}"
        return _replace_result(formatted, original=text, legacy_type="format")
    if digits.startswith("0505") and len(digits) == 11:
        formatted = f"{digits[:4]}-{digits[4:7]}-{digits[7:]}"
        return _replace_result(formatted, original=text, legacy_type="format")
    if len(digits) == 11 and digits.startswith("0"):
        formatted = f"{digits[:3]}-{digits[3:7]}-{digits[7:]}"
        return _replace_result(formatted, original=text, legacy_type="format")
    if len(digits) == 10 and digits.startswith("0"):
        formatted = f"{digits[:3]}-{digits[3:6]}-{digits[6:]}"
        return _replace_result(formatted, original=text, legacy_type="format")
    return None


def format_email(text: str):
    email = text.strip().lower()
    return _replace_result(email, original=text, legacy_type="format")


def transform_text(text: str, mode: str):
    if mode == "trim":
        return _replace_result(text.strip(), legacy_type="transform")
    if mode == "upper":
        return _replace_result(text.upper(), legacy_type="transform")
    if mode == "lower":
        return _replace_result(text.lower(), legacy_type="transform")
    return None


__all__ = ["format_phone", "format_email", "replacement_text_from_result", "transform_text"]

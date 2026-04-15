"""Synchronous clipboard text formatters."""

from __future__ import annotations

import re


def format_phone(text: str):
    digits = re.sub(r"\D", "", text)
    if digits.startswith("02") and len(digits) == 9:
        formatted = f"{digits[:2]}-{digits[2:5]}-{digits[5:]}"
        return {"type": "format", "original": text, "formatted": formatted}
    if digits.startswith("02") and len(digits) == 10:
        formatted = f"{digits[:2]}-{digits[2:6]}-{digits[6:]}"
        return {"type": "format", "original": text, "formatted": formatted}
    if len(digits) == 8 and digits.startswith(("15", "16", "18")):
        formatted = f"{digits[:4]}-{digits[4:]}"
        return {"type": "format", "original": text, "formatted": formatted}
    if digits.startswith("0505") and len(digits) == 11:
        formatted = f"{digits[:4]}-{digits[4:7]}-{digits[7:]}"
        return {"type": "format", "original": text, "formatted": formatted}
    if len(digits) == 11 and digits.startswith("0"):
        formatted = f"{digits[:3]}-{digits[3:7]}-{digits[7:]}"
        return {"type": "format", "original": text, "formatted": formatted}
    if len(digits) == 10 and digits.startswith("0"):
        formatted = f"{digits[:3]}-{digits[3:6]}-{digits[6:]}"
        return {"type": "format", "original": text, "formatted": formatted}
    return None


def format_email(text: str):
    email = text.strip().lower()
    return {"type": "format", "original": text, "formatted": email}


def transform_text(text: str, mode: str):
    if mode == "trim":
        return {"type": "transform", "result": text.strip()}
    if mode == "upper":
        return {"type": "transform", "result": text.upper()}
    if mode == "lower":
        return {"type": "transform", "result": text.lower()}
    return None


__all__ = ["format_phone", "format_email", "transform_text"]

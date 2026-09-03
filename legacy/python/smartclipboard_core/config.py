from __future__ import annotations

import os


class Config:
    """SmartClipboard application configuration constants."""

    APP_NAME = "SmartClipboard"
    VERSION = "10.7"

    # Public update-channel metadata is configurable at build/run time.
    # The signing private key must never be present in this repository or an executable.
    UPDATE_MANIFEST_URL = os.environ.get(
        "SMARTCLIPBOARD_UPDATE_MANIFEST_URL",
        (
            "https://raw.githubusercontent.com/"
            "twbeatles/smartclipboard/main/updates/latest.json"
        ),
    )
    UPDATE_PUBLIC_KEY_B64_DEFAULT = "EV71tLaj1Qk4keGFCw3FKmVP7w96sUFDq7D0nJsNyC8="
    UPDATE_PUBLIC_KEY_B64 = os.environ.get(
        "SMARTCLIPBOARD_UPDATE_PUBLIC_KEY_B64",
        UPDATE_PUBLIC_KEY_B64_DEFAULT,
    )
    UPDATE_RELEASES_URL = (
        "https://github.com/twbeatles/smartclipboard/releases/latest"
    )
    UPDATE_MANIFEST_MAX_BYTES = 256 * 1024
    UPDATE_ARTIFACT_MAX_BYTES = 500 * 1024 * 1024
    UPDATE_REQUEST_TIMEOUT_SECONDS = 20.0
    UPDATE_BACKUP_KEEP_COUNT = 2


__all__ = ["Config"]

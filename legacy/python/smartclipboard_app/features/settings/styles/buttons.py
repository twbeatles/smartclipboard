"""QSS section builders for MainWindow themes."""

from __future__ import annotations

from .tokens import derive_tokens


def _build_button_section(theme, glass, tokens=None) -> str:
    t = tokens if tokens is not None else derive_tokens(theme, glass)
    return f"""QPushButton {{
        background-color: {t["surface_high"]};
        border: 1px solid {theme["border"]};
        border-radius: {t["radius_control"]}px;
        padding: 11px 18px;
        color: {theme["text"]};
        font-weight: 600;
        font-size: 13px;
        outline: none;
        min-height: 20px;
    }}
    QPushButton:hover {{
        background-color: {theme["surface_variant"]};
        border-color: {theme["primary"]};
        color: {theme["primary"]};
    }}
    QPushButton:focus {{
        border: 1px solid {theme["primary"]};
    }}
    QPushButton:pressed {{
        background-color: {t["primary_soft"]};
    }}
    QPushButton:disabled {{
        background-color: {theme["surface"]};
        color: {theme["text_secondary"]};
        border-color: {t["divider"]};
    }}

    /* 주요 액션 (복사) - 그라데이션 필 */
    QPushButton#PrimaryBtn {{
        background-color: qlineargradient(x1:0, y1:0, x2:1, y2:1,
            stop:0 {theme.get("gradient_start", theme["primary"])},
            stop:1 {theme.get("gradient_end", theme["primary_variant"])});
        color: {t["on_primary"]};
        border: none;
        font-weight: 700;
        font-size: 14px;
        border-radius: {t["radius_control"]}px;
    }}
    QPushButton#PrimaryBtn:hover {{
        background-color: qlineargradient(x1:0, y1:0, x2:1, y2:1,
            stop:0 {theme.get("gradient_end", theme["primary_variant"])},
            stop:1 {theme.get("gradient_start", theme["primary"])});
    }}
    QPushButton#PrimaryBtn:pressed {{
        background-color: {theme["primary"]};
    }}
    QPushButton#PrimaryBtn:focus {{
        border: 2px solid {t["focus_ring"]};
    }}

    /* 인라인 텍스트 도구 - 고스트 아웃라인 칩 */
    QPushButton#ToolBtn {{
        background-color: transparent;
        border: 1px solid {theme["border"]};
        color: {theme["text_secondary"]};
        font-size: 13px;
        font-weight: 600;
        padding: 7px 12px;
        border-radius: {t["radius_chip"]}px;
        min-width: 32px;
    }}
    QPushButton#ToolBtn:hover {{
        background-color: {t["primary_soft"]};
        border-color: {theme["primary"]};
        color: {theme["primary"]};
    }}
    QPushButton#ToolBtn:focus {{
        border-color: {theme["primary"]};
    }}
    QPushButton#ToolBtn:pressed {{
        background-color: {theme["primary"]};
        border-color: {theme["primary"]};
        color: {t["on_primary"]};
    }}

    /* 상단 빠른 실행 칩 */
    QPushButton#QuickBtn {{
        background-color: {t["chip_bg"]};
        border: 1px solid {t["chip_border"]};
        border-radius: {t["radius_chip"]}px;
        padding: 7px 14px;
        color: {theme["text"]};
        font-size: 12px;
        font-weight: 600;
        min-width: 72px;
    }}
    QPushButton#QuickBtn:hover {{
        background-color: {theme["primary"]};
        border-color: {theme["primary"]};
        color: {t["on_primary"]};
    }}
    QPushButton#QuickBtn:focus {{
        border-color: {theme["primary"]};
    }}
    QPushButton#QuickBtn:pressed {{
        background-color: {theme["primary_variant"]};
        border-color: {theme["primary_variant"]};
        color: {t["on_primary"]};
    }}

    QFrame#ToolsGroup {{
        background-color: {t["surface_high"]};
        border: 1px solid {t["divider"]};
        border-radius: {t["radius_control"]}px;
        padding: 4px 8px;
    }}

    /* 위험 액션 (삭제) */
    QPushButton#DeleteBtn {{
        background-color: transparent;
        color: {theme["error"]};
        border: 1px solid {theme["error"]};
        border-radius: {t["radius_control"]}px;
        font-weight: 700;
    }}
    QPushButton#DeleteBtn:hover {{
        background-color: {theme["error"]};
        color: #ffffff;
        border-color: {theme["error"]};
    }}
    QPushButton#DeleteBtn:pressed {{
        background-color: #b91c1c;
        border-color: #b91c1c;
        color: #ffffff;
    }}

    QPushButton#CardBtn {{
        background-color: {t["surface_high"]};
        border: 1px solid {theme["border"]};
        border-radius: {t["radius_card"]}px;
        padding: 14px 18px;
        text-align: left;
    }}
    QPushButton#CardBtn:hover {{
        background-color: {theme["surface_variant"]};
        border-color: {theme["primary"]};
    }}
    """


__all__ = ["_build_button_section"]

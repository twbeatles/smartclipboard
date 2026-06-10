"""QSS section builders for MainWindow themes."""

from __future__ import annotations

def _build_button_section(theme, glass) -> str:
    return f"""QPushButton {{
        background-color: {theme["surface_variant"]};
        border: 2px solid {theme["border"]};
        border-radius: 12px;
        padding: 12px 20px;
        color: {theme["text"]};
        font-weight: 600;
        font-size: 13px;
        outline: none;
        min-height: 20px;
    }}
    QPushButton:hover {{
        background-color: {theme["primary"]};
        border-color: {theme["primary"]};
        color: white;
    }}
    QPushButton:focus {{
        border: 2px solid {theme["primary"]};
        background-color: {theme["surface_variant"]};
    }}
    QPushButton:pressed {{
        background-color: {theme["primary_variant"]};
        border-color: {theme["primary_variant"]};
        padding-left: 21px;
        padding-top: 13px;
    }}
    QPushButton:disabled {{
        background-color: {theme["surface"]};
        color: {theme["text_secondary"]};
        border-color: {theme["border"]};
        opacity: 0.6;
    }}

    QPushButton#PrimaryBtn {{
        background-color: qlineargradient(x1:0, y1:0, x2:1, y2:1,
            stop:0 {theme.get("gradient_start", theme["primary"])},
            stop:1 {theme.get("gradient_end", theme["primary_variant"])});
        color: white;
        border: none;
        font-weight: bold;
        font-size: 14px;
    }}
    QPushButton#PrimaryBtn:hover {{
        background-color: qlineargradient(x1:0, y1:0, x2:1, y2:1,
            stop:0 {theme.get("gradient_end", theme["primary_variant"])},
            stop:1 {theme.get("gradient_start", theme["primary"])});
    }}

    QPushButton#ToolBtn {{
        background-color: transparent;
        border: 2px solid {theme["border"]};
        font-size: 13px;
        padding: 8px 14px;
        border-radius: 10px;
        min-width: 36px;
    }}
    QPushButton#ToolBtn:hover {{
        background-color: {theme["secondary"]};
        border-color: {theme["secondary"]};
        color: white;
    }}
    QPushButton#ToolBtn:focus {{
        border-color: {theme["primary"]};
        background-color: rgba(255, 255, 255, 0.05);
    }}
    QPushButton#ToolBtn:pressed {{
        background-color: {theme["primary"]};
        border-color: {theme["primary"]};
    }}

    QPushButton#QuickBtn {{
        background-color: {glass["glass_bg"]};
        border: 1px solid {theme["border"]};
        border-radius: 8px;
        padding: 6px 12px;
        font-size: 12px;
        font-weight: 500;
        min-width: 70px;
    }}
    QPushButton#QuickBtn:hover {{
        background-color: {theme["surface_variant"]};
        border-color: {theme["primary"]};
        color: {theme["primary"]};
    }}
    QPushButton#QuickBtn:pressed {{
        background-color: {theme["primary"]};
        color: white;
        border-color: {theme["primary"]};
    }}

    QFrame#ToolsGroup {{
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
            stop:0 {theme["surface_variant"]}, stop:1 {theme["surface"]});
        border: 1px solid {theme["border"]};
        border-radius: 12px;
        padding: 4px 8px;
    }}

    QPushButton#DeleteBtn {{
        background-color: qlineargradient(x1:0, y1:0, x2:1, y2:1,
            stop:0 {theme["error"]}, stop:1 #dc2626);
        color: white;
        border: none;
        font-weight: bold;
    }}
    QPushButton#DeleteBtn:hover {{
        background-color: qlineargradient(x1:0, y1:0, x2:1, y2:1,
            stop:0 #dc2626, stop:1 #b91c1c);
    }}

    QPushButton#CardBtn {{
        background-color: {glass["glass_bg"]};
        border: 1px solid {theme["border"]};
        border-radius: 14px;
        padding: 14px 18px;
        text-align: left;
    }}
    QPushButton#CardBtn:hover {{
        background-color: {theme["surface_variant"]};
        border-color: {theme["primary"]};
    }}
    """

__all__ = ["_build_button_section"]

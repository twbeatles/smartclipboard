"""QSS section builders for MainWindow themes."""

from __future__ import annotations

from .tokens import derive_tokens


def _build_window_input_table_section(theme, glass, tokens=None) -> str:
    t = tokens if tokens is not None else derive_tokens(theme, glass)
    return f"""
    QMainWindow {{
        background-color: {theme["background"]};
    }}

    /* 글래스모피즘 메뉴바 */
    QMenuBar {{
        background-color: {t["glass_bg"]};
        color: {theme["text"]};
        font-family: 'Malgun Gothic', 'Segoe UI', sans-serif;
        padding: 6px 6px;
        border-bottom: 1px solid {t["divider"]};
    }}
    QMenuBar::item {{
        padding: 7px 14px;
        border-radius: {t["radius_small"]}px;
        margin: 0 2px;
        color: {theme["text_secondary"]};
    }}
    QMenuBar::item:selected {{
        background-color: {t["primary_soft"]};
        color: {theme["text"]};
    }}
    QMenuBar::item:pressed {{
        background-color: {theme["primary"]};
        color: {t["on_primary"]};
    }}

    /* 글래스모피즘 컨텍스트/드롭 메뉴 */
    QMenu {{
        background-color: {theme["surface"]};
        color: {theme["text"]};
        border: 1px solid {theme["border"]};
        border-radius: {t["radius_control"]}px;
        font-family: 'Malgun Gothic', 'Segoe UI', sans-serif;
        padding: 8px;
    }}
    QMenu::item {{
        padding: 9px 22px;
        border-radius: {t["radius_small"]}px;
        margin: 1px 4px;
    }}
    QMenu::item:selected {{
        background-color: {theme["primary"]};
        color: {t["on_primary"]};
    }}
    QMenu::separator {{
        height: 1px;
        background-color: {t["divider"]};
        margin: 6px 12px;
    }}

    QWidget {{
        color: {theme["text"]};
        font-family: 'Malgun Gothic', 'Segoe UI', sans-serif;
        font-size: 13px;
    }}

    QToolTip {{
        background-color: {theme["surface"]};
        color: {theme["text"]};
        border: 1px solid {theme["border"]};
        border-radius: {t["radius_small"]}px;
        padding: 6px 10px;
        font-size: 12px;
    }}

    /* 글래스모피즘 검색창/콤보 */
    QLineEdit, QComboBox {{
        background-color: {t["surface_high"]};
        border: 1px solid {theme["border"]};
        border-radius: {t["radius_pill"]}px;
        padding: 9px 16px;
        color: {theme["text"]};
        selection-background-color: {theme["primary"]};
        selection-color: {t["on_primary"]};
        font-size: 14px;
    }}
    QLineEdit:hover, QComboBox:hover {{
        border-color: {theme["primary_variant"]};
        background-color: {theme["surface_variant"]};
    }}
    QLineEdit:focus, QComboBox:focus {{
        border: 1px solid {theme["primary"]};
        background-color: {theme["surface_variant"]};
    }}
    QComboBox::drop-down {{
        border: none;
        padding-right: 12px;
        width: 22px;
    }}
    QComboBox::down-arrow {{
        width: 0;
        height: 0;
    }}
    QComboBox QAbstractItemView {{
        background-color: {theme["surface"]};
        border: 1px solid {theme["border"]};
        border-radius: {t["radius_control"]}px;
        selection-background-color: {theme["primary"]};
        selection-color: {t["on_primary"]};
        padding: 6px;
        outline: none;
    }}

    /* 글래스모피즘 히스토리 테이블 */
    QTableWidget {{
        background-color: {t["glass_bg"]};
        alternate-background-color: {t["overlay_hover"]};
        border: 1px solid {t["divider"]};
        border-radius: {t["radius_card"]}px;
        selection-background-color: transparent;
        gridline-color: transparent;
        outline: none;
        padding: 6px;
    }}
    QTableWidget::item {{
        padding: 12px 12px;
        border-bottom: 1px solid {t["divider"]};
        border-radius: 0px;
        color: {theme["text"]};
    }}
    QTableWidget::item:selected {{
        background-color: {t["primary_soft"]};
        color: {theme["text"]};
        font-weight: 600;
        border-left: 3px solid {theme["primary"]};
        padding-left: 9px;
    }}
    QTableWidget::item:hover:!selected {{
        background-color: {t["overlay_hover"]};
        color: {theme.get("hover_text", theme["text"])};
        border-left: 3px solid {theme["primary_variant"]};
        padding-left: 9px;
    }}
    QTableWidget::item:focus {{
        outline: none;
    }}

    QHeaderView::section {{
        background-color: transparent;
        padding: 10px 8px;
        border: none;
        border-bottom: 1px solid {theme["border"]};
        font-weight: 700;
        font-size: 11px;
        letter-spacing: 0.6px;
        color: {theme["text_secondary"]};
    }}
    QHeaderView::section:hover {{
        color: {theme["primary"]};
    }}

    QTextEdit {{
        background-color: {t["surface_high"]};
        border: 1px solid {theme["border"]};
        border-radius: {t["radius_control"]}px;
        padding: 14px;
        font-family: 'Malgun Gothic', 'Cascadia Code', 'Consolas', 'D2Coding', monospace;
        font-size: 14px;
        line-height: 1.5;
        selection-background-color: {theme["primary"]};
        selection-color: {t["on_primary"]};
    }}
    QTextEdit:focus {{
        border-color: {theme["primary"]};
    }}

    QLabel#ImagePreview {{
        background-color: {t["surface_high"]};
        border: 1px solid {theme["border"]};
        border-radius: {t["radius_card"]}px;
    }}
    """


__all__ = ["_build_window_input_table_section"]

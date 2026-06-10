"""QSS section builders for MainWindow themes."""

from __future__ import annotations

def _build_window_input_table_section(theme, glass) -> str:
    return f"""
    QMainWindow {{
        background-color: {theme["background"]};
    }}

    /* v9.0: 글래스모피즘 메뉴바 */
    QMenuBar {{
        background-color: {glass["glass_bg"]};
        color: {theme["text"]};
        font-family: 'Malgun Gothic', 'Segoe UI', sans-serif;
        padding: 6px 4px;
        border-bottom: 1px solid {theme["border"]};
    }}
    QMenuBar::item {{
        padding: 6px 12px;
        border-radius: 6px;
        margin: 0 2px;
    }}
    QMenuBar::item:selected {{
        background-color: {theme["primary"]};
        border-radius: 6px;
    }}

    /* v9.0: 글래스모피즘 메뉴 */
    QMenu {{
        background-color: {glass["glass_bg"]};
        color: {theme["text"]};
        border: 1px solid {theme["border"]};
        border-radius: 12px;
        font-family: 'Malgun Gothic', 'Segoe UI', sans-serif;
        padding: 8px;
    }}
    QMenu::item {{
        padding: 10px 24px;
        border-radius: 8px;
        margin: 2px 4px;
    }}
    QMenu::item:selected {{
        background-color: {theme["primary"]};
    }}
    QMenu::separator {{
        height: 1px;
        background-color: {theme["border"]};
        margin: 6px 12px;
    }}

    QWidget {{
        color: {theme["text"]};
        font-family: 'Malgun Gothic', 'Segoe UI', sans-serif;
        font-size: 13px;
    }}

    /* v9.0: 글래스모피즘 검색창 */
    QLineEdit, QComboBox {{
        background-color: {glass["glass_bg"]};
        border: 2px solid {theme["border"]};
        border-radius: 14px;
        padding: 10px 18px;
        color: {theme["text"]};
        selection-background-color: {theme["primary"]};
        font-size: 14px;
    }}
    QLineEdit:focus, QComboBox:focus {{
        border: 2px solid {theme["primary"]};
        background-color: {theme["surface_variant"]};
    }}
    QLineEdit:hover, QComboBox:hover {{
        border-color: {theme["primary_variant"]};
    }}
    QComboBox::drop-down {{
        border: none;
        padding-right: 12px;
        width: 20px;
    }}
    QComboBox QAbstractItemView {{
        background-color: {glass["glass_bg"]};
        border: 1px solid {theme["border"]};
        border-radius: 10px;
        selection-background-color: {theme["primary"]};
        padding: 4px;
    }}

    /* v9.0: 글래스모피즘 테이블 */
    QTableWidget {{
        background-color: {glass["glass_bg"]};
        border: none;
        border-radius: 16px;
        selection-background-color: {theme["primary"]};
        gridline-color: transparent;
        outline: none;
        padding: 4px;
    }}
    QTableWidget::item {{
        padding: 14px 12px;
        border-bottom: 1px solid {theme["border"]};
        border-radius: 0px;
    }}
    QTableWidget::item:selected {{
        background-color: {theme["primary"]};
        color: {theme.get("selected_text", "#ffffff")};
        font-weight: 500;
        border-left: 4px solid {theme.get("gradient_end", theme["primary_variant"])};
        padding-left: 10px;
    }}
    QTableWidget::item:hover:!selected {{
        background-color: {theme.get("hover_bg", theme["surface_variant"])};
        color: {theme.get("hover_text", theme["text"])};
        border-left: 4px solid {theme["primary"]};
        padding-left: 8px;
    }}
    QTableWidget::item:focus {{
        outline: none;
        border: 2px solid {theme["primary"]};
        border-radius: 4px;
    }}

    QHeaderView::section {{
        background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,
            stop:0 {theme["surface_variant"]}, stop:1 {theme["surface"]});
        padding: 12px 8px;
        border: none;
        border-bottom: 2px solid {theme["border"]};
        font-weight: 700;
        font-size: 12px;
        color: {theme["text_secondary"]};
    }}
    QHeaderView::section:hover {{
        background-color: {theme["surface_variant"]};
        color: {theme["primary"]};
    }}

    QTextEdit {{
        background-color: {glass["glass_bg"]};
        border: 2px solid {theme["border"]};
        border-radius: 14px;
        padding: 14px;
        font-family: 'Malgun Gothic', 'Cascadia Code', 'Consolas', 'D2Coding', monospace;
        font-size: 14px;
        line-height: 1.5;
        selection-background-color: {theme["primary"]};
    }}
    QTextEdit:focus {{
        border-color: {theme["primary"]};
    }}

    QLabel#ImagePreview {{
        background-color: {glass["glass_bg"]};
        border: 2px solid {theme["border"]};
        border-radius: 16px;
    }}
    """

__all__ = ["_build_window_input_table_section"]

"""QSS section builders for MainWindow themes."""

from __future__ import annotations

def _build_misc_section(theme, glass) -> str:
    return f"""QSplitter::handle {{
        background-color: {theme["border"]};
        height: 3px;
        border-radius: 1px;
    }}
    QSplitter::handle:hover {{
        background-color: {theme["primary"]};
    }}

    QStatusBar {{
        background-color: {glass["glass_bg"]};
        color: {theme["text_secondary"]};
        border-top: 1px solid {theme["border"]};
        padding: 4px 8px;
        font-size: 12px;
    }}

    QTabWidget::pane {{
        border: 1px solid {theme["border"]};
        border-radius: 12px;
        background-color: {glass["glass_bg"]};
    }}
    QTabBar::tab {{
        background-color: {theme["surface_variant"]};
        color: {theme["text_secondary"]};
        padding: 12px 24px;
        margin-right: 4px;
        border-top-left-radius: 10px;
        border-top-right-radius: 10px;
        font-weight: 500;
    }}
    QTabBar::tab:hover {{
        background-color: {theme["surface"]};
        color: {theme["text"]};
    }}
    QTabBar::tab:selected {{
        background-color: {theme["primary"]};
        color: white;
        font-weight: 600;
    }}

    QScrollBar:vertical {{
        background-color: transparent;
        width: 6px;
        border-radius: 3px;
        margin: 4px 2px;
    }}
    QScrollBar:vertical:hover {{
        width: 10px;
    }}
    QScrollBar::handle:vertical {{
        background-color: {theme["border"]};
        border-radius: 3px;
        min-height: 40px;
    }}
    QScrollBar::handle:vertical:hover {{
        background-color: {theme["primary"]};
        border-radius: 5px;
    }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0px;
    }}
    QScrollBar:horizontal {{
        background-color: transparent;
        height: 8px;
        border-radius: 4px;
    }}
    QScrollBar::handle:horizontal {{
        background-color: {theme["border"]};
        border-radius: 4px;
        min-width: 40px;
    }}
    QScrollBar::handle:horizontal:hover {{
        background-color: {theme["primary"]};
    }}

    QDialog {{
        background-color: {theme["background"]};
    }}

    QGroupBox {{
        background-color: {glass["glass_bg"]};
        border: 1px solid {theme["border"]};
        border-radius: 12px;
        margin-top: 12px;
        padding-top: 12px;
        font-weight: 600;
    }}
    QGroupBox::title {{
        subcontrol-origin: margin;
        subcontrol-position: top left;
        left: 12px;
        padding: 0 8px;
        color: {theme["text"]};
    }}

    QSpinBox {{
        background-color: {glass["glass_bg"]};
        border: 2px solid {theme["border"]};
        border-radius: 10px;
        padding: 8px 12px;
        color: {theme["text"]};
    }}
    QSpinBox:focus {{
        border-color: {theme["primary"]};
    }}

    QCheckBox {{
        spacing: 8px;
    }}
    QCheckBox::indicator {{
        width: 20px;
        height: 20px;
        border-radius: 6px;
        border: 2px solid {theme["border"]};
    }}
    QCheckBox::indicator:checked {{
        background-color: {theme["primary"]};
        border-color: {theme["primary"]};
    }}
    QCheckBox::indicator:hover {{
        border-color: {theme["primary_variant"]};
    }}

    QFrame#ToolsGroup {{
        background-color: {glass["glass_bg"]};
        border: 1px solid {theme["border"]};
        border-radius: 10px;
        padding: 4px 8px;
    }}

    QComboBox#FilterCombo {{
        background-color: {theme["surface_variant"]};
        font-weight: 600;
        min-width: 130px;
    }}
    QComboBox#FilterCombo:hover {{
        background-color: {theme["surface"]};
        border-color: {theme["primary"]};
    }}

    QLineEdit::placeholder {{
        color: {theme["text_secondary"]};
        font-style: italic;
    }}
    """

__all__ = ["_build_misc_section"]

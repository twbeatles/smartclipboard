"""QSS section builders for MainWindow themes."""

from __future__ import annotations

from .tokens import derive_tokens


def _build_misc_section(theme, glass, tokens=None) -> str:
    t = tokens if tokens is not None else derive_tokens(theme, glass)
    return f"""QSplitter::handle {{
        background-color: transparent;
        height: 10px;
    }}
    QSplitter::handle:hover {{
        background-color: {t["primary_softer"]};
        border-radius: 4px;
    }}

    QStatusBar {{
        background-color: {t["glass_bg"]};
        color: {theme["text_secondary"]};
        border-top: 1px solid {t["divider"]};
        padding: 4px 12px;
        font-size: 12px;
    }}
    QStatusBar::item {{
        border: none;
    }}

    QTabWidget::pane {{
        border: 1px solid {theme["border"]};
        border-radius: {t["radius_control"]}px;
        background-color: {t["glass_bg"]};
        top: -1px;
    }}
    QTabBar::tab {{
        background-color: transparent;
        color: {theme["text_secondary"]};
        padding: 10px 20px;
        margin-right: 4px;
        border: none;
        border-bottom: 2px solid transparent;
        font-weight: 600;
    }}
    QTabBar::tab:hover {{
        color: {theme["text"]};
    }}
    QTabBar::tab:selected {{
        color: {theme["primary"]};
        border-bottom: 2px solid {theme["primary"]};
    }}

    QScrollBar:vertical {{
        background-color: transparent;
        width: 10px;
        margin: 4px 2px;
    }}
    QScrollBar::handle:vertical {{
        background-color: {theme["border"]};
        border-radius: 4px;
        min-height: 40px;
    }}
    QScrollBar::handle:vertical:hover {{
        background-color: {theme["primary"]};
    }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0px;
    }}
    QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
        background: transparent;
    }}
    QScrollBar:horizontal {{
        background-color: transparent;
        height: 10px;
        margin: 2px 4px;
    }}
    QScrollBar::handle:horizontal {{
        background-color: {theme["border"]};
        border-radius: 4px;
        min-width: 40px;
    }}
    QScrollBar::handle:horizontal:hover {{
        background-color: {theme["primary"]};
    }}
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
        width: 0px;
    }}
    QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{
        background: transparent;
    }}

    QDialog {{
        background-color: {theme["background"]};
    }}

    QGroupBox {{
        background-color: {t["surface_high"]};
        border: 1px solid {theme["border"]};
        border-radius: {t["radius_control"]}px;
        margin-top: 14px;
        padding: 14px 12px 12px 12px;
        font-weight: 700;
    }}
    QGroupBox::title {{
        subcontrol-origin: margin;
        subcontrol-position: top left;
        left: 14px;
        padding: 0 8px;
        color: {theme["primary"]};
    }}

    QSpinBox {{
        background-color: {t["surface_high"]};
        border: 1px solid {theme["border"]};
        border-radius: {t["radius_small"]}px;
        padding: 8px 12px;
        color: {theme["text"]};
    }}
    QSpinBox:hover {{
        border-color: {theme["primary_variant"]};
    }}
    QSpinBox:focus {{
        border-color: {theme["primary"]};
    }}

    QCheckBox {{
        spacing: 10px;
    }}
    QCheckBox::indicator {{
        width: 20px;
        height: 20px;
        border-radius: 6px;
        border: 2px solid {theme["border"]};
        background-color: {t["surface_high"]};
    }}
    QCheckBox::indicator:checked {{
        background-color: {theme["primary"]};
        border-color: {theme["primary"]};
    }}
    QCheckBox::indicator:hover {{
        border-color: {theme["primary"]};
    }}

    QRadioButton {{
        spacing: 10px;
    }}
    QRadioButton::indicator {{
        width: 18px;
        height: 18px;
        border-radius: 9px;
        border: 2px solid {theme["border"]};
        background-color: {t["surface_high"]};
    }}
    QRadioButton::indicator:checked {{
        background-color: {theme["primary"]};
        border-color: {theme["primary"]};
    }}

    QProgressBar {{
        background-color: {t["surface_high"]};
        border: none;
        border-radius: 6px;
        height: 8px;
        text-align: center;
        color: {theme["text"]};
    }}
    QProgressBar::chunk {{
        background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0,
            stop:0 {theme.get("gradient_start", theme["primary"])},
            stop:1 {theme.get("gradient_end", theme["primary_variant"])});
        border-radius: 6px;
    }}

    QComboBox#FilterCombo {{
        background-color: {t["surface_high"]};
        font-weight: 600;
        min-width: 130px;
    }}
    QComboBox#FilterCombo:hover {{
        background-color: {theme["surface_variant"]};
        border-color: {theme["primary"]};
    }}

    QLabel#PrivacyIndicator {{
        color: {theme["warning"]};
        font-size: 12px;
        font-weight: 700;
        padding: 4px 10px;
        border: 1px solid {theme["warning"]};
        border-radius: {t["radius_chip"]}px;
    }}

    QLineEdit::placeholder {{
        color: {theme["text_secondary"]};
    }}
    """


__all__ = ["_build_misc_section"]

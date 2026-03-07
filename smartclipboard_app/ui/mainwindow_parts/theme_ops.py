"""Extracted MainWindow helper operations."""

from __future__ import annotations

def apply_theme_impl(self, THEMES, GLASS_STYLES):
    theme = THEMES.get(self.current_theme, THEMES["dark"])
    glass = GLASS_STYLES.get(self.current_theme, GLASS_STYLES["dark"])
    style = f"""
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
    /* v10.1: 개선된 테이블 항목 스타일 - 선택 시각화 강화 */
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
    
    /* v9.0: 개선된 헤더 */
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
    
    /* v9.0: 글래스 텍스트 영역 */
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
    
    /* v10.6: 개선된 버튼 스타일 - 마이크로 인터랙션 및 일관성 강화 */
    QPushButton {{ 
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
    
    /* v9.0: 그라데이션 Primary 버튼 */
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
    
    /* v10.1: 개선된 아이콘 버튼 - 호버 피드백 강화 */
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
    
    /* v10.7: 퀵 액션 버튼 - 상단 바 전용 */
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
    
    /* v10.7: 도구 버튼 그룹 컨테이너 */
    QFrame#ToolsGroup {{
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
            stop:0 {theme["surface_variant"]}, stop:1 {theme["surface"]});
        border: 1px solid {theme["border"]};
        border-radius: 12px;
        padding: 4px 8px;
    }}
    
    /* v9.0: 경고 삭제 버튼 */
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
    
    /* v9.0: 카드 스타일 버튼 */
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
    
    /* v9.0: 스플리터 */
    QSplitter::handle {{
        background-color: {theme["border"]};
        height: 3px;
        border-radius: 1px;
    }}
    QSplitter::handle:hover {{
        background-color: {theme["primary"]};
    }}
    
    /* v9.0: 글래스 상태바 */
    QStatusBar {{
        background-color: {glass["glass_bg"]};
        color: {theme["text_secondary"]};
        border-top: 1px solid {theme["border"]};
        padding: 4px 8px;
        font-size: 12px;
    }}
    
    /* v9.0: 모던 탭 위젯 */
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
    
    /* v10.6: 울트라 슬림 스크롤바 - 부드러운 호버 효과 */
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
    
    /* v9.0: 다이얼로그 스타일 */
    QDialog {{
        background-color: {theme["background"]};
    }}
    
    /* v9.0: 그룹박스 */
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
    
    /* v9.0: 스핀박스 */
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
    
    /* v9.0: 체크박스 */
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
    
    /* v10.6: 도구 버튼 그룹 컨테이너 */
    QFrame#ToolsGroup {{
        background-color: {glass["glass_bg"]};
        border: 1px solid {theme["border"]};
        border-radius: 10px;
        padding: 4px 8px;
    }}
    
    /* v10.6: 필터 콤보박스 강조 */
    QComboBox#FilterCombo {{
        background-color: {theme["surface_variant"]};
        font-weight: 600;
        min-width: 130px;
    }}
    QComboBox#FilterCombo:hover {{
        background-color: {theme["surface"]};
        border-color: {theme["primary"]};
    }}
    
    /* v10.6: 향상된 플레이스홀더 스타일 */
    QLineEdit::placeholder {{
        color: {theme["text_secondary"]};
        font-style: italic;
    }}
    """
    self.setStyleSheet(style)

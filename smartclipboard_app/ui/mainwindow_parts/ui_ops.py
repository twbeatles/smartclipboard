"""Extracted MainWindow helper operations."""

from __future__ import annotations

from typing import TypeVar

from PyQt6.QtCore import QEvent, Qt, QTimer
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QSplitter,
    QStackedWidget,
    QTableWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

T = TypeVar("T")


def _ensure(value: T | None) -> T:
    assert value is not None
    return value


def init_ui_impl(self, HAS_QRCODE):
    central_widget = QWidget()
    self.setCentralWidget(central_widget)
    main_layout = QVBoxLayout(central_widget)
    main_layout.setContentsMargins(16, 16, 16, 16)
    main_layout.setSpacing(12)

    # v10.7: 상단 퀵 액션 바 (자주 사용하는 기능 빠른 접근)
    quick_bar = QHBoxLayout()
    quick_bar.setSpacing(8)
    
    btn_vault = QPushButton("🔒 보관함")
    btn_vault.setObjectName("QuickBtn")
    btn_vault.setToolTip("보안 보관함 열기")
    btn_vault.clicked.connect(self.show_secure_vault)
    
    btn_snippets = QPushButton("📝 스니펫")
    btn_snippets.setObjectName("QuickBtn")
    btn_snippets.setToolTip("스니펫 관리")
    btn_snippets.clicked.connect(self.show_snippet_manager)
    
    btn_trash = QPushButton("🗑️ 휴지통")
    btn_trash.setObjectName("QuickBtn")
    btn_trash.setToolTip("휴지통 열기")
    btn_trash.clicked.connect(self.show_trash)
    
    btn_settings = QPushButton("⚙️ 설정")
    btn_settings.setObjectName("QuickBtn")
    btn_settings.setToolTip("설정 열기")
    btn_settings.clicked.connect(self.show_settings)
    
    quick_bar.addWidget(btn_vault)
    quick_bar.addWidget(btn_snippets)
    quick_bar.addWidget(btn_trash)
    quick_bar.addWidget(btn_settings)
    quick_bar.addStretch()
    
    # 프라이버시 모드 인디케이터
    self.privacy_indicator = QLabel("")
    self.privacy_indicator.setStyleSheet("font-size: 12px; color: #fbbf24;")
    quick_bar.addWidget(self.privacy_indicator)
    
    main_layout.addLayout(quick_bar)

    # v9.0: 상단 필터/검색 영역 (개선된 레이아웃)
    top_layout = QHBoxLayout()
    top_layout.setSpacing(12)
    
    self.filter_combo = QComboBox()
    self.filter_combo.setObjectName("FilterCombo")  # v10.6: 스타일 연결용
    self.filter_combo.addItems(["전체", "📌 고정", "⭐ 북마크", "📝 텍스트", "🖼️ 이미지", "🔗 링크", "💻 코드", "🎨 색상"])
    self.filter_combo.setFixedWidth(150)
    self.filter_combo.setToolTip("유형별 필터")
    self.filter_combo.currentTextChanged.connect(self.load_data)

    self.collection_filter_combo = QComboBox()
    self.collection_filter_combo.setObjectName("FilterCombo")
    self.collection_filter_combo.setFixedWidth(180)
    self.collection_filter_combo.setToolTip("컬렉션 필터")
    self.collection_filter_combo.currentIndexChanged.connect(self.on_collection_filter_changed)
    
    self.search_input = QLineEdit()
    self.search_input.setPlaceholderText("🔍 검색어 입력... (Ctrl+F)")
    # Debounced search to avoid UI stutter on large DBs.
    self._search_debounce_timer = QTimer(self)
    self._search_debounce_timer.setSingleShot(True)
    self._search_debounce_timer.setInterval(200)
    self._search_debounce_timer.timeout.connect(self.load_data)
    self._search_fallback_notified = False

    self.search_input.textChanged.connect(self.on_search_text_changed)
    self.search_input.setClearButtonEnabled(True)
    self.search_input.setMinimumHeight(40)
    
    # v9.0: 태그 필터 버튼 개선
    self.btn_tag_filter = QPushButton("🏷️")
    self.btn_tag_filter.setObjectName("ToolBtn")
    self.btn_tag_filter.setToolTip("태그 필터")
    self.btn_tag_filter.setFixedSize(44, 40)
    self.btn_tag_filter.clicked.connect(self.show_tag_filter_menu)
    
    top_layout.addWidget(self.filter_combo)
    top_layout.addWidget(self.collection_filter_combo)
    top_layout.addWidget(self.search_input, 1)  # stretch factor 1
    top_layout.addWidget(self.btn_tag_filter)
    main_layout.addLayout(top_layout)
    self.refresh_collection_filter_options()

    # 메인 스플리터
    splitter = QSplitter(Qt.Orientation.Vertical)

    # v9.0: 개선된 테이블
    self.table = QTableWidget()
    self.table.setColumnCount(5)
    self.table.setHorizontalHeaderLabels(["📌", "유형", "내용", "시간", "사용"])
    
    header = _ensure(self.table.horizontalHeader())
    header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
    header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
    header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
    header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
    header.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
    
    self.table.setColumnWidth(0, 40)
    self.table.setColumnWidth(1, 60)
    self.table.setColumnWidth(3, 95)
    self.table.setColumnWidth(4, 50)
    
    vertical_header = self.table.verticalHeader()
    if vertical_header is not None:
        vertical_header.setVisible(False)
        vertical_header.setDefaultSectionSize(42)  # v9.0: 행 높이 증가
    
    self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)  # 다중 선택 지원
    self.table.setShowGrid(False)
    self.table.setAlternatingRowColors(True)
    self.table.itemSelectionChanged.connect(self.on_selection_changed)
    self.table.cellDoubleClicked.connect(self.on_double_click_paste)
    
    self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
    self.table.customContextMenuRequested.connect(self.show_context_menu)
    
    # 헤더 클릭 정렬
    header.setSectionsClickable(True)
    header.sectionClicked.connect(self.on_header_clicked)
    
    # 드래그 앤 드롭 (고정 항목 재정렬용)
    # DragDrop 모드: Qt 자동 행 삭제 방지, 커스텀 eventFilter에서 처리
    self.table.setDragEnabled(True)
    self.table.setAcceptDrops(True)
    self.table.setDragDropMode(QAbstractItemView.DragDropMode.DragDrop)
    self.table.setDefaultDropAction(Qt.DropAction.CopyAction)
    self.table.setDragDropOverwriteMode(False)
    viewport = self.table.viewport()
    if viewport is not None:
        viewport.installEventFilter(self)

    splitter.addWidget(self.table)

    # 상세 영역
    detail_container = QWidget()
    detail_layout = QVBoxLayout(detail_container)
    detail_layout.setContentsMargins(0, 10, 0, 0)
    detail_layout.setSpacing(10)
    
    # 도구 버튼
    self.tools_layout = QHBoxLayout()
    self.tools_layout.setSpacing(6)
    self.tools_layout.addStretch()
    
    self.btn_save_img = QPushButton("💾 저장")
    self.btn_save_img.setObjectName("ToolBtn")
    self.btn_save_img.clicked.connect(self.save_image_to_file)
    self.btn_save_img.setVisible(False)
    
    self.btn_google = QPushButton("🔍 구글")
    self.btn_google.setObjectName("ToolBtn")
    self.btn_google.setToolTip("구글에서 검색 (Ctrl+G)")
    self.btn_google.clicked.connect(self.search_google)
    
    self.btn_qr = QPushButton("📱 QR")
    self.btn_qr.setObjectName("ToolBtn")
    self.btn_qr.setToolTip("QR 코드 생성")
    self.btn_qr.clicked.connect(self.generate_qr)
    
    self.btn_upper = QPushButton("ABC")
    self.btn_upper.setObjectName("ToolBtn")
    self.btn_upper.setToolTip("대문자 변환")
    self.btn_upper.clicked.connect(lambda: self.transform_text("upper"))
    
    self.btn_lower = QPushButton("abc")
    self.btn_lower.setObjectName("ToolBtn")
    self.btn_lower.setToolTip("소문자 변환")
    self.btn_lower.clicked.connect(lambda: self.transform_text("lower"))
    
    self.btn_strip = QPushButton("✂️")
    self.btn_strip.setObjectName("ToolBtn")
    self.btn_strip.setToolTip("공백 제거")
    self.btn_strip.clicked.connect(lambda: self.transform_text("strip"))
    
    self.btn_normalize = QPushButton("📋")
    self.btn_normalize.setObjectName("ToolBtn")
    self.btn_normalize.setToolTip("줄바꿈 정리")
    self.btn_normalize.clicked.connect(lambda: self.transform_text("normalize"))
    
    self.btn_json = QPushButton("{ }")
    self.btn_json.setObjectName("ToolBtn")
    self.btn_json.setToolTip("JSON 포맷팅")
    self.btn_json.clicked.connect(lambda: self.transform_text("json"))

    self.tools_layout.addWidget(self.btn_save_img)
    self.tools_layout.addWidget(self.btn_google)
    if HAS_QRCODE:
        self.tools_layout.addWidget(self.btn_qr)
    
    # 그룹 구분선 1: 검색/공유 | 대소문자
    sep1 = QFrame()
    sep1.setFrameShape(QFrame.Shape.VLine)
    sep1.setFixedWidth(2)
    sep1.setStyleSheet("background-color: rgba(128,128,128,0.4);")
    self.tools_layout.addWidget(sep1)
    
    self.tools_layout.addWidget(self.btn_upper)
    self.tools_layout.addWidget(self.btn_lower)
    
    # 그룹 구분선 2: 대소문자 | 공백/포맷
    sep2 = QFrame()
    sep2.setFrameShape(QFrame.Shape.VLine)
    sep2.setFixedWidth(2)
    sep2.setStyleSheet("background-color: rgba(128,128,128,0.4);")
    self.tools_layout.addWidget(sep2)
    
    self.tools_layout.addWidget(self.btn_strip)
    self.tools_layout.addWidget(self.btn_normalize)
    self.tools_layout.addWidget(self.btn_json)
    detail_layout.addLayout(self.tools_layout)

    # 상세 보기 스택
    self.detail_stack = QStackedWidget()
    
    self.detail_text = QTextEdit()
    self.detail_text.setReadOnly(True)
    self.detail_stack.addWidget(self.detail_text)
    
    self.detail_image_lbl = QLabel()
    self.detail_image_lbl.setObjectName("ImagePreview")
    self.detail_image_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
    self.detail_stack.addWidget(self.detail_image_lbl)
    
    detail_layout.addWidget(self.detail_stack)

    # v10.6: 하단 액션 버튼 - 통일된 높이와 완성된 디자인
    btn_layout = QHBoxLayout()
    btn_layout.setSpacing(8)
    
    self.btn_copy = QPushButton("📄 복사")
    self.btn_copy.setMinimumHeight(44)
    self.btn_copy.setObjectName("PrimaryBtn")
    self.btn_copy.setToolTip("클립보드에 복사 (Enter)")
    self.btn_copy.clicked.connect(self.copy_item)
    
    self.btn_link = QPushButton("🔗 링크 열기")
    self.btn_link.setMinimumHeight(44)
    self.btn_link.setToolTip("브라우저에서 링크 열기 (Ctrl+L)")
    self.btn_link.clicked.connect(self.open_link)
    
    self.btn_pin = QPushButton("📌 고정")
    self.btn_pin.setMinimumHeight(44)
    self.btn_pin.setToolTip("항목 고정/해제 (Ctrl+P)")
    self.btn_pin.clicked.connect(self.toggle_pin)
    
    self.btn_del = QPushButton("🗑 삭제")
    self.btn_del.setMinimumHeight(44)
    self.btn_del.setObjectName("DeleteBtn")
    self.btn_del.setToolTip("항목 삭제 (Delete)")
    self.btn_del.clicked.connect(self.delete_item)

    btn_layout.addWidget(self.btn_copy, 3)
    btn_layout.addWidget(self.btn_link, 2)
    btn_layout.addWidget(self.btn_pin, 2)
    btn_layout.addWidget(self.btn_del, 1)
    detail_layout.addLayout(btn_layout)

    splitter.addWidget(detail_container)
    splitter.setStretchFactor(0, 7)  # v9.0: 테이블 영역 더 크게
    splitter.setStretchFactor(1, 3)
    main_layout.addWidget(splitter)
    
    self.update_ui_state(False)

def event_filter_impl(self, source, event, fallback_event_filter):
    """드래그 앤 드롭 이벤트 처리 (고정 항목 순서 변경)"""
    viewport = self.table.viewport()
    if viewport is None or source != viewport:
        return fallback_event_filter(source, event)
    
    # DragEnter: 드래그 시작 허용 여부
    if event.type() == QEvent.Type.DragEnter:
        if event.source() == self.table:
            event.acceptProposedAction()
            return True
        return False
    
    # DragMove: 드래그 중
    if event.type() == QEvent.Type.DragMove:
        event.acceptProposedAction()
        return True
    
    # Drop: 드래그 완료
    if event.type() == QEvent.Type.Drop:
        return self._handle_drop_event(event)
    
    return fallback_event_filter(source, event)

def handle_drop_event_impl(self, event, THEMES, logger) -> bool:
    """드롭 이벤트 처리 - 고정 항목끼리만 순서 변경 허용"""
    try:
        # 드롭 위치 확인
        target_row = self.table.rowAt(int(event.position().y()))
        if target_row == -1:
            event.ignore()
            return True  # 이벤트 소비 (Qt 기본 동작 막기)
        
        # 선택된 행 (드래그 중인 행)
        selection_model = self.table.selectionModel()
        if selection_model is None:
            event.ignore()
            return True
        selected_rows = selection_model.selectedRows()
        if not selected_rows:
            event.ignore()
            return True
        source_row = selected_rows[0].row()
        
        # 같은 위치면 무시
        if source_row == target_row:
            event.ignore()
            return True
        
        # 소스/타겟 항목 확인
        source_item = self.table.item(source_row, 0)
        target_item = self.table.item(target_row, 0)
        
        if not source_item or not target_item:
            event.ignore()
            return True
        
        # 고정 항목 확인
        is_source_pinned = source_item.text() == "📌"
        is_target_pinned = target_item.text() == "📌"
        
        if not (is_source_pinned and is_target_pinned):
            # 비고정 항목 드래그 시도 시 토스트 알림
            status_bar = self.statusBar()
            if status_bar is not None:
                status_bar.showMessage("📌 고정 항목끼리만 순서를 변경할 수 있습니다.", 2000)
            event.ignore()
            return True
        
        # 고정 항목 순서 재정렬
        source_pid = source_item.data(Qt.ItemDataRole.UserRole)
        
        # 현재 고정된 항목들의 ID 목록 (화면 순서)
        pinned_ids = []
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item and item.text() == "📌":
                pid = item.data(Qt.ItemDataRole.UserRole)
                if pid != source_pid:  # 드래그 중인 항목 제외
                    pinned_ids.append(pid)
        
        # 삽입 위치 계산
        insert_idx = 0
        for r in range(target_row):
            item = self.table.item(r, 0)
            if item and item.text() == "📌":
                pid = item.data(Qt.ItemDataRole.UserRole)
                if pid != source_pid:
                    insert_idx += 1
        
        # 위에서 아래로 드래그 시 인덱스 조정
        if source_row < target_row:
            pinned_ids.insert(insert_idx, source_pid)
        else:
            pinned_ids.insert(insert_idx, source_pid)
        
        # DB 업데이트
        success = self.db.update_pin_orders(pinned_ids)
        
        if success:
            # 성공 시 UI 갱신 (딜레이로 드롭 애니메이션 방지)
            QTimer.singleShot(50, self.load_data)
            status_bar = self.statusBar()
            if status_bar is not None:
                status_bar.showMessage("✅ 고정 항목 순서가 변경되었습니다.", 2000)
        else:
            status_bar = self.statusBar()
            if status_bar is not None:
                status_bar.showMessage("⚠️ 순서 변경 중 오류가 발생했습니다.", 2000)
        
        event.accept()
        return True  # 이벤트 소비
        
    except Exception as e:
        logger.error(f"Drop event error: {e}")
        event.ignore()
        return True

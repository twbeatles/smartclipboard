"""Extracted MainWindow helper operations."""

from __future__ import annotations

import datetime

from PyQt6.QtCore import QSize, Qt
from PyQt6.QtGui import QColor, QPixmap
from PyQt6.QtWidgets import QTableWidgetItem

from smartclipboard_core.file_paths import (
    build_file_paths_detail_text,
    build_file_paths_tooltip,
    describe_file_paths_with_status,
    file_paths_from_content,
)


def load_data_impl(self, THEMES, logger):
    """데이터 로드 및 테이블 갱신 - 리팩토링된 버전"""
    try:
        items = self._get_display_items()
        self._last_display_count = len(items)
        self._last_search_query = self.search_input.text() if hasattr(self, "search_input") else ""

        if (
            getattr(self, "_last_search_query", "").strip()
            and getattr(self.db, "_last_search_fallback", False)
            and not getattr(self, "_search_fallback_notified", False)
        ):
            self._search_fallback_notified = True
            self.statusBar().showMessage("⚠️ 고급 검색 오류로 일반 검색으로 전환했습니다.", 2500)
        
        # v10.4: 데이터 로드 완료로 플래그 리셋
        self.is_data_dirty = False
        
        # v10.1: UI 업데이트 일괄 처리 (성능 최적화)
        self.table.setUpdatesEnabled(False)
        try:
            self.table.setRowCount(0)
            theme = THEMES.get(self.current_theme, THEMES["dark"])
        
            if not items:
                self._show_empty_state(theme)
                return
            
            self._populate_table(items, theme)
            
            # 상태바 업데이트
            self.update_status_bar()
        finally:
            self.table.setUpdatesEnabled(True)
    except Exception as e:
        logger.exception("Data loading error")

def get_display_items_impl(self):
    """표시할 항목 조회 및 정렬"""
    search_query = self.search_input.text()
    filter_type = self.filter_combo.currentText()
    collection_filter = getattr(self, "current_collection_filter", "__all__")

    bookmarked = filter_type == "⭐ 북마크"
    tag_filter = self.current_tag_filter
    collection_id = collection_filter if isinstance(collection_filter, int) else None
    uncategorized = collection_filter == "__uncategorized__"

    # 1. DB 조회 (FTS-backed unified search if available)
    if hasattr(self.db, "search_items"):
        items = self.db.search_items(
            search_query,
            type_filter=filter_type,
            tag_filter=tag_filter,
            bookmarked=bookmarked,
            collection_id=collection_id,
            uncategorized=uncategorized,
        )
    else:
        if tag_filter:
            items = self.db.get_items_by_tag(tag_filter)
            if search_query:
                items = [i for i in items if search_query.lower() in (i[1] or "").lower()]
        elif uncategorized and hasattr(self.db, "get_items_uncategorized"):
            items = self.db.get_items_uncategorized()
            if search_query:
                items = [i for i in items if search_query.lower() in (i[1] or "").lower()]
        elif collection_id is not None:
            items = self.db.get_items_by_collection(collection_id)
            if search_query:
                items = [i for i in items if search_query.lower() in (i[1] or "").lower()]
        elif bookmarked:
            items = self.db.get_bookmarked_items()
            if search_query:
                items = [i for i in items if search_query.lower() in (i[1] or "").lower()]
        else:
            items = self.db.get_items(search_query, filter_type)
        
    # 2. 정렬 (고정 항목은 항상 상단)
    if items and self.sort_column > 0:
        def get_sort_key(item):
            _pid, content, ptype, timestamp, _pinned, use_count, _pin_order = item
            col = self.sort_column
            if col == 1: return ptype or ""
            elif col == 2: return (content or "").lower()
            elif col == 3: return timestamp or ""
            elif col == 4: return use_count or 0
            return 0
        
        reverse = self.sort_order == Qt.SortOrder.DescendingOrder
        pinned_items = [item for item in items if item[4]]
        unpinned_items = [item for item in items if not item[4]]
        items = (
            sorted(pinned_items, key=get_sort_key, reverse=reverse)
            + sorted(unpinned_items, key=get_sort_key, reverse=reverse)
        )
        
    return items

def show_empty_state_impl(self, theme):
    """빈 결과 상태 표시"""
    search_query = self.search_input.text()
    self.table.setRowCount(1)
    
    if search_query:
        empty_msg = f"🔍 '{search_query}'에 대한 검색 결과가 없습니다\n\n다른 검색어를 입력하거나 필터를 변경해보세요"
    elif self.current_tag_filter:
        empty_msg = f"🏷️ '{self.current_tag_filter}' 태그가 없습니다\n\n항목을 선택하고 마우스 오른쪽 버튼으로 태그를 추가하세요"
    elif getattr(self, "current_collection_filter", "__all__") == "__uncategorized__":
        empty_msg = "🧺 미분류 항목이 없습니다\n\n컬렉션에서 제거된 항목만 이 필터에 표시됩니다"
    elif isinstance(getattr(self, "current_collection_filter", "__all__"), int):
        current_collection_label = self.collection_filter_combo.currentText() if hasattr(self, "collection_filter_combo") else "선택한 컬렉션"
        empty_msg = f"📁 '{current_collection_label}'에 항목이 없습니다\n\n항목을 우클릭하여 컬렉션으로 이동해보세요"
    else:
        empty_msg = "📋 클립보드 히스토리가 비어있습니다\n\n"
        empty_msg += "💡 시작 방법:\n"
        empty_msg += "• 텍스트, 이미지, 파일을 복사하면 자동 저장\n"
        empty_msg += "• Ctrl+Shift+V: 클립보드 창 열기\n"
        empty_msg += "• Alt+V: 미니 창 열기\n"
        empty_msg += "• 더블클릭으로 항목 붙여넣기"
        
    empty_item = QTableWidgetItem(empty_msg)
    empty_item.setForeground(QColor(theme["text_secondary"]))
    empty_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
    empty_item.setFlags(empty_item.flags() & ~Qt.ItemFlag.ItemIsSelectable)
    self.table.setItem(0, 0, empty_item)
    self.table.setSpan(0, 0, 1, 5)
    self.table.setRowHeight(0, 150)

def populate_table_impl(self, items, theme, TYPE_ICONS):
    """테이블 행 생성"""
    today = datetime.date.today()
    yesterday = today - datetime.timedelta(days=1)
    
    for row_idx, item_data in enumerate(items):
        pid, content, ptype, timestamp, pinned, use_count, pin_order = item_data
        self.table.insertRow(row_idx)
        
        # 1. 고정 아이콘
        pin_item = QTableWidgetItem("📌" if pinned else "")
        pin_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        pin_item.setData(Qt.ItemDataRole.UserRole, pid)
        if pinned:
            pin_item.setBackground(QColor(theme["primary"]).lighter(170))
        self.table.setItem(row_idx, 0, pin_item)
        
        # 2. 유형
        type_item = QTableWidgetItem(TYPE_ICONS.get(ptype, "📝"))
        type_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        type_item.setToolTip(ptype)
        type_item.setData(Qt.ItemDataRole.UserRole + 1, ptype)
        self.table.setItem(row_idx, 1, type_item)
        
        # 3. 내용
        if ptype == "FILE":
            file_paths = file_paths_from_content(content)
            display = describe_file_paths_with_status(file_paths)
        else:
            display = content.replace('\n', ' ').strip()
            if len(display) > 45:
                display = display[:45] + "..."
        content_item = QTableWidgetItem(display)
        
        if ptype == "IMAGE":
            content_item.setToolTip("🖼️ 이미지 항목 - 더블클릭으로 미리보기")
        elif ptype == "FILE":
            file_paths = file_paths_from_content(content)
            content_item.setToolTip(build_file_paths_tooltip(file_paths))
        else:
            content_item.setToolTip(content[:500] if len(content) > 500 else content)
            
        if ptype == "LINK": content_item.setForeground(QColor(theme["secondary"]))
        elif ptype == "CODE": content_item.setForeground(QColor(theme["success"]))
        elif ptype == "COLOR": content_item.setForeground(QColor(content) if content.startswith("#") else QColor(theme["warning"]))
        elif ptype == "FILE": content_item.setForeground(QColor(theme["primary"]))
        
        content_item.setData(Qt.ItemDataRole.UserRole + 1, content)
        self.table.setItem(row_idx, 2, content_item)
        
        # 4. 시간
        try:
            dt = datetime.datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S")
            if dt.date() == today: time_str = dt.strftime("%H:%M")
            elif dt.date() == yesterday: time_str = f"어제 {dt.hour}시"
            else: time_str = f"{dt.month}/{dt.day} {dt.hour}시"
        except (ValueError, TypeError):
            time_str = timestamp
        
        time_item = QTableWidgetItem(time_str)
        time_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        time_item.setForeground(QColor(theme["text_secondary"]))
        time_item.setData(Qt.ItemDataRole.UserRole + 1, timestamp)
        self.table.setItem(row_idx, 3, time_item)
        
        # 5. 사용 횟수
        if use_count and use_count >= 10: use_display = f"🔥 {use_count}"
        elif use_count and use_count >= 5: use_display = f"⭐ {use_count}"
        elif use_count: use_display = str(use_count)
        else: use_display = "-"
        
        use_item = QTableWidgetItem(use_display)
        use_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        use_item.setForeground(QColor(theme["text_secondary"]))
        use_item.setData(Qt.ItemDataRole.UserRole + 1, use_count or 0)
        self.table.setItem(row_idx, 4, use_item)

def on_selection_changed_impl(self, HAS_QRCODE, THEMES):
    # 선택된 항목 수 계산 및 상태바 업데이트
    selected_count = len(self.table.selectionModel().selectedRows())
    self.update_status_bar(selected_count)
    
    pid = self.get_selected_id()
    if not pid:
        self.update_ui_state(False)
        return
        
    data = self.db.get_content(pid)
    if data:
        content, blob, ptype = data
        theme = THEMES.get(self.current_theme, THEMES["dark"])
        
        if ptype == "IMAGE" and blob:
            self.detail_stack.setCurrentIndex(1)
            pixmap = QPixmap()
            pixmap.loadFromData(blob)
            w, h = self.detail_image_lbl.width(), self.detail_image_lbl.height()
            if w > 0 and h > 0:
                self.detail_image_lbl.setPixmap(pixmap.scaled(QSize(w-10, h-10), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
            else:
                self.detail_image_lbl.setPixmap(pixmap)
            
            self.tools_layout_visible(False)
            self.btn_save_img.setVisible(True)
            
            self.btn_link.setEnabled(False)
            self.btn_google.setEnabled(False)
            if HAS_QRCODE: self.btn_qr.setEnabled(False)
        elif ptype == "FILE":
            self.detail_stack.setCurrentIndex(0)
            self.detail_text.setPlainText(build_file_paths_detail_text(file_paths_from_content(content)))
            self.tools_layout_visible(False)
            self.btn_save_img.setVisible(False)
            self.btn_link.setEnabled(False)
            self.btn_google.setEnabled(False)
            if HAS_QRCODE:
                self.btn_qr.setEnabled(False)
            self.detail_text.setStyleSheet(f"background-color: {theme['surface_variant']}; color: {theme['text']}; border: 2px solid {theme['border']};")
        else:
            self.detail_stack.setCurrentIndex(0)
            self.detail_text.setPlainText(content)
            self.tools_layout_visible(True)
            self.btn_save_img.setVisible(False)
            
            self.btn_link.setEnabled(ptype == "LINK")
            self.btn_google.setEnabled(True)
            if HAS_QRCODE: self.btn_qr.setEnabled(True)
            
            if ptype == "COLOR" and content.startswith("#"):
                self.detail_text.setStyleSheet(f"background-color: {content}; color: {'black' if self.is_light_color(content) else 'white'};")
            else:
                self.detail_text.setStyleSheet(f"background-color: {theme['surface_variant']}; color: {theme['text']}; border: 2px solid {theme['border']};")

        self.btn_copy.setEnabled(True)
        self.btn_pin.setEnabled(True)
        self.btn_del.setEnabled(True)
        
        is_pinned = self.table.item(self.table.currentRow(), 0).text() == "📌"
        self.btn_pin.setText("📌 해제" if is_pinned else "📌 고정")

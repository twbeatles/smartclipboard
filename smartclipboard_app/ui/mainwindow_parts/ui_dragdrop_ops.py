"""MainWindow drag-and-drop helper operations."""

from __future__ import annotations

from PyQt6.QtCore import QEvent, QTimer, Qt

def event_filter_body(self, source, event, fallback_event_filter):
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

def handle_drop_event_body(self, event, THEMES, logger) -> bool:
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


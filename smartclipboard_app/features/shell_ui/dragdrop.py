"""MainWindow drag-and-drop helper operations."""

from __future__ import annotations

from PyQt6.QtCore import QEvent, QTimer, Qt


def event_filter_body(self, source, event, fallback_event_filter):
    viewport = self.table.viewport()
    if viewport is None or source != viewport:
        return fallback_event_filter(source, event)

    if event.type() == QEvent.Type.DragEnter:
        if event.source() == self.table:
            event.acceptProposedAction()
            return True
        return False

    if event.type() == QEvent.Type.DragMove:
        event.acceptProposedAction()
        return True

    if event.type() == QEvent.Type.Drop:
        return self._handle_drop_event(event)

    return fallback_event_filter(source, event)


def handle_drop_event_body(self, event, THEMES, logger) -> bool:
    try:
        target_row = self.table.rowAt(int(event.position().y()))
        if target_row == -1:
            event.ignore()
            return True

        selection_model = self.table.selectionModel()
        if selection_model is None:
            event.ignore()
            return True
        selected_rows = selection_model.selectedRows()
        if not selected_rows:
            event.ignore()
            return True
        source_row = selected_rows[0].row()

        if source_row == target_row:
            event.ignore()
            return True

        source_item = self.table.item(source_row, 0)
        target_item = self.table.item(target_row, 0)
        if not source_item or not target_item:
            event.ignore()
            return True

        is_source_pinned = source_item.text() == "📌"
        is_target_pinned = target_item.text() == "📌"
        if not (is_source_pinned and is_target_pinned):
            status_bar = self.statusBar()
            if status_bar is not None:
                status_bar.showMessage("📌 고정 항목끼리만 순서를 변경할 수 있습니다.", 2000)
            event.ignore()
            return True

        source_pid = source_item.data(Qt.ItemDataRole.UserRole)

        pinned_ids = []
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item and item.text() == "📌":
                pid = item.data(Qt.ItemDataRole.UserRole)
                if pid != source_pid:
                    pinned_ids.append(pid)

        insert_idx = 0
        for row in range(target_row):
            item = self.table.item(row, 0)
            if item and item.text() == "📌":
                pid = item.data(Qt.ItemDataRole.UserRole)
                if pid != source_pid:
                    insert_idx += 1

        pinned_ids.insert(insert_idx, source_pid)
        success = self.db.update_pin_orders(pinned_ids)

        if success:
            QTimer.singleShot(50, self.load_data)
            status_bar = self.statusBar()
            if status_bar is not None:
                status_bar.showMessage("✅ 고정 항목 순서가 변경되었습니다.", 2000)
        else:
            status_bar = self.statusBar()
            if status_bar is not None:
                status_bar.showMessage("⚠️ 순서 변경 중 오류가 발생했습니다.", 2000)

        event.accept()
        return True
    except Exception as e:
        logger.error(f"Drop event error: {e}")
        event.ignore()
        return True

"""MainWindow history interaction operations."""

from __future__ import annotations

def edit_tag_impl(self, namespace):
    Qt = namespace["Qt"]
    QDialog = namespace["QDialog"]
    QInputDialog = namespace["QInputDialog"]
    QMessageBox = namespace["QMessageBox"]
    TagEditDialog = namespace["TagEditDialog"]
    mark_internal_copy = namespace["mark_internal_copy"]

    """선택 항목 태그 편집"""
    pid = self.get_selected_id()
    if not pid:
        return
    current_tags = self.db.get_item_tags(pid)
    dialog = TagEditDialog(self, self.db, pid, current_tags)
    if dialog.exec() == QDialog.DialogCode.Accepted:
        new_tags = dialog.get_tags()
        self.db.set_item_tags(pid, new_tags)
        self.statusBar().showMessage("✅ 태그가 저장되었습니다.", 2000)


def merge_selected_impl(self, namespace):
    Qt = namespace["Qt"]
    QDialog = namespace["QDialog"]
    QInputDialog = namespace["QInputDialog"]
    QMessageBox = namespace["QMessageBox"]
    TagEditDialog = namespace["TagEditDialog"]
    mark_internal_copy = namespace["mark_internal_copy"]

    """선택된 여러 항목 병합"""
    rows = self.table.selectionModel().selectedRows()
    if len(rows) < 2:
        QMessageBox.information(self, "알림", "병합하려면 2개 이상의 항목을 선택하세요.")
        return

    # 구분자 선택
    separators = {"줄바꿈": "\n", "콤마": ", ", "공백": " ", "탭": "\t"}
    sep_name, ok = QInputDialog.getItem(self, "병합", "구분자 선택:", list(separators.keys()), 0, False)
    if not ok:
        return

    separator = separators[sep_name]
    contents = []
    for row_idx in sorted([r.row() for r in rows]):
        pid = self.table.item(row_idx, 0).data(Qt.ItemDataRole.UserRole)
        data = self.db.get_content(pid)
        if data and data[2] != "IMAGE":
            contents.append(data[0])

    if contents:
        merged = separator.join(contents)
        mark_internal_copy(self)
        self.clipboard.setText(merged)
        self.statusBar().showMessage(f"✅ {len(contents)}개 항목 병합 완료", 2000)


def filter_by_tag_impl(self, namespace, tag):
    Qt = namespace["Qt"]
    QDialog = namespace["QDialog"]
    QInputDialog = namespace["QInputDialog"]
    QMessageBox = namespace["QMessageBox"]
    TagEditDialog = namespace["TagEditDialog"]
    mark_internal_copy = namespace["mark_internal_copy"]

    """태그로 필터링"""
    self.current_tag_filter = tag
    if tag:
        self.statusBar().showMessage(f"🏷️ '{tag}' 태그 필터 적용", 2000)
    self.load_data()


def refresh_collection_filter_options_impl(self, namespace):
    Qt = namespace["Qt"]
    QDialog = namespace["QDialog"]
    QInputDialog = namespace["QInputDialog"]
    QMessageBox = namespace["QMessageBox"]
    TagEditDialog = namespace["TagEditDialog"]
    mark_internal_copy = namespace["mark_internal_copy"]

    """컬렉션 필터 콤보 항목 갱신."""
    if not hasattr(self, "collection_filter_combo"):
        return
    current = getattr(self, "current_collection_filter", "__all__")
    self.collection_filter_combo.blockSignals(True)
    try:
        self.collection_filter_combo.clear()
        self.collection_filter_combo.addItem("📂 전체 컬렉션", "__all__")
        self.collection_filter_combo.addItem("🧺 미분류", "__uncategorized__")
        for cid, cname, cicon, _ccolor, _created_at in self.db.get_collections():
            self.collection_filter_combo.addItem(f"{cicon} {cname}", cid)

        idx = self.collection_filter_combo.findData(current)
        if idx < 0:
            idx = 0
            current = "__all__"
        self.current_collection_filter = current
        self.collection_filter_combo.setCurrentIndex(idx)
    finally:
        self.collection_filter_combo.blockSignals(False)


def on_collection_filter_changed_impl(self, namespace, _index):
    Qt = namespace["Qt"]
    QDialog = namespace["QDialog"]
    QInputDialog = namespace["QInputDialog"]
    QMessageBox = namespace["QMessageBox"]
    TagEditDialog = namespace["TagEditDialog"]
    mark_internal_copy = namespace["mark_internal_copy"]

    if not hasattr(self, "collection_filter_combo"):
        return
    self.current_collection_filter = self.collection_filter_combo.currentData()
    self.load_data()


def on_header_clicked_impl(self, namespace, section):
    Qt = namespace["Qt"]
    QDialog = namespace["QDialog"]
    QInputDialog = namespace["QInputDialog"]
    QMessageBox = namespace["QMessageBox"]
    TagEditDialog = namespace["TagEditDialog"]
    mark_internal_copy = namespace["mark_internal_copy"]

    """헤더 클릭 시 정렬 토글"""
    # 📌(0) 컬럼은 정렬 비활성화
    if section == 0:
        return

    # 같은 컬럼 클릭: 정렬 순서 토글
    if self.sort_column == section:
        if self.sort_order == Qt.SortOrder.AscendingOrder:
            self.sort_order = Qt.SortOrder.DescendingOrder
        else:
            self.sort_order = Qt.SortOrder.AscendingOrder
    else:
        self.sort_column = section
        self.sort_order = Qt.SortOrder.AscendingOrder
    self._search_sort_override = not (
        self.sort_column == 3 and self.sort_order == Qt.SortOrder.DescendingOrder
    )

    # 헤더 라벨 업데이트 (정렬 표시자)
    header_labels = ["📌", "유형", "내용", "시간", "사용"]
    for i in range(len(header_labels)):
        if i == section:
            indicator = "▲" if self.sort_order == Qt.SortOrder.AscendingOrder else "▼"
            header_labels[i] = f"{header_labels[i]} {indicator}"
    self.table.setHorizontalHeaderLabels(header_labels)

    self.load_data()


__all__ = [
    "edit_tag_impl",
    "filter_by_tag_impl",
    "merge_selected_impl",
    "on_collection_filter_changed_impl",
    "on_header_clicked_impl",
    "refresh_collection_filter_options_impl",
]

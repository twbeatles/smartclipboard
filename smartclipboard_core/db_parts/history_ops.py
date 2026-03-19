from __future__ import annotations
import datetime
import os
import sqlite3

from .shared import CLEANUP_INTERVAL, DEFAULT_MAX_HISTORY, FILTER_TAG_MAP, history_order_by, logger

class HistoryOpsMixin:
    def add_item(self, content: str, image_data: bytes | None, type_tag: str) -> int | bool:
        """항목 추가. 동일 텍스트는 기존 항목을 최신 상태로 갱신."""
        with self.lock:
            try:
                cursor = self.conn.cursor()
                timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                updated_existing = False

                if type_tag != "IMAGE":
                    cursor.execute(
                        "SELECT id FROM history WHERE content = ? AND type != 'IMAGE' "
                        "ORDER BY timestamp DESC, id DESC LIMIT 1",
                        (content,),
                    )
                    existing = cursor.fetchone()
                    if existing:
                        item_id = int(existing[0])
                        cursor.execute(
                            "UPDATE history SET content = ?, image_data = NULL, type = ?, timestamp = ? WHERE id = ?",
                            (content, type_tag, timestamp, item_id),
                        )
                        updated_existing = True
                    else:
                        cursor.execute(
                            "INSERT INTO history (content, image_data, type, timestamp) VALUES (?, ?, ?, ?)",
                            (content, image_data, type_tag, timestamp),
                        )
                        item_id = cursor.lastrowid
                        if item_id is None:
                            raise sqlite3.Error("Inserted history row has no id")
                else:
                    cursor.execute(
                        "INSERT INTO history (content, image_data, type, timestamp) VALUES (?, ?, ?, ?)",
                        (content, image_data, type_tag, timestamp),
                    )
                    item_id = cursor.lastrowid
                    if item_id is None:
                        raise sqlite3.Error("Inserted history row has no id")

                self.conn.commit()

                if updated_existing:
                    logger.debug(f"항목 갱신: {type_tag} (id={item_id})")
                else:
                    # v10.0: cleanup 최적화 - 매번이 아닌 N회마다 실행
                    self.add_count += 1
                    if self.add_count >= CLEANUP_INTERVAL:
                        self.cleanup()
                        self.add_count = 0
                    logger.debug(f"항목 추가: {type_tag} (id={item_id})")
                return item_id
            except sqlite3.Error as e:
                logger.exception("DB Add Error")
                self.conn.rollback()
                return False

    def get_items(self, search_query: str = "", type_filter: str = "전체") -> list:
        with self.lock:
            try:
                cursor = self.conn.cursor()
                sql = "SELECT id, content, type, timestamp, pinned, use_count, pin_order FROM history WHERE 1=1"
                params = []

                if search_query:
                    sql += " AND content LIKE ?"
                    params.append(f"%{search_query}%")
                
                if type_filter == "📌 고정":
                    sql += " AND pinned = 1"
                elif type_filter == "⭐ 북마크":
                    sql += " AND bookmark = 1"
                elif type_filter in FILTER_TAG_MAP:  # v10.0: 상수 사용
                    sql += " AND type = ?"
                    params.append(FILTER_TAG_MAP[type_filter])
                elif type_filter != "전체":
                    # 레거시 필터 호환성
                    legacy_map = {"텍스트": "TEXT", "이미지": "IMAGE", "링크": "LINK", "코드": "CODE", "색상": "COLOR"}
                    if type_filter in legacy_map:
                        sql += " AND type = ?"
                        params.append(legacy_map[type_filter])

                sql += f" {history_order_by()}"
                cursor.execute(sql, params)
                return cursor.fetchall()
            except sqlite3.Error as e:
                logger.exception("DB Get Error")
                return []

    def update_pin_order(self, item_id: int, order: int) -> bool:
        """고정 항목의 순서를 업데이트"""
        with self.lock:
            try:
                cursor = self.conn.cursor()
                cursor.execute("UPDATE history SET pin_order = ? WHERE id = ?", (order, item_id))
                self.conn.commit()
                return True
            except sqlite3.Error as e:
                logger.error(f"Pin order update failed: {e}")
                self.conn.rollback()
                return False

    def update_pin_orders(self, ordered_ids: list[int]) -> bool:
        """고정 항목 순서를 원자적으로 업데이트"""
        if not ordered_ids:
            return True
        if len(ordered_ids) != len(set(ordered_ids)):
            logger.error("Pin order update failed: duplicate ids")
            return False

        with self.lock:
            try:
                cursor = self.conn.cursor()
                cursor.execute("BEGIN")
                for order, item_id in enumerate(ordered_ids):
                    cursor.execute(
                        "UPDATE history SET pin_order = ? WHERE id = ? AND pinned = 1",
                        (order, item_id),
                    )
                    if cursor.rowcount != 1:
                        raise sqlite3.Error(f"Invalid pinned item id: {item_id}")
                self.conn.commit()
                return True
            except sqlite3.Error as e:
                logger.error(f"Pin orders bulk update failed: {e}")
                self.conn.rollback()
                return False

    def toggle_pin(self, item_id):
        with self.lock:
            try:
                cursor = self.conn.cursor()
                cursor.execute("SELECT pinned FROM history WHERE id=?", (item_id,))
                current = cursor.fetchone()
                if current:
                    new_status = 0 if current[0] else 1
                    if new_status == 1:
                        # 새 고정 항목은 맨 아래에 추가 (최대 pin_order + 1)
                        cursor.execute("SELECT COALESCE(MAX(pin_order), -1) + 1 FROM history WHERE pinned = 1")
                        new_order = cursor.fetchone()[0]
                        cursor.execute("UPDATE history SET pinned = ?, pin_order = ? WHERE id = ?", 
                                       (new_status, new_order, item_id))
                    else:
                        # 고정 해제 시 pin_order 초기화
                        cursor.execute("UPDATE history SET pinned = ?, pin_order = 0 WHERE id = ?", 
                                       (new_status, item_id))
                    self.conn.commit()
                    return new_status
            except sqlite3.Error as e:
                logger.error(f"DB Pin Error: {e}")
                self.conn.rollback()
            return 0

    def increment_use_count(self, item_id):
        with self.lock:
            try:
                cursor = self.conn.cursor()
                cursor.execute("UPDATE history SET use_count = use_count + 1 WHERE id = ?", (item_id,))
                self.conn.commit()
            except sqlite3.Error as e:
                logger.error(f"DB Use Count Error: {e}")
                self.conn.rollback()

    def delete_item(self, item_id):
        with self.lock:
            try:
                cursor = self.conn.cursor()
                cursor.execute("DELETE FROM history WHERE id = ?", (item_id,))
                self.conn.commit()
                logger.info(f"항목 삭제: {item_id}")
            except sqlite3.Error as e:
                logger.error(f"DB Delete Error: {e}")
                self.conn.rollback()

    def clear_all(self):
        with self.lock:
            try:
                cursor = self.conn.cursor()
                cursor.execute("DELETE FROM history WHERE pinned = 0")
                self.conn.commit()
                logger.info("고정되지 않은 모든 항목 삭제")
            except sqlite3.Error as e:
                logger.error(f"DB Clear Error: {e}")
                self.conn.rollback()

    def get_content(self, item_id):
        with self.lock:
            try:
                cursor = self.conn.cursor()
                cursor.execute("SELECT content, image_data, type FROM history WHERE id=?", (item_id,))
                return cursor.fetchone()
            except sqlite3.Error as e:
                logger.error(f"DB Get Content Error: {e}")
                return None

    def get_all_text_content(self):
        with self.lock:
            try:
                cursor = self.conn.cursor()
                cursor.execute(
                    "SELECT content, timestamp FROM history WHERE type != 'IMAGE' "
                    "ORDER BY timestamp DESC, id DESC"
                )
                return cursor.fetchall()
            except sqlite3.Error as e:
                logger.error(f"DB Get All Text Error: {e}")
                return []

    def get_statistics(self):
        """통계 정보 반환"""
        with self.lock:
            try:
                cursor = self.conn.cursor()
                stats = {}
                cursor.execute("SELECT COUNT(*) FROM history")
                stats['total'] = cursor.fetchone()[0]
                cursor.execute("SELECT COUNT(*) FROM history WHERE pinned = 1")
                stats['pinned'] = cursor.fetchone()[0]
                cursor.execute("SELECT type, COUNT(*) FROM history GROUP BY type")
                stats['by_type'] = dict(cursor.fetchall())
                return stats
            except sqlite3.Error as e:
                logger.error(f"DB Stats Error: {e}")
                return {'total': 0, 'pinned': 0, 'by_type': {}}

    def _get_max_history(self, fallback: int = DEFAULT_MAX_HISTORY) -> int:
        """Resolve max_history setting with safe bounds."""
        raw_value = self.get_setting("max_history", fallback)
        if raw_value is None:
            max_history = fallback
        else:
            try:
                max_history = int(raw_value)
            except (TypeError, ValueError):
                max_history = fallback
        return min(max(max_history, 10), 500)

    def cleanup(self, max_history: int | None = None) -> None:
        """오래된 항목 정리 - 이미지 제한 및 전체 제한 적용."""
        with self.lock:
            try:
                cursor = self.conn.cursor()

                # v10.5: 이미지 항목 별도 제한 (최대 20개)
                max_image_history = 20
                cursor.execute("SELECT COUNT(*) FROM history WHERE type='IMAGE' AND pinned=0")
                img_count = cursor.fetchone()[0]
                if img_count > max_image_history:
                    diff = img_count - max_image_history
                    cursor.execute(
                        f"DELETE FROM history WHERE id IN (SELECT id FROM history WHERE type='IMAGE' AND pinned=0 ORDER BY id ASC LIMIT {diff})"
                    )
                    logger.info(f"오래된 이미지 {diff}개 정리됨")

                # 전체 히스토리 제한 (설정값 반영)
                effective_max_history = self._get_max_history() if max_history is None else max_history
                cursor.execute("SELECT COUNT(*) FROM history WHERE pinned = 0")
                result = cursor.fetchone()
                if not result:
                    self.conn.commit()
                    return

                count = result[0]
                if count > effective_max_history:
                    diff = count - effective_max_history
                    cursor.execute(
                        f"DELETE FROM history WHERE id IN (SELECT id FROM history WHERE pinned = 0 ORDER BY id ASC LIMIT {diff})"
                    )
                    self.conn.commit()
                    logger.info(f"오래된 항목 {diff}개 정리")
                else:
                    self.conn.commit()

                # v10.6: 주기적 VACUUM 실행 (50회 cleanup 마다)
                self.cleanup_count += 1
                if self.cleanup_count >= 50:
                    self.cleanup_count = 0
                    self.conn.execute("VACUUM")
                    logger.info("Database VACUUM completed")
            except sqlite3.Error as e:
                logger.error(f"DB Cleanup Error: {e}")

    def backup_db(self, target_path: str | None = None, force: bool = False) -> bool:
        """WAL 안전 온라인 백업. target_path가 없으면 일일 자동 백업."""
        with self.lock:
            try:
                backup_dir = os.path.join(self.app_dir, "backups")
                os.makedirs(backup_dir, exist_ok=True)

                if target_path:
                    backup_file = target_path
                    os.makedirs(os.path.dirname(os.path.abspath(backup_file)) or ".", exist_ok=True)
                else:
                    today = datetime.datetime.now().strftime("%Y%m%d")
                    backup_file = os.path.join(backup_dir, f"clipboard_history_{today}.db")
                    if os.path.exists(backup_file) and not force:
                        return True

                dest_conn = sqlite3.connect(backup_file)
                try:
                    self.conn.backup(dest_conn)
                finally:
                    dest_conn.close()

                logger.info(f"Database backup created: {backup_file}")

                # 자동 백업만 7일 유지
                if not target_path:
                    backups = sorted(
                        [f for f in os.listdir(backup_dir) if f.startswith("clipboard_history_") and f.endswith(".db")]
                    )
                    if len(backups) > 7:
                        for old_backup in backups[:-7]:
                            try:
                                os.remove(os.path.join(backup_dir, old_backup))
                                logger.info(f"Old backup deleted: {old_backup}")
                            except OSError as cleanup_err:
                                logger.warning(f"Failed to delete old backup: {cleanup_err}")
                return True
            except Exception as e:
                logger.error(f"Backup Error: {e}")
                return False

    def get_today_count(self):
        with self.lock:
            try:
                cursor = self.conn.cursor()
                today = datetime.date.today().strftime("%Y-%m-%d")
                cursor.execute("SELECT COUNT(*) FROM history WHERE timestamp LIKE ?", (f"{today}%",))
                result = cursor.fetchone()
                return result[0] if result else 0
            except sqlite3.Error as e:
                logger.debug(f"Get today count error: {e}")
                return 0

    def get_top_items(self, limit=5):
        with self.lock:
            try:
                cursor = self.conn.cursor()
                cursor.execute("SELECT content, use_count FROM history WHERE type != 'IMAGE' AND use_count > 0 ORDER BY use_count DESC LIMIT ?", (limit,))
                return cursor.fetchall()
            except sqlite3.Error as e:
                logger.debug(f"Get top items error: {e}")
                return []

    def toggle_bookmark(self, item_id):
        with self.lock:
            try:
                cursor = self.conn.cursor()
                cursor.execute("SELECT bookmark FROM history WHERE id = ?", (item_id,))
                current = cursor.fetchone()
                if current:
                    new_status = 0 if current[0] else 1
                    cursor.execute("UPDATE history SET bookmark = ? WHERE id = ?", (new_status, item_id))
                    self.conn.commit()
                    return new_status
            except sqlite3.Error as e:
                logger.error(f"Toggle Bookmark Error: {e}")
                self.conn.rollback()
            return 0

    def get_bookmarked_items(self):
        with self.lock:
            try:
                cursor = self.conn.cursor()
                cursor.execute(
                    "SELECT id, content, type, timestamp, pinned, use_count, pin_order "
                    f"FROM history WHERE bookmark = 1 {history_order_by()}"
                )
                return cursor.fetchall()
            except sqlite3.Error as e:
                logger.error(f"Get Bookmarked Error: {e}")
                return []

    def set_note(self, item_id, note):
        with self.lock:
            try:
                cursor = self.conn.cursor()
                cursor.execute("UPDATE history SET note = ? WHERE id = ?", (note, item_id))
                self.conn.commit()
            except sqlite3.Error as e:
                logger.error(f"Set Note Error: {e}")

    def get_note(self, item_id):
        with self.lock:
            try:
                cursor = self.conn.cursor()
                cursor.execute("SELECT note FROM history WHERE id = ?", (item_id,))
                result = cursor.fetchone()
                return result[0] if result else ""
            except sqlite3.Error as e:
                logger.error(f"Get Note Error: {e}")
                return ""

    def set_item_metadata(self, item_id: int, **metadata) -> bool:
        """항목 메타데이터를 키-값 형태로 일괄 업데이트."""
        allowed = {
            "tags",
            "note",
            "bookmark",
            "collection_id",
            "pinned",
            "pin_order",
            "use_count",
            "timestamp",
        }
        updates = {k: v for k, v in metadata.items() if k in allowed}
        if not updates:
            return True

        with self.lock:
            try:
                cursor = self.conn.cursor()
                cols = ", ".join(f"{k} = ?" for k in updates.keys())
                params = list(updates.values())
                params.append(item_id)
                cursor.execute(f"UPDATE history SET {cols} WHERE id = ?", params)
                self.conn.commit()
                return True
            except sqlite3.Error as e:
                logger.error(f"Set Metadata Error: {e}")
                self.conn.rollback()
                return False

    def add_temp_item(self, content, image_data, type_tag, minutes=30):
        """임시 항목 추가 (N분 후 자동 만료)"""
        with self.lock:
            try:
                cursor = self.conn.cursor()
                timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                expires_at = (datetime.datetime.now() + datetime.timedelta(minutes=minutes)).strftime("%Y-%m-%d %H:%M:%S")
                cursor.execute("INSERT INTO history (content, image_data, type, timestamp, expires_at) VALUES (?, ?, ?, ?, ?)",
                               (content, image_data, type_tag, timestamp, expires_at))
                self.conn.commit()
                return cursor.lastrowid
            except sqlite3.Error as e:
                logger.error(f"Add Temp Item Error: {e}")
                return None

    def cleanup_expired_items(self):
        """만료된 임시 항목 삭제"""
        with self.lock:
            try:
                cursor = self.conn.cursor()
                now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                cursor.execute("DELETE FROM history WHERE expires_at IS NOT NULL AND expires_at < ?", (now,))
                deleted = cursor.rowcount
                self.conn.commit()
                if deleted > 0:
                    logger.info(f"만료된 임시 항목 {deleted}개 삭제됨")
                return deleted
            except sqlite3.Error as e:
                logger.error(f"Cleanup Expired Items Error: {e}")
                return 0

    def close(self):
        if self.conn:
            self.conn.close()
            logger.info("DB 연결 종료")


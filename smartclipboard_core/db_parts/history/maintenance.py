from __future__ import annotations

import datetime
import os
import sqlite3

from smartclipboard_core.file_paths import (
    file_content_from_paths,
    file_paths_from_content,
    file_signature_from_paths,
)

from ..shared import CLEANUP_INTERVAL, DEFAULT_MAX_HISTORY, FILTER_TAG_MAP, history_order_by, logger
from ..typing_helpers import DBRuntimeMixin


class HistoryMaintenanceMixin(DBRuntimeMixin):
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

    def cleanup(self, max_history: int | None = None) -> int:
        """오래된 항목 정리 - 이미지 제한 및 전체 제한 적용."""
        with self.lock:
            deleted_total = 0
            try:
                cursor = self.conn.cursor()

                # v10.5: 이미지 항목 별도 제한 (최대 20개)
                max_image_history = 20
                cursor.execute("SELECT COUNT(*) FROM history WHERE type='IMAGE' AND pinned=0")
                img_count = cursor.fetchone()[0]
                if img_count > max_image_history:
                    diff = img_count - max_image_history
                    cursor.execute(
                        """
                        DELETE FROM history
                        WHERE id IN (
                            SELECT id
                            FROM history
                            WHERE type = 'IMAGE' AND pinned = 0
                            ORDER BY timestamp ASC, id ASC
                            LIMIT ?
                        )
                        """,
                        (diff,),
                    )
                    deleted_total += max(cursor.rowcount or 0, 0)
                    logger.info(f"오래된 이미지 {diff}개 정리됨")

                # 전체 히스토리 제한 (설정값 반영)
                effective_max_history = self._get_max_history() if max_history is None else max_history
                cursor.execute("SELECT COUNT(*) FROM history WHERE pinned = 0")
                result = cursor.fetchone()
                if not result:
                    self.conn.commit()
                    return deleted_total

                count = result[0]
                if count > effective_max_history:
                    diff = count - effective_max_history
                    cursor.execute(
                        """
                        DELETE FROM history
                        WHERE id IN (
                            SELECT id
                            FROM history
                            WHERE pinned = 0
                            ORDER BY timestamp ASC, id ASC
                            LIMIT ?
                        )
                        """,
                        (diff,),
                    )
                    deleted_total += max(cursor.rowcount or 0, 0)
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
                return deleted_total
            except sqlite3.Error as e:
                logger.error(f"DB Cleanup Error: {e}")
                self.conn.rollback()
                return 0

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

    def add_temp_item(self, content, image_data, type_tag, minutes=30):
        """임시 항목 추가 (N분 후 자동 만료)"""
        with self.lock:
            try:
                cursor = self.conn.cursor()
                timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                expires_at = (datetime.datetime.now() + datetime.timedelta(minutes=minutes)).strftime("%Y-%m-%d %H:%M:%S")
                cursor.execute(
                    "INSERT INTO history (content, image_data, type, timestamp, expires_at, file_path, file_signature) "
                    "VALUES (?, ?, ?, ?, ?, '', '')",
                    (content, image_data, type_tag, timestamp, expires_at),
                )
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
            self.conn = None  # type: ignore[assignment]
            logger.info("DB 연결 종료")


__all__ = ["HistoryMaintenanceMixin"]

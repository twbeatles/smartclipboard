from __future__ import annotations

import sqlite3

from ..shared import logger


class SearchFtsMixin:
    def ensure_search_index(self) -> bool:
        with self.lock:
            try:
                cursor = self.conn.cursor()
                cursor.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='history_fts'")
                exists = cursor.fetchone() is not None

                if not exists:
                    try:
                        self.backup_db(force=True)
                    except Exception:
                        logger.exception("FTS init: backup failed (continuing)")

                    cursor.execute(
                        "CREATE VIRTUAL TABLE IF NOT EXISTS history_fts "
                        "USING fts5(content, tags, note, url_title, tokenize='unicode61')"
                    )

                cursor.execute(
                    """
                    CREATE TRIGGER IF NOT EXISTS history_ai AFTER INSERT ON history BEGIN
                        INSERT INTO history_fts(rowid, content, tags, note, url_title)
                        VALUES (new.id, COALESCE(new.content, ''), COALESCE(new.tags, ''), COALESCE(new.note, ''), COALESCE(new.url_title, ''));
                    END;
                    """
                )
                cursor.execute(
                    """
                    CREATE TRIGGER IF NOT EXISTS history_ad AFTER DELETE ON history BEGIN
                        DELETE FROM history_fts WHERE rowid = old.id;
                    END;
                    """
                )
                cursor.execute(
                    """
                    CREATE TRIGGER IF NOT EXISTS history_au AFTER UPDATE OF content, tags, note, url_title ON history BEGIN
                        DELETE FROM history_fts WHERE rowid = old.id;
                        INSERT INTO history_fts(rowid, content, tags, note, url_title)
                        VALUES (new.id, COALESCE(new.content, ''), COALESCE(new.tags, ''), COALESCE(new.note, ''), COALESCE(new.url_title, ''));
                    END;
                    """
                )

                if not exists:
                    cursor.execute("INSERT INTO history_fts(history_fts) VALUES('rebuild')")

                self.conn.commit()
                return True
            except sqlite3.OperationalError as e:
                logger.warning(f"FTS unavailable or failed to initialize: {e}")
                try:
                    self.conn.rollback()
                except Exception:
                    pass
                return False
            except sqlite3.Error as e:
                logger.error(f"FTS init error: {e}")
                try:
                    self.conn.rollback()
                except Exception:
                    pass
                return False

    @staticmethod
    def _tokenize_search_query(query: str) -> list[str]:
        import re

        if not query:
            return []
        tokens = re.findall(r"[\w]+", query, flags=re.UNICODE)
        return [t for t in (x.strip() for x in tokens) if t]

    @classmethod
    def _build_fts_match(cls, query: str) -> str:
        tokens = cls._tokenize_search_query(query)
        if not tokens:
            return ""
        parts = []
        for token in tokens:
            parts.append(f"{token}*" if len(token) > 1 else token)
        return " ".join(parts)

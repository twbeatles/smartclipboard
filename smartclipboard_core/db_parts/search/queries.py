from __future__ import annotations

import sqlite3

from ..shared import FILTER_TAG_MAP, history_order_by, logger


class SearchQueryMixin:
    def search_items(
        self,
        query: str,
        type_filter: str = "전체",
        tag_filter: str | None = None,
        bookmarked: bool = False,
        collection_id: int | None = None,
        limit: int | None = None,
        uncategorized: bool = False,
    ) -> list:
        q = (query or "").strip()
        normalized_tag = (tag_filter or "").replace("，", ",").strip().strip(",") if tag_filter else ""

        self._last_search_used_fts = False
        self._last_search_fallback = False
        self._last_search_error = None

        match_expr = self._build_fts_match(q)
        if q and match_expr:
            with self.lock:
                try:
                    cursor = self.conn.cursor()
                    sql = (
                        "SELECT h.id, h.content, h.type, h.timestamp, h.pinned, h.use_count, h.pin_order "
                        "FROM history h "
                        "JOIN history_fts ON history_fts.rowid = h.id "
                        "WHERE history_fts MATCH ?"
                    )
                    params: list[object] = [match_expr]

                    if normalized_tag:
                        sql += (
                            " AND h.tags IS NOT NULL AND h.tags != '' AND instr("
                            " ',' || REPLACE(REPLACE(REPLACE(h.tags, '，', ','), ', ', ','), ' ,', ',') || ',',"
                            " ',' || ? || ','"
                            " ) > 0"
                        )
                        params.append(normalized_tag)

                    if bookmarked or type_filter == "⭐ 북마크":
                        sql += " AND h.bookmark = 1"
                    elif type_filter == "📌 고정":
                        sql += " AND h.pinned = 1"
                    elif type_filter in FILTER_TAG_MAP:
                        sql += " AND h.type = ?"
                        params.append(FILTER_TAG_MAP[type_filter])
                    elif type_filter != "전체":
                        legacy_map = {"텍스트": "TEXT", "이미지": "IMAGE", "링크": "LINK", "코드": "CODE", "색상": "COLOR", "파일": "FILE"}
                        if type_filter in legacy_map:
                            sql += " AND h.type = ?"
                            params.append(legacy_map[type_filter])

                    if collection_id is not None:
                        sql += " AND h.collection_id = ?"
                        params.append(collection_id)
                    elif uncategorized:
                        sql += " AND h.collection_id IS NULL"

                    sql += " ORDER BY h.pinned DESC, h.pin_order ASC, bm25(history_fts) ASC, h.timestamp DESC, h.id DESC"
                    if limit is not None:
                        sql += " LIMIT ?"
                        params.append(int(limit))

                    cursor.execute(sql, params)
                    rows = cursor.fetchall()
                    self._last_search_used_fts = True
                    if rows:
                        return rows
                except sqlite3.Error as e:
                    self._last_search_fallback = True
                    self._last_search_error = str(e)
                    logger.debug(f"FTS search failed, falling back to LIKE: {e}")

        with self.lock:
            cursor = self.conn.cursor()
            sql = "SELECT id, content, type, timestamp, pinned, use_count, pin_order FROM history WHERE 1=1"
            params2: list[object] = []

            if q:
                like = f"%{q}%"
                sql += " AND (content LIKE ? OR tags LIKE ? OR note LIKE ? OR url_title LIKE ?)"
                params2.extend([like, like, like, like])

            if normalized_tag:
                sql += (
                    " AND tags IS NOT NULL AND tags != '' AND instr("
                    " ',' || REPLACE(REPLACE(REPLACE(tags, '，', ','), ', ', ','), ' ,', ',') || ',',"
                    " ',' || ? || ','"
                    " ) > 0"
                )
                params2.append(normalized_tag)

            if bookmarked or type_filter == "⭐ 북마크":
                sql += " AND bookmark = 1"
            elif type_filter == "📌 고정":
                sql += " AND pinned = 1"
            elif type_filter in FILTER_TAG_MAP:
                sql += " AND type = ?"
                params2.append(FILTER_TAG_MAP[type_filter])
            elif type_filter != "전체":
                legacy_map = {"텍스트": "TEXT", "이미지": "IMAGE", "링크": "LINK", "코드": "CODE", "색상": "COLOR", "파일": "FILE"}
                if type_filter in legacy_map:
                    sql += " AND type = ?"
                    params2.append(legacy_map[type_filter])

            if collection_id is not None:
                sql += " AND collection_id = ?"
                params2.append(collection_id)
            elif uncategorized:
                sql += " AND collection_id IS NULL"

            sql += f" {history_order_by()}"
            if limit is not None:
                sql += " LIMIT ?"
                params2.append(int(limit))

            cursor.execute(sql, params2)
            return cursor.fetchall()

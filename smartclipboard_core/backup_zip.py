from __future__ import annotations

import datetime as _dt
import hashlib
import io
import json
import zipfile


def _now_ts() -> str:
    return _dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _safe_int(x, default=0) -> int:
    try:
        return int(x)
    except Exception:
        return default


def export_history_zip(db, zip_path: str) -> int:
    """Export history+collections+image blobs into a single zip file.

    Returns the number of history rows exported.
    """
    # Best-effort schema ensure (new DBs / old DBs).
    if hasattr(db, "create_tables"):
        try:
            db.create_tables()
        except Exception:
            pass

    with getattr(db, "lock", _DummyLock()):
        cur = db.conn.cursor()

        # Collections
        cur.execute("SELECT id, name, icon, color, created_at FROM collections ORDER BY id")
        collections = [
            {
                "old_id": cid,
                "name": name,
                "icon": icon,
                "color": color,
                "created_at": created_at,
            }
            for (cid, name, icon, color, created_at) in cur.fetchall()
        ]

        # History (include optional columns if present)
        cols = _history_columns(cur)
        sql = "SELECT " + ", ".join(cols) + " FROM history ORDER BY id"
        cur.execute(sql)
        rows = cur.fetchall()

    manifest = {
        "app": "SmartClipboard Pro",
        "version": getattr(db, "get_setting", lambda *_: None)("version", None)
        if hasattr(db, "get_setting")
        else None,
        "exported_at": _dt.datetime.now().isoformat(),
        "collections": collections,
        "history": [],
    }

    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        exported = 0
        for row in rows:
            item = dict(zip(cols, row))
            old_id = item.get("id")
            ptype = item.get("type")
            blob = item.get("image_data")

            image_ref = None
            if ptype == "IMAGE" and blob:
                # Keep raw png bytes as stored.
                image_ref = f"images/{old_id}.png"
                zf.writestr(image_ref, blob)

            manifest["history"].append(
                {
                    "old_id": old_id,
                    "type": ptype,
                    "timestamp": item.get("timestamp"),
                    "pinned": bool(_safe_int(item.get("pinned"))),
                    "use_count": _safe_int(item.get("use_count")),
                    "pin_order": _safe_int(item.get("pin_order")),
                    "content": item.get("content") or "",
                    "tags": item.get("tags") or "",
                    "note": item.get("note") or "",
                    "bookmark": bool(_safe_int(item.get("bookmark"))),
                    "collection_old_id": item.get("collection_id"),
                    "url_title": item.get("url_title") or "",
                    "file_path": item.get("file_path") or "",
                    "expires_at": item.get("expires_at"),
                    "image_ref": image_ref,
                }
            )
            exported += 1

        zf.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8"))
        return exported


def import_history_zip(db, zip_path: str, conflict: str = "skip") -> int:
    """Import from an exported zip.

    conflict: currently supports only 'skip'.
    Returns the number of history rows imported.
    """
    if conflict != "skip":
        raise ValueError("unsupported conflict policy")

    if hasattr(db, "create_tables"):
        try:
            db.create_tables()
        except Exception:
            pass

    db_lock = getattr(db, "lock", _DummyLock())
    with db_lock:
        cur = db.conn.cursor()
        cur.execute("BEGIN")
        try:
            with zipfile.ZipFile(zip_path, "r") as zf:
                manifest = json.loads(zf.read("manifest.json").decode("utf-8"))

                # Collection mapping: old_id -> new_id
                col_map = _import_collections(db, manifest.get("collections") or [], commit=False)

                # Precompute existing image hashes to skip duplicates.
                existing_image_md5 = _load_existing_image_md5(db)

                imported = 0
                imported_pinned: list[tuple[int, int]] = []  # (new_id, pin_order)

                for h in manifest.get("history") or []:
                    ptype = (h.get("type") or "TEXT").strip().upper()
                    content = h.get("content") or ""
                    file_path = h.get("file_path") or ""
                    image_ref = h.get("image_ref")

                    if _should_skip_existing(db, ptype, content, file_path, image_ref, zf, existing_image_md5):
                        continue

                    image_data = None
                    if image_ref:
                        image_data = zf.read(image_ref)
                        existing_image_md5.add(hashlib.md5(image_data).hexdigest())

                    timestamp = h.get("timestamp") or _now_ts()
                    pinned = 1 if h.get("pinned") else 0
                    use_count = _safe_int(h.get("use_count"))
                    pin_order = _safe_int(h.get("pin_order"))
                    tags = h.get("tags") or ""
                    note = h.get("note") or ""
                    bookmark = 1 if h.get("bookmark") else 0
                    url_title = h.get("url_title") or ""
                    expires_at = h.get("expires_at")

                    old_col = h.get("collection_old_id")
                    new_col = col_map.get(old_col) if old_col is not None else None

                    cur.execute(
                        """
                        INSERT INTO history
                        (content, image_data, type, timestamp, pinned, use_count, tags, pin_order, file_path, url_title, collection_id, note, bookmark, expires_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            content,
                            image_data,
                            ptype,
                            timestamp,
                            pinned,
                            use_count,
                            tags,
                            pin_order,
                            file_path,
                            url_title,
                            new_col,
                            note,
                            bookmark,
                            expires_at,
                        ),
                    )
                    new_id = cur.lastrowid

                    if pinned:
                        imported_pinned.append((new_id, pin_order))
                    imported += 1

                # Normalize imported pinned ordering after insert, preserving existing pinned items.
                if imported_pinned:
                    imported_pinned.sort(key=lambda t: t[1])
                    _append_pin_orders(db, [nid for (nid, _po) in imported_pinned], commit=False)

            db.conn.commit()
            return imported
        except Exception:
            db.conn.rollback()
            raise


class _DummyLock:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def _history_columns(cur) -> list[str]:
    cur.execute("PRAGMA table_info(history)")
    existing = {row[1] for row in cur.fetchall()}
    desired = [
        "id",
        "content",
        "image_data",
        "type",
        "timestamp",
        "pinned",
        "use_count",
        "tags",
        "pin_order",
        "file_path",
        "url_title",
        "collection_id",
        "note",
        "bookmark",
        "expires_at",
    ]
    return [c for c in desired if c in existing]


def _import_collections(db, collections: list[dict], commit: bool = True) -> dict[int, int]:
    with getattr(db, "lock", _DummyLock()):
        cur = db.conn.cursor()
        cur.execute("SELECT id, name FROM collections")
        existing = {((name or "").casefold()): cid for (cid, name) in cur.fetchall()}

        out: dict[int, int] = {}
        for c in collections:
            old_id = c.get("old_id")
            name = (c.get("name") or "").strip()
            if not name or old_id is None:
                continue
            key = name.casefold()
            if key in existing:
                out[int(old_id)] = existing[key]
                continue
            icon = c.get("icon") or "📁"
            color = c.get("color") or "#6366f1"
            created_at = c.get("created_at") or _now_ts()
            cur.execute(
                "INSERT INTO collections (name, icon, color, created_at) VALUES (?, ?, ?, ?)",
                (name, icon, color, created_at),
            )
            new_id = cur.lastrowid
            existing[key] = new_id
            out[int(old_id)] = new_id
        if commit:
            db.conn.commit()
        return out


def _load_existing_image_md5(db) -> set[str]:
    with getattr(db, "lock", _DummyLock()):
        cur = db.conn.cursor()
        cur.execute("SELECT image_data FROM history WHERE type='IMAGE' AND image_data IS NOT NULL")
        out = set()
        for (blob,) in cur.fetchall():
            if blob:
                out.add(hashlib.md5(blob).hexdigest())
        return out


def _should_skip_existing(db, ptype: str, content: str, file_path: str, image_ref: str | None, zf, img_md5: set[str]) -> bool:
    ptype = (ptype or "TEXT").strip().upper()

    if ptype == "IMAGE" and image_ref:
        data = zf.read(image_ref)
        return hashlib.md5(data).hexdigest() in img_md5

    # FILE: use file_path for identity if present, else fall back to content.
    if ptype == "FILE":
        key = file_path or content
        with getattr(db, "lock", _DummyLock()):
            cur = db.conn.cursor()
            cur.execute("SELECT 1 FROM history WHERE type='FILE' AND (file_path = ? OR content = ?) LIMIT 1", (key, key))
            return cur.fetchone() is not None

    # Other text-like types.
    with getattr(db, "lock", _DummyLock()):
        cur = db.conn.cursor()
        cur.execute("SELECT 1 FROM history WHERE type=? AND content=? LIMIT 1", (ptype, content))
        return cur.fetchone() is not None


def _append_pin_orders(db, ordered_ids: list[int], commit: bool = True) -> None:
    if not ordered_ids:
        return
    with getattr(db, "lock", _DummyLock()):
        cur = db.conn.cursor()
        cur.execute("SELECT COALESCE(MAX(pin_order), -1) FROM history WHERE pinned = 1")
        start = _safe_int(cur.fetchone()[0], -1) + 1
        for idx, hid in enumerate(ordered_ids):
            cur.execute("UPDATE history SET pin_order=? WHERE id=?", (start + idx, hid))
        if commit:
            db.conn.commit()

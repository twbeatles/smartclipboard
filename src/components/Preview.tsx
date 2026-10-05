import { useEffect, useState } from "react";
import { Copy, Globe, Pin, Star, Trash2, Zap } from "lucide-react";
import type { Collection, HistoryDetail, HistoryItem } from "../types";
import { TYPE_META, TypeIcon } from "../lib/format";
import { tauriInvoke } from "../lib/tauri";

interface Props {
  item: HistoryItem;
  collections: Collection[];
  onCopy: () => void;
  onPin: () => void;
  onBookmark: () => void;
  onPalette: () => void;
  onFetchTitle: () => void;
  onDelete: () => void;
  onSaveNote: (note: string) => void;
  onSetCollection: (collectionId: number | null) => void;
}

export const canTransform = (item: HistoryItem) => item.type !== "IMAGE" && item.type !== "FILE";

export default function Preview(props: Props) {
  const { item, collections } = props;
  const [note, setNote] = useState(item.note);
  const [image, setImage] = useState<string | null>(null);

  useEffect(() => setNote(item.note), [item.id, item.note]);

  useEffect(() => {
    setImage(null);
    if (item.type !== "IMAGE") return;
    let live = true;
    tauriInvoke<HistoryDetail>("history_detail", { id: item.id })
      .then((d) => {
        if (live && d?.image_data_base64) setImage(d.image_data_base64);
      })
      .catch(() => {});
    return () => {
      live = false;
    };
  }, [item.id, item.type]);

  const tags = item.tags.split(",").map((t) => t.trim()).filter(Boolean);
  const isLinkish = item.type === "TEXT" || item.type === "LINK";

  return (
    <div className="h-full flex flex-col min-h-0">
      {/* Header: meta + actions */}
      <div className="flex items-center gap-1 px-3 h-10 border-b border-theme-border shrink-0">
        <span className="text-theme-muted"><TypeIcon item={item} /></span>
        <span className="text-xs font-medium ml-1">{(TYPE_META[item.type] ?? TYPE_META.TEXT).label}</span>
        <span className="text-[11px] text-theme-muted ml-1.5 truncate">
          {item.timestamp}
          {item.use_count > 0 && ` · ${item.use_count}회 사용`}
        </span>
        <span className="flex-1" />
        <button onClick={props.onPin} className={`icon-btn ${item.pinned ? "text-theme-accent" : ""}`} title={item.pinned ? "고정 해제" : "고정"}>
          <Pin size={15} />
        </button>
        <button onClick={props.onBookmark} className="icon-btn" title={item.bookmark ? "북마크 해제" : "북마크"}>
          <Star size={15} className={item.bookmark ? "text-amber-400 fill-amber-400" : ""} />
        </button>
        {canTransform(item) && (
          <button onClick={props.onPalette} className="icon-btn" title="변환 (Alt+A)">
            <Zap size={15} />
          </button>
        )}
        {isLinkish && (
          <button onClick={props.onFetchTitle} className="icon-btn" title="페이지 제목 가져오기">
            <Globe size={15} />
          </button>
        )}
        <button onClick={props.onDelete} className="icon-btn hover:text-red-400" title="휴지통으로 (Delete)">
          <Trash2 size={15} />
        </button>
        <button onClick={props.onCopy} className="btn-primary ml-1" title="복사 (Enter)">
          <Copy size={13} /> 복사
        </button>
      </div>

      {/* Content */}
      <div className="flex-1 min-h-0 overflow-auto p-3">
        {item.url_title && <div className="text-sm font-semibold mb-2 select-text">{item.url_title}</div>}
        {item.type === "IMAGE" ? (
          image ? (
            <img src={`data:image/png;base64,${image}`} alt={item.content} className="max-w-full rounded border border-theme-border" />
          ) : (
            <div className="text-xs text-theme-muted">{item.content || "이미지"}</div>
          )
        ) : (
          <pre className={`text-[13px] leading-relaxed whitespace-pre-wrap break-words select-text ${item.type === "TEXT" || item.type === "LINK" ? "font-sans" : "font-mono text-xs"}`}>
            {item.content}
          </pre>
        )}
      </div>

      {/* Footer: organize */}
      <div className="border-t border-theme-border px-3 py-2 flex flex-col gap-1.5 shrink-0">
        {tags.length > 0 && (
          <div className="flex gap-1 flex-wrap">
            {tags.map((t) => (
              <span key={t} className="px-1.5 py-0.5 rounded text-[11px] bg-theme-hover text-theme-muted">#{t}</span>
            ))}
          </div>
        )}
        <div className="flex gap-2">
          <input
            value={note}
            onChange={(e) => setNote(e.target.value)}
            onBlur={() => {
              if (note !== item.note) props.onSaveNote(note);
            }}
            onKeyDown={(e) => {
              if (e.key === "Enter") e.currentTarget.blur();
            }}
            placeholder="메모 추가..."
            className="field flex-1 min-w-0"
          />
          {collections.length > 0 && (
            <select
              value={item.collection_id ?? ""}
              onChange={(e) => props.onSetCollection(e.target.value === "" ? null : Number(e.target.value))}
              className="field w-32"
              title="컬렉션"
            >
              <option value="">컬렉션 없음</option>
              {collections.map((c) => (
                <option key={c.id} value={c.id}>{c.name}</option>
              ))}
            </select>
          )}
        </div>
      </div>
    </div>
  );
}

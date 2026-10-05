import { useEffect, useRef } from "react";
import { Copy, Pin, Star } from "lucide-react";
import type { HistoryItem } from "../types";
import { TypeIcon, relativeTime, summarize } from "../lib/format";

interface Props {
  items: HistoryItem[];
  selectedId: number | null;
  loading: boolean;
  filtered: boolean;
  onSelect: (id: number) => void;
  onCopy: (item: HistoryItem) => void;
}

export default function HistoryList({ items, selectedId, loading, filtered, onSelect, onCopy }: Props) {
  const selectedRef = useRef<HTMLLIElement>(null);

  useEffect(() => {
    selectedRef.current?.scrollIntoView({ block: "nearest" });
  }, [selectedId]);

  if (loading || items.length === 0) {
    return (
      <div className="p-8 text-center text-xs text-theme-muted">
        {loading ? "불러오는 중..." : filtered ? "조건에 맞는 항목이 없습니다." : "복사한 내용이 여기에 쌓입니다."}
      </div>
    );
  }

  return (
    <ul>
      {items.map((item) => {
        const selected = item.id === selectedId;
        return (
          <li
            key={item.id}
            ref={selected ? selectedRef : undefined}
            onClick={() => onSelect(item.id)}
            onDoubleClick={() => onCopy(item)}
            className={`group flex items-center gap-2 h-9 pl-2.5 pr-1.5 cursor-default border-l-2 ${
              selected ? "bg-theme-accent/15 border-l-theme-accent" : "border-l-transparent hover:bg-theme-hover/60"
            }`}
          >
            <span className={selected ? "text-theme-accent" : "text-theme-muted"}>
              <TypeIcon item={item} />
            </span>
            <span className={`flex-1 min-w-0 truncate text-[13px] ${item.type === "CODE" ? "font-mono text-xs" : ""}`}>
              {summarize(item)}
            </span>
            {item.pinned && <Pin size={11} className="text-theme-accent shrink-0" />}
            {item.bookmark && <Star size={11} className="text-amber-400 fill-amber-400 shrink-0" />}
            <span className="text-[11px] text-theme-muted shrink-0 tabular-nums group-hover:hidden">
              {relativeTime(item.timestamp)}
            </span>
            <button
              onClick={(e) => {
                e.stopPropagation();
                onCopy(item);
              }}
              className="icon-btn hidden group-hover:inline-flex"
              title="복사"
            >
              <Copy size={13} />
            </button>
          </li>
        );
      })}
    </ul>
  );
}

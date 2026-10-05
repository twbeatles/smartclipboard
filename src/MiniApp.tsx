import { useCallback, useEffect, useRef, useState } from "react";
import { Pin, Search } from "lucide-react";
import type { HistoryItem } from "./types";
import { listenAll, tauriInvoke } from "./lib/tauri";
import { TypeIcon, relativeTime, summarize } from "./lib/format";

const MINI_LIMIT = 30;

export default function MiniApp() {
  const [items, setItems] = useState<HistoryItem[]>([]);
  const [query, setQuery] = useState("");
  const [selectedIndex, setSelectedIndex] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const input = useRef<HTMLInputElement>(null);
  const selectedRow = useRef<HTMLLIElement>(null);
  const loadSeq = useRef(0);

  const load = useCallback(async () => {
    const seq = ++loadSeq.current;
    try {
      const q = query.trim();
      const res = q
        ? await tauriInvoke<HistoryItem[]>("history_search", { filter: { query: q, limit: MINI_LIMIT } })
        : await tauriInvoke<HistoryItem[]>("history_list", { limit: MINI_LIMIT });
      if (seq !== loadSeq.current) return;
      // Images cannot be pasted from here (no native image restore).
      setItems((Array.isArray(res) ? res : []).filter((i) => i.type !== "IMAGE"));
      setSelectedIndex(0);
    } catch (e) {
      console.error("Mini load error:", e);
    }
  }, [query]);
  const loadRef = useRef(load);
  loadRef.current = load;

  useEffect(() => {
    void load();
  }, [load]);

  // The window is reused across Alt+V presses: start fresh each time it is shown.
  useEffect(() => {
    const applyTheme = () => {
      tauriInvoke<Record<string, string>>("settings_get_all")
        .then((s) => {
          if (s?.theme) document.documentElement.setAttribute("data-theme", s.theme);
        })
        .catch(() => {});
    };
    const onFocus = () => {
      setError(null);
      setQuery("");
      applyTheme();
      void loadRef.current();
      input.current?.focus();
    };
    applyTheme();
    window.addEventListener("focus", onFocus);
    const unlisten = listenAll({ history_changed: () => void loadRef.current() });
    return () => {
      window.removeEventListener("focus", onFocus);
      unlisten();
    };
  }, []);

  useEffect(() => {
    selectedRow.current?.scrollIntoView({ block: "nearest" });
  }, [selectedIndex]);

  const paste = async (item: HistoryItem | undefined) => {
    if (!item) return;
    try {
      await tauriInvoke("history_paste", { id: item.id });
    } catch {
      setError("붙여넣기에 실패했습니다.");
    }
  };

  const onKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setSelectedIndex((prev) => Math.min(prev + 1, Math.max(0, items.length - 1)));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setSelectedIndex((prev) => Math.max(prev - 1, 0));
    } else if (e.key === "Enter") {
      e.preventDefault();
      void paste(items[selectedIndex]);
    } else if (e.key === "Escape") {
      tauriInvoke("hide_mini_window").catch(() => {});
    }
  };

  return (
    <div onKeyDown={onKeyDown} className="flex flex-col h-screen w-screen bg-theme-bg text-theme-text select-none border border-theme-border overflow-hidden">
      <div className="flex items-center gap-2 px-3 h-10 border-b border-theme-border bg-theme-card shrink-0">
        <Search size={14} className="text-theme-muted shrink-0" />
        <input
          ref={input}
          autoFocus
          type="text"
          placeholder="검색해서 붙여넣기"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          className="flex-1 min-w-0 bg-transparent text-[13px] placeholder:text-theme-muted/70 outline-none"
        />
      </div>
      <ul className="flex-1 overflow-y-auto">
        {items.length === 0 && <li className="p-6 text-center text-xs text-theme-muted">{query ? "검색 결과가 없습니다." : "히스토리가 비어 있습니다."}</li>}
        {items.map((item, idx) => {
          const selected = idx === selectedIndex;
          return (
            <li
              key={item.id}
              ref={selected ? selectedRow : undefined}
              onMouseMove={() => setSelectedIndex(idx)}
              onClick={() => void paste(item)}
              className={`flex items-center gap-2 h-9 pl-2.5 pr-3 cursor-default border-l-2 ${
                selected ? "bg-theme-accent/15 border-l-theme-accent" : "border-l-transparent"
              }`}
            >
              <span className={selected ? "text-theme-accent" : "text-theme-muted"}>
                <TypeIcon item={item} />
              </span>
              <span className="flex-1 min-w-0 truncate text-[13px]">{summarize(item)}</span>
              {item.pinned && <Pin size={11} className="text-theme-accent shrink-0" />}
              <span className="text-[11px] text-theme-muted shrink-0">{relativeTime(item.timestamp)}</span>
            </li>
          );
        })}
      </ul>
      <div className="px-3 h-6 flex items-center border-t border-theme-border bg-theme-card text-[11px] text-theme-muted shrink-0">
        {error ? <span className="text-red-400">{error}</span> : "↑↓ 이동 · Enter 붙여넣기 · Esc 닫기"}
      </div>
    </div>
  );
}

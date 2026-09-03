import { useState, useEffect } from "react";
import type { HistoryItem } from "./types";

async function tauriInvoke<T>(cmd: string, args: Record<string, unknown> = {}): Promise<T> {
  if (typeof window !== "undefined" && (window as unknown as { __TAURI_INTERNALS__?: unknown }).__TAURI_INTERNALS__) {
    const { invoke } = await import("@tauri-apps/api/core");
    return invoke<T>(cmd, args);
  }
  return [] as unknown as T;
}

export default function MiniApp() {
  const [items, setItems] = useState<HistoryItem[]>([]);
  const [query, setQuery] = useState("");
  const [selectedIndex, setSelectedIndex] = useState(0);

  useEffect(() => {
    async function load() {
      try {
        let res: HistoryItem[] = [];
        if (query.trim()) {
          res = await tauriInvoke<HistoryItem[]>("history_search", {
            filter: { query: query.trim(), limit: 20 },
          });
        } else {
          res = await tauriInvoke<HistoryItem[]>("history_list", { limit: 20 });
        }
        setItems(res || []);
        setSelectedIndex(0);
      } catch (e) {
        console.error("Mini load error:", e);
      }
    }
    load();
  }, [query]);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "ArrowDown") {
        e.preventDefault();
        setSelectedIndex((prev) => Math.min(prev + 1, Math.max(0, items.length - 1)));
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        setSelectedIndex((prev) => Math.max(prev - 1, 0));
      } else if (e.key === "Escape") {
        // Hide window
        tauriInvoke("hide_mini_window").catch(() => {});
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [items.length]);

  return (
    <div className="flex flex-col h-screen w-screen bg-theme-bg text-theme-text font-sans select-none border border-theme-border rounded-xl shadow-2xl overflow-hidden">
      <div className="p-2 border-b border-theme-border bg-theme-card flex items-center gap-2">
        <span className="text-sm">🔍</span>
        <input
          autoFocus
          type="text"
          placeholder="미니 검색 (Esc 닫기)..."
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          className="flex-1 bg-transparent text-sm text-theme-text placeholder:text-theme-muted outline-none"
        />
      </div>
      <div className="flex-1 overflow-y-auto divide-y divide-theme-border/40">
        {items.map((item, idx) => (
          <div
            key={item.id}
            onClick={() => setSelectedIndex(idx)}
            className={`p-2.5 cursor-pointer text-xs flex flex-col gap-1 transition ${
              selectedIndex === idx ? "bg-theme-accent/20 border-l-4 border-l-theme-accent font-medium" : "hover:bg-theme-hover"
            }`}
          >
            <div className="flex justify-between text-[11px] text-theme-muted">
              <span>{item.type}</span>
              <span>{item.timestamp}</span>
            </div>
            <div className="truncate font-mono text-theme-text">{item.content}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

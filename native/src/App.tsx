import React, { useState, useEffect } from "react";
import type { HistoryItem, Collection, ItemType } from "./types";

// Safe wrapper for Tauri invoke
async function tauriInvoke<T>(cmd: string, args: Record<string, unknown> = {}): Promise<T> {
  if (typeof window !== "undefined" && (window as unknown as { __TAURI_INTERNALS__?: unknown }).__TAURI_INTERNALS__) {
    const { invoke } = await import("@tauri-apps/api/core");
    return invoke<T>(cmd, args);
  }
  // Browser preview fallback
  console.log(`[Browser Preview] invoke: ${cmd}`, args);
  return [] as unknown as T;
}

const TYPE_ICONS: Record<ItemType, string> = {
  TEXT: "📝",
  LINK: "🔗",
  IMAGE: "🖼️",
  CODE: "💻",
  COLOR: "🎨",
  FILE: "📎",
};

export default function App() {
  const [items, setItems] = useState<HistoryItem[]>([]);
  const [collections, setCollections] = useState<Collection[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [activeTypeFilter, setActiveTypeFilter] = useState("전체");
  const [activeCollectionId, setActiveCollectionId] = useState<number | null>(null);
  const [theme, setTheme] = useState("Ocean");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
  }, [theme]);

  // Load initial settings and data
  useEffect(() => {
    async function init() {
      setLoading(true);
      try {
        const settings = await tauriInvoke<Record<string, string>>("settings_get_all");
        if (settings?.theme) {
          setTheme(settings.theme);
        }
        const cols = await tauriInvoke<Collection[]>("collections_list");
        if (Array.isArray(cols)) {
          setCollections(cols);
        }
        await loadItems();
      } catch (err) {
        console.error("Initialization error:", err);
      } finally {
        setLoading(false);
      }
    }
    init();
  }, []);

  const loadItems = async (query = searchQuery, typeFilter = activeTypeFilter, colId = activeCollectionId) => {
    try {
      let res: HistoryItem[] = [];
      if (query.trim() || typeFilter !== "전체" || colId !== null) {
        res = await tauriInvoke<HistoryItem[]>("history_search", {
          filter: {
            query: query.trim(),
            type_filter: typeFilter,
            collection_id: colId,
            limit: 100,
          },
        });
      } else {
        res = await tauriInvoke<HistoryItem[]>("history_list", { limit: 100 });
      }
      setItems(res || []);
      if (res && res.length > 0 && selectedId === null) {
        setSelectedId(res[0].id);
      }
    } catch (err) {
      console.error("Failed to load history items:", err);
    }
  };

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    loadItems(searchQuery, activeTypeFilter, activeCollectionId);
  };

  const selectedItem = items.find((i) => i.id === selectedId);

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-theme-bg text-theme-text font-sans select-none">
      {/* Sidebar */}
      <aside className="w-56 bg-theme-card border-r border-theme-border flex flex-col p-3 gap-4 shrink-0">
        <div className="flex items-center gap-2 px-2 py-1">
          <span className="text-xl">📋</span>
          <div>
            <h1 className="font-bold text-sm leading-tight tracking-wide">SmartClipboard</h1>
            <span className="text-[10px] text-theme-muted uppercase tracking-wider font-semibold">Native Rust Shell</span>
          </div>
        </div>

        {/* Read-Only Badge */}
        <div className="px-2.5 py-1.5 rounded bg-amber-500/10 border border-amber-500/30 text-amber-400 text-xs flex items-center gap-1.5 font-medium">
          <span className="inline-block w-2 h-2 rounded-full bg-amber-400 animate-pulse"></span>
          <span>읽기 전용 호환 모드 (M-C)</span>
        </div>

        {/* Navigation Categories */}
        <nav className="flex flex-col gap-1 text-xs">
          <button
            onClick={() => {
              setActiveCollectionId(null);
              setActiveTypeFilter("전체");
              loadItems(searchQuery, "전체", null);
            }}
            className={`flex items-center gap-2 px-3 py-2 rounded-md text-left transition ${
              activeCollectionId === null && activeTypeFilter === "전체"
                ? "bg-theme-accent/20 text-theme-accent font-semibold"
                : "hover:bg-theme-hover text-theme-muted"
            }`}
          >
            <span>📜</span> 전체 히스토리
          </button>
          <button
            onClick={() => {
              setActiveTypeFilter("⭐ 북마크");
              loadItems(searchQuery, "⭐ 북마크", activeCollectionId);
            }}
            className={`flex items-center gap-2 px-3 py-2 rounded-md text-left transition ${
              activeTypeFilter === "⭐ 북마크"
                ? "bg-theme-accent/20 text-theme-accent font-semibold"
                : "hover:bg-theme-hover text-theme-muted"
            }`}
          >
            <span>⭐</span> 북마크
          </button>
        </nav>

        {/* Collections */}
        <div className="flex flex-col gap-1 text-xs mt-2">
          <div className="text-[11px] font-semibold text-theme-muted px-2 py-1">컬렉션</div>
          {collections.map((col) => (
            <button
              key={col.id}
              onClick={() => {
                const nextColId = activeCollectionId === col.id ? null : col.id;
                setActiveCollectionId(nextColId);
                loadItems(searchQuery, activeTypeFilter, nextColId);
              }}
              className={`flex items-center gap-2 px-3 py-1.5 rounded-md text-left transition ${
                activeCollectionId === col.id
                  ? "bg-theme-accent/20 text-theme-accent font-semibold"
                  : "hover:bg-theme-hover text-theme-muted"
              }`}
            >
              <span>{col.icon || "📁"}</span> {col.name}
            </button>
          ))}
        </div>

        {/* Theme Selector */}
        <div className="mt-auto pt-3 border-t border-theme-border flex items-center justify-between text-xs px-1">
          <span className="text-theme-muted">테마</span>
          <select
            value={theme}
            onChange={(e) => setTheme(e.target.value)}
            className="bg-theme-bg border border-theme-border rounded px-2 py-1 text-xs text-theme-text outline-none focus:border-theme-accent"
          >
            <option value="Dark">Dark</option>
            <option value="Light">Light</option>
            <option value="Ocean">Ocean</option>
            <option value="Purple">Purple</option>
            <option value="Midnight">Midnight</option>
          </select>
        </div>
      </aside>

      {/* Main Content Area */}
      <main className="flex-1 flex flex-col min-w-0 bg-theme-bg">
        {/* Search Header */}
        <header className="p-3 border-b border-theme-border flex flex-col gap-2 bg-theme-card/50 backdrop-blur-sm">
          <form onSubmit={handleSearch} className="flex gap-2">
            <input
              type="text"
              placeholder="클립보드 전문 검색 (FTS5)..."
              value={searchQuery}
              onChange={(e) => {
                setSearchQuery(e.target.value);
                loadItems(e.target.value, activeTypeFilter, activeCollectionId);
              }}
              className="flex-1 bg-theme-bg border border-theme-border rounded-lg px-3 py-2 text-sm text-theme-text placeholder:text-theme-muted/60 outline-none focus:border-theme-accent transition"
            />
            <button
              type="submit"
              className="px-4 py-2 bg-theme-accent text-white rounded-lg text-sm font-medium hover:opacity-90 transition"
            >
              검색
            </button>
          </form>

          {/* Type Filter Tabs */}
          <div className="flex gap-1 overflow-x-auto pb-1 text-xs scrollbar-none">
            {["전체", "📝 텍스트", "🖼️ 이미지", "🔗 링크", "💻 코드", "🎨 색상", "📎 파일"].map((tab) => (
              <button
                key={tab}
                onClick={() => {
                  setActiveTypeFilter(tab);
                  loadItems(searchQuery, tab, activeCollectionId);
                }}
                className={`px-2.5 py-1 rounded-full whitespace-nowrap transition ${
                  activeTypeFilter === tab
                    ? "bg-theme-accent text-white font-medium shadow-sm"
                    : "bg-theme-card hover:bg-theme-hover text-theme-muted"
                }`}
              >
                {tab}
              </button>
            ))}
          </div>
        </header>

        {/* Body: Split View (List + Preview) */}
        <div className="flex-1 flex min-h-0">
          {/* Item List */}
          <div className="w-1/2 border-r border-theme-border overflow-y-auto divide-y divide-theme-border/50">
            {loading ? (
              <div className="p-8 text-center text-sm text-theme-muted">불러오는 중...</div>
            ) : items.length === 0 ? (
              <div className="p-8 text-center text-sm text-theme-muted">
                {searchQuery ? "검색 결과가 없습니다." : "히스토리가 비어 있습니다."}
              </div>
            ) : (
              items.map((item) => (
                <div
                  key={item.id}
                  onClick={() => setSelectedId(item.id)}
                  className={`p-3 cursor-pointer transition flex flex-col gap-1.5 ${
                    selectedId === item.id ? "bg-theme-accent/15 border-l-4 border-l-theme-accent" : "hover:bg-theme-hover"
                  }`}
                >
                  <div className="flex items-center justify-between text-xs text-theme-muted">
                    <span className="flex items-center gap-1.5 font-medium text-theme-text">
                      <span>{TYPE_ICONS[item.type] || "📄"}</span>
                      {item.pinned && <span className="text-amber-400">📌</span>}
                      {item.bookmark && <span className="text-yellow-400">⭐</span>}
                      <span className="text-[11px] opacity-75">{item.type}</span>
                    </span>
                    <span className="text-[11px]">{item.timestamp}</span>
                  </div>
                  <p className="text-sm line-clamp-2 break-all text-theme-text/90 font-mono">
                    {item.content || "(내용 없음)"}
                  </p>
                  {item.tags && (
                    <div className="flex gap-1 flex-wrap mt-0.5">
                      {item.tags.split(",").map((t, idx) => (
                        <span
                          key={idx}
                          className="px-1.5 py-0.5 rounded text-[10px] bg-theme-bg border border-theme-border text-theme-muted"
                        >
                          #{t.trim()}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              ))
            )}
          </div>

          {/* Item Detail Preview */}
          <div className="w-1/2 p-4 flex flex-col gap-3 overflow-y-auto bg-theme-card/20">
            {selectedItem ? (
              <>
                <div className="flex items-center justify-between pb-2 border-b border-theme-border">
                  <div className="flex items-center gap-2">
                    <span className="text-xl">{TYPE_ICONS[selectedItem.type]}</span>
                    <div>
                      <h2 className="text-sm font-semibold">{selectedItem.type} 항목 상세</h2>
                      <span className="text-xs text-theme-muted">{selectedItem.timestamp}</span>
                    </div>
                  </div>
                  <div className="flex items-center gap-2 text-xs">
                    <span className="text-theme-muted">사용 횟수: {selectedItem.use_count}</span>
                  </div>
                </div>

                {selectedItem.url_title && (
                  <div className="p-2 rounded bg-theme-card border border-theme-border text-xs">
                    <span className="text-theme-muted font-medium">URL 제목: </span>
                    <span className="text-theme-text font-semibold">{selectedItem.url_title}</span>
                  </div>
                )}

                {selectedItem.note && (
                  <div className="p-2.5 rounded bg-theme-card border border-theme-border text-xs">
                    <div className="text-theme-muted font-medium mb-1">메모</div>
                    <div className="text-theme-text whitespace-pre-wrap">{selectedItem.note}</div>
                  </div>
                )}

                {/* Content Box */}
                <div className="flex-1 flex flex-col min-h-0 bg-theme-bg border border-theme-border rounded-lg p-3">
                  <span className="text-[11px] font-semibold text-theme-muted uppercase mb-1">본문</span>
                  <pre className="flex-1 overflow-auto text-xs font-mono text-theme-text/90 whitespace-pre-wrap select-text">
                    {selectedItem.content}
                  </pre>
                </div>
              </>
            ) : (
              <div className="m-auto text-sm text-theme-muted">선택된 항목이 없습니다.</div>
            )}
          </div>
        </div>
      </main>
    </div>
  );
}

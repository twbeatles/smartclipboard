import { useCallback, useEffect, useRef, useState } from "react";
import { ClipboardList, Ellipsis, Search, Star, X } from "lucide-react";
import type { Collection, HistoryDetail, HistoryItem } from "./types";
import { errorText, listenAll, tauriInvoke } from "./lib/tauri";
import { TYPE_FILTERS } from "./lib/format";
import AppMenu from "./components/AppMenu";
import HistoryList from "./components/HistoryList";
import PaletteDialog from "./components/PaletteDialog";
import Preview, { canTransform } from "./components/Preview";
import TrashDialog from "./components/TrashDialog";
import VaultDialog from "./components/VaultDialog";

interface UpdateCheckResult {
  status: string;
  current_version: string;
  version?: string | null;
}

interface UpdateOutcome {
  status: string;
  version: string;
  message?: string | null;
  rolled_back: boolean;
}

type Dialog = "palette" | "trash" | "vault" | null;

const HISTORY_LIMIT = 200;

function downloadTextFile(filename: string, text: string, mime: string) {
  const blob = new Blob([text], { type: mime });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

export default function App() {
  const [items, setItems] = useState<HistoryItem[]>([]);
  const [collections, setCollections] = useState<Collection[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [query, setQuery] = useState("");
  const [typeFilter, setTypeFilter] = useState<string>(TYPE_FILTERS[0]);
  const [bookmarkedOnly, setBookmarkedOnly] = useState(false);
  const [collectionId, setCollectionId] = useState<number | null>(null);
  const [theme, setTheme] = useState("Ocean");
  const [loading, setLoading] = useState(true);
  const [toast, setToast] = useState<string | null>(null);
  const [privacy, setPrivacy] = useState(false);
  const [paused, setPaused] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const [dialog, setDialog] = useState<Dialog>(null);
  const [updateMsg, setUpdateMsg] = useState<string | null>(null);
  const [updateBusy, setUpdateBusy] = useState(false);
  const searchInput = useRef<HTMLInputElement>(null);
  const jsonInput = useRef<HTMLInputElement>(null);
  const csvInput = useRef<HTMLInputElement>(null);
  const toastTimer = useRef<number | undefined>(undefined);
  const loadSeq = useRef(0);

  const showToast = useCallback((msg: string) => {
    setToast(msg);
    window.clearTimeout(toastTimer.current);
    toastTimer.current = window.setTimeout(() => setToast(null), 3000);
  }, []);

  const filtered = query.trim() !== "" || typeFilter !== TYPE_FILTERS[0] || bookmarkedOnly || collectionId !== null;

  // ---------- Data loading ----------

  const loadItems = useCallback(async () => {
    const seq = ++loadSeq.current;
    try {
      const res = filtered
        ? await tauriInvoke<HistoryItem[]>("history_search", {
            filter: {
              query: query.trim(),
              type_filter: typeFilter,
              bookmarked: bookmarkedOnly ? true : null,
              collection_id: collectionId,
              limit: HISTORY_LIMIT,
            },
          })
        : await tauriInvoke<HistoryItem[]>("history_list", { limit: HISTORY_LIMIT });
      // Drop responses that a newer request has already superseded.
      if (seq === loadSeq.current) setItems(Array.isArray(res) ? res : []);
    } catch (err) {
      console.error("Failed to load history items:", err);
    } finally {
      if (seq === loadSeq.current) setLoading(false);
    }
  }, [filtered, query, typeFilter, bookmarkedOnly, collectionId]);
  const loadItemsRef = useRef(loadItems);
  loadItemsRef.current = loadItems;

  const loadCollections = useCallback(async () => {
    try {
      const cols = await tauriInvoke<Collection[]>("collections_list");
      if (Array.isArray(cols)) setCollections(cols);
    } catch { /* noop */ }
  }, []);

  // Reload on any filter change; typing is debounced.
  useEffect(() => {
    const t = window.setTimeout(() => void loadItems(), query ? 120 : 0);
    return () => window.clearTimeout(t);
  }, [loadItems, query]);

  // Keep the selection on a row that still exists.
  useEffect(() => {
    setSelectedId((cur) => (items.some((i) => i.id === cur) ? cur : items[0]?.id ?? null));
  }, [items]);

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
  }, [theme]);

  useEffect(() => {
    (async () => {
      try {
        const settings = await tauriInvoke<Record<string, string>>("settings_get_all");
        if (settings?.theme) setTheme(settings.theme);
        setPrivacy(settings?.privacy_mode === "1");
        setPaused(settings?.monitoring_paused === "1");
      } catch (err) {
        console.error("Initialization error:", err);
      }
      await loadCollections();
      try {
        const pending = await tauriInvoke<UpdateOutcome | null>("update_pending_result");
        if (pending && typeof pending.status === "string") {
          if (pending.status === "applied") {
            showToast(`업데이트가 완료되었습니다${pending.version ? ` (v${pending.version})` : ""}.`);
          } else {
            showToast(`업데이트 적용에 실패했습니다.${pending.message ? ` 오류: ${pending.message}` : ""}${pending.rolled_back ? " 이전 버전으로 복원했습니다." : ""}`);
          }
        }
      } catch {
        /* preview / staging unavailable */
      }
    })();
  }, [loadCollections, showToast]);

  // Backend events: new captures, capture flags, hotkey errors, title fetches.
  useEffect(
    () =>
      listenAll({
        history_changed: () => void loadItemsRef.current(),
        privacy_changed: (v) => setPrivacy(v === true),
        monitoring_changed: (v) => setPaused(v !== true),
        hotkey_error: (v) => {
          if (typeof v === "string") showToast(v);
        },
        open_settings: () => setMenuOpen(true),
        title_fetch_result: (v) => {
          if (typeof v !== "object" || v === null) return;
          const evt = v as { title?: unknown; message?: unknown };
          if (typeof evt.title === "string" && evt.title) void loadItemsRef.current();
          else if (typeof evt.message === "string" && evt.message) showToast(evt.message);
        },
      }),
    [showToast],
  );

  // ---------- Item actions ----------

  const selectedItem = items.find((i) => i.id === selectedId) ?? null;

  const copyItem = async (item: HistoryItem) => {
    try {
      if (item.type === "IMAGE") {
        const detail = await tauriInvoke<HistoryDetail>("history_detail", { id: item.id });
        if (!detail?.image_data_base64) throw new Error("no image data");
        const bytes = Uint8Array.from(atob(detail.image_data_base64), (c) => c.charCodeAt(0));
        await navigator.clipboard.write([new ClipboardItem({ "image/png": new Blob([bytes], { type: "image/png" }) })]);
        await tauriInvoke("history_mark_used", { id: item.id });
      } else {
        await tauriInvoke("history_copy", { id: item.id });
      }
      showToast("복사했습니다.");
      await loadItems();
    } catch {
      showToast("복사에 실패했습니다.");
    }
  };

  const itemAction = async (cmd: string, args: Record<string, unknown>, failMsg: string) => {
    try {
      await tauriInvoke(cmd, args);
      await loadItems();
    } catch {
      showToast(failMsg);
    }
  };

  const deleteItem = async (item: HistoryItem) => {
    const idx = items.findIndex((i) => i.id === item.id);
    const next = items[idx + 1] ?? items[idx - 1] ?? null;
    try {
      await tauriInvoke("history_delete", { id: item.id });
      setSelectedId(next?.id ?? null);
      showToast("휴지통으로 이동했습니다.");
      await loadItems();
    } catch {
      showToast("삭제에 실패했습니다.");
    }
  };

  const fetchTitle = async (item: HistoryItem) => {
    try {
      const started = await tauriInvoke<boolean>("history_fetch_title", { id: item.id });
      showToast(started === true ? "페이지 제목을 가져오는 중..." : "URL이 없는 항목입니다.");
    } catch {
      showToast("제목 가져오기에 실패했습니다.");
    }
  };

  const moveSelection = (delta: number) => {
    if (items.length === 0) return;
    const idx = items.findIndex((i) => i.id === selectedId);
    const next = Math.min(Math.max(idx + delta, 0), items.length - 1);
    setSelectedId(items[next].id);
  };

  // ---------- Capture flags ----------

  const togglePrivacy = async () => {
    try {
      const next = await tauriInvoke<boolean>("privacy_set", { enabled: !privacy });
      if (typeof next === "boolean") setPrivacy(next);
    } catch {
      showToast("프라이버시 전환에 실패했습니다.");
    }
  };

  const togglePaused = async () => {
    try {
      const enabled = await tauriInvoke<boolean>("monitoring_set", { enabled: paused });
      if (typeof enabled === "boolean") setPaused(!enabled);
    } catch {
      showToast("수집 전환에 실패했습니다.");
    }
  };

  // ---------- Menu actions ----------

  const changeTheme = (next: string) => {
    setTheme(next);
    tauriInvoke("settings_set", { key: "theme", value: next }).catch(() => showToast("테마 저장에 실패했습니다."));
  };

  const addCollection = async (name: string) => {
    try {
      await tauriInvoke("collection_add", { name, icon: "📁", color: "#6366f1" });
      await loadCollections();
      showToast(`컬렉션 “${name}”을 만들었습니다.`);
    } catch (err) {
      showToast(errorText(err) || "컬렉션 추가에 실패했습니다.");
    }
  };

  const deleteCollection = async () => {
    if (collectionId === null) return;
    if (!window.confirm("컬렉션을 삭제할까요? 소속 항목은 유지됩니다.")) return;
    try {
      await tauriInvoke("collection_delete", { id: collectionId });
      setCollectionId(null);
      await loadCollections();
    } catch {
      showToast("컬렉션 삭제에 실패했습니다.");
    }
  };

  const doExport = async (kind: "json" | "csv" | "md") => {
    try {
      if (kind === "json") downloadTextFile("smartclipboard.json", await tauriInvoke<string>("export_json"), "application/json");
      else if (kind === "csv") downloadTextFile("smartclipboard.csv", await tauriInvoke<string>("export_csv"), "text/csv");
      else downloadTextFile("smartclipboard.md", await tauriInvoke<string>("export_markdown"), "text/markdown");
    } catch {
      showToast("내보내기에 실패했습니다.");
    }
  };

  const doImportFile = async (file: File, kind: "json" | "csv") => {
    try {
      const text = await file.text();
      const res = await tauriInvoke<[number, number]>(kind === "json" ? "import_json" : "import_csv", { payload: text });
      showToast(Array.isArray(res) ? `가져오기 완료: ${res[0]}건` : "가져오기 완료");
      // Collections first so the filter reflects imported ones immediately.
      await loadCollections();
      await loadItems();
    } catch (err) {
      showToast(errorText(err) || "가져오기에 실패했습니다.");
    }
  };

  const doCheckUpdate = async () => {
    if (updateBusy) return;
    setUpdateBusy(true);
    setUpdateMsg("업데이트 확인 중...");
    try {
      const res = await tauriInvoke<UpdateCheckResult>("update_check");
      if (!res || typeof res.status !== "string") {
        setUpdateMsg(null);
        showToast("업데이트 확인에 실패했습니다.");
        return;
      }
      if (res.status !== "available" || !res.version) {
        setUpdateMsg(`최신 버전입니다 (v${res.current_version})`);
        return;
      }
      setUpdateMsg(`새 버전 v${res.version}`);
      if (!window.confirm(`새 버전 v${res.version}이 있습니다.\n\n현재: v${res.current_version}\n최신: v${res.version}\n\n다운로드할까요?`)) return;
      setUpdateMsg(`v${res.version} 다운로드 중...`);
      const dl = await tauriInvoke<{ version: string; staged_path: string }>("update_download");
      if (!dl || typeof dl.staged_path !== "string") {
        showToast("업데이트 다운로드에 실패했습니다.");
        setUpdateMsg(null);
        return;
      }
      if (!window.confirm(`업데이트 v${dl.version} 검증을 완료했습니다.\n지금 설치하고 다시 시작할까요?`)) return;
      await tauriInvoke("update_apply", { stagedPath: dl.staged_path });
      await tauriInvoke("quit_for_update");
    } catch (err) {
      console.error("Update failed:", err);
      showToast("업데이트에 실패했습니다.");
      setUpdateMsg(null);
    } finally {
      setUpdateBusy(false);
    }
  };

  // ---------- Keyboard ----------

  const keyHandler = (e: KeyboardEvent) => {
    if (dialog !== null || menuOpen) return;
    const target = e.target as HTMLElement | null;
    const inSearch = target === searchInput.current;
    const typing = !inSearch && target !== null && ["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName);

    if (e.ctrlKey && e.key.toLowerCase() === "f") {
      e.preventDefault();
      searchInput.current?.focus();
      searchInput.current?.select();
      return;
    }
    if (e.altKey && e.key.toLowerCase() === "a") {
      e.preventDefault();
      if (selectedItem && canTransform(selectedItem)) setDialog("palette");
      return;
    }
    if (typing) return;

    if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      e.preventDefault();
      moveSelection(e.key === "ArrowDown" ? 1 : -1);
    } else if (e.key === "Enter" && target?.tagName !== "BUTTON") {
      if (selectedItem) {
        e.preventDefault();
        void copyItem(selectedItem);
      }
    } else if (e.key === "Delete" && !inSearch) {
      if (selectedItem) void deleteItem(selectedItem);
    } else if (e.key === "Escape" && query) {
      setQuery("");
    }
  };
  const keyHandlerRef = useRef(keyHandler);
  keyHandlerRef.current = keyHandler;

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => keyHandlerRef.current(e);
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  // ---------- Render ----------

  const capturing = !privacy && !paused;
  const statusLabel = privacy ? "프라이버시" : paused ? "일시정지" : "수집 중";
  const activeCollection = collections.find((c) => c.id === collectionId) ?? null;

  return (
    <div className="relative flex flex-col h-screen w-screen overflow-hidden bg-theme-bg text-theme-text select-none">
      {/* Top bar: search + capture status + menu */}
      <header className="flex items-center gap-2 px-2 h-11 border-b border-theme-border bg-theme-card shrink-0">
        <div className="flex-1 flex items-center gap-2 h-8 px-2.5 rounded-md bg-theme-bg border border-theme-border focus-within:border-theme-accent">
          <Search size={14} className="text-theme-muted shrink-0" />
          <input
            ref={searchInput}
            autoFocus
            type="text"
            placeholder="검색 (Ctrl+F)"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            className="flex-1 min-w-0 bg-transparent text-[13px] placeholder:text-theme-muted/70 outline-none"
          />
          {query && (
            <button onClick={() => { setQuery(""); searchInput.current?.focus(); }} className="text-theme-muted hover:text-theme-text" title="지우기 (Esc)">
              <X size={14} />
            </button>
          )}
        </div>
        <button
          onClick={() => void (privacy ? togglePrivacy() : togglePaused())}
          className="flex items-center gap-1.5 h-8 px-2.5 rounded-md text-xs hover:bg-theme-hover"
          title={privacy ? "프라이버시 모드 끄기" : paused ? "수집 다시 시작" : "수집 일시정지"}
        >
          <span className={`w-2 h-2 rounded-full ${capturing ? "bg-emerald-400" : "bg-amber-400"}`} />
          {statusLabel}
        </button>
        <button onClick={() => setMenuOpen((v) => !v)} onMouseDown={(e) => e.stopPropagation()} className="icon-btn w-8 h-8" title="메뉴">
          <Ellipsis size={16} />
        </button>
      </header>

      {menuOpen && (
        <AppMenu
          onClose={() => setMenuOpen(false)}
          privacy={privacy}
          onTogglePrivacy={() => void togglePrivacy()}
          theme={theme}
          onTheme={changeTheme}
          onTrash={() => setDialog("trash")}
          onVault={() => setDialog("vault")}
          activeCollection={activeCollection}
          onAddCollection={(name) => void addCollection(name)}
          onDeleteCollection={() => void deleteCollection()}
          onExport={(kind) => void doExport(kind)}
          onImport={(kind) => (kind === "json" ? jsonInput : csvInput).current?.click()}
          updateBusy={updateBusy}
          updateMsg={updateMsg}
          onCheckUpdate={() => void doCheckUpdate()}
        />
      )}

      {/* Filters */}
      <div className="flex items-center gap-1 px-2 h-9 border-b border-theme-border shrink-0 text-xs">
        {TYPE_FILTERS.map((f) => (
          <button key={f} onClick={() => setTypeFilter(f)} className={`chip ${typeFilter === f ? "chip-on" : ""}`}>
            {f}
          </button>
        ))}
        <button onClick={() => setBookmarkedOnly((v) => !v)} className={`chip ${bookmarkedOnly ? "chip-on" : ""}`} title="북마크만 보기">
          <Star size={12} className={bookmarkedOnly ? "fill-current" : ""} />
        </button>
        <span className="flex-1" />
        {collections.length > 0 && (
          <select
            value={collectionId ?? ""}
            onChange={(e) => setCollectionId(e.target.value === "" ? null : Number(e.target.value))}
            className={`field w-36 ${collectionId !== null ? "border-theme-accent text-theme-accent" : ""}`}
            title="컬렉션 필터"
          >
            <option value="">모든 컬렉션</option>
            {collections.map((c) => (
              <option key={c.id} value={c.id}>{c.name}</option>
            ))}
          </select>
        )}
      </div>

      {/* Body: list + preview */}
      <div className="flex-1 flex min-h-0">
        <div className="w-[42%] min-w-[260px] border-r border-theme-border overflow-y-auto">
          <HistoryList
            items={items}
            selectedId={selectedId}
            loading={loading}
            filtered={filtered}
            onSelect={setSelectedId}
            onCopy={(item) => void copyItem(item)}
          />
        </div>
        <div className="flex-1 min-w-0">
          {selectedItem ? (
            <Preview
              item={selectedItem}
              collections={collections}
              onCopy={() => void copyItem(selectedItem)}
              onPin={() => void itemAction("history_toggle_pin", { id: selectedItem.id }, "고정 전환에 실패했습니다.")}
              onBookmark={() => void itemAction("history_toggle_bookmark", { id: selectedItem.id }, "북마크 전환에 실패했습니다.")}
              onPalette={() => setDialog("palette")}
              onFetchTitle={() => void fetchTitle(selectedItem)}
              onDelete={() => void deleteItem(selectedItem)}
              onSaveNote={(note) => void itemAction("history_set_note", { id: selectedItem.id, note }, "메모 저장에 실패했습니다.")}
              onSetCollection={(cid) => void itemAction("history_set_collection", { id: selectedItem.id, collectionId: cid }, "컬렉션 지정에 실패했습니다.")}
            />
          ) : (
            <div className="h-full flex flex-col items-center justify-center gap-2 text-theme-muted">
              <ClipboardList size={28} strokeWidth={1.5} />
              <span className="text-xs">항목을 선택하면 내용이 표시됩니다.</span>
            </div>
          )}
        </div>
      </div>

      {/* Status bar */}
      <footer className="flex items-center justify-between px-3 h-6 border-t border-theme-border bg-theme-card text-[11px] text-theme-muted shrink-0">
        <span>{items.length}개{items.length >= HISTORY_LIMIT ? " (최근 항목만 표시)" : ""}</span>
        <span>Enter 복사 · Del 삭제 · Alt+V 빠른 붙여넣기</span>
      </footer>

      {toast && (
        <div className="fixed bottom-9 left-1/2 -translate-x-1/2 max-w-[80vw] px-3 py-1.5 rounded-md bg-theme-text text-theme-bg text-xs shadow-lg z-50">
          {toast}
        </div>
      )}

      {dialog === "palette" && selectedItem && (
        <PaletteDialog item={selectedItem} onClose={() => setDialog(null)} onChanged={() => void loadItems()} />
      )}
      {dialog === "trash" && (
        <TrashDialog onClose={() => setDialog(null)} onRestored={() => void loadItems()} showToast={showToast} />
      )}
      {dialog === "vault" && <VaultDialog onClose={() => setDialog(null)} showToast={showToast} />}

      <input ref={jsonInput} type="file" accept=".json,application/json" className="hidden" onChange={(e) => { const f = e.target.files?.[0]; if (f) void doImportFile(f, "json"); e.target.value = ""; }} />
      <input ref={csvInput} type="file" accept=".csv,text/csv" className="hidden" onChange={(e) => { const f = e.target.files?.[0]; if (f) void doImportFile(f, "csv"); e.target.value = ""; }} />
    </div>
  );
}

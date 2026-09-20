import React, { useState, useEffect, useRef } from "react";
import type { HistoryItem, Collection, ItemType, TrashItem } from "./types";

interface PaletteAction {
  id: string;
  title: string;
  description: string;
  category: string;
}

interface VaultItem {
  id: number;
  label: string;
  created_at: string;
}

interface UpdateCheckResult {
  status: string;
  current_version: string;
  version?: string | null;
  artifact_url?: string | null;
  artifact_size?: number | null;
  expires_at?: string | null;
}

interface UpdateOutcome {
  status: string;
  version: string;
  target: string;
  backup: string | null;
  message?: string | null;
  rolled_back: boolean;
}


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
  const [toast, setToast] = useState<string | null>(null);
  const [privacy, setPrivacy] = useState(false);
  const [paused, setPaused] = useState(false);
  const [showTrash, setShowTrash] = useState(false);
  const [trashItems, setTrashItems] = useState<TrashItem[]>([]);
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [paletteActions, setPaletteActions] = useState<PaletteAction[]>([]);
  const [paletteActionId, setPaletteActionId] = useState("");
  const [paletteResult, setPaletteResult] = useState<string | null>(null);
  const [vaultOpen, setVaultOpen] = useState(false);
  const [vaultUnlocked, setVaultUnlocked] = useState(false);
  const [vaultHasPassword, setVaultHasPassword] = useState(false);
  const [vaultItems, setVaultItems] = useState<VaultItem[]>([]);
  const [vaultPassword, setVaultPassword] = useState("");
  const [vaultNewPassword, setVaultNewPassword] = useState("");
  const [vaultLabel, setVaultLabel] = useState("");
  const [vaultSecret, setVaultSecret] = useState("");
  const [newCollection, setNewCollection] = useState("");
  const [updateMsg, setUpdateMsg] = useState<string | null>(null);
  const [updateBusy, setUpdateBusy] = useState(false);
  const jsonInput = useRef<HTMLInputElement>(null);
  const csvInput = useRef<HTMLInputElement>(null);
  const reloadRef = useRef<() => Promise<void>>(async () => {});

  const showToast = (msg: string) => {
    setToast(msg);
    window.setTimeout(() => setToast((cur) => (cur === msg ? null : cur)), 3500);
  };


  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
  }, [theme]);

  // Backend event listeners (privacy / monitoring / hotkey errors)
  useEffect(() => {
    let mounted = true;
    const unlistens: Array<() => void> = [];
    (async () => {
      try {
        const tev = await import("@tauri-apps/api/event");
        const on = async (name: string, cb: (v: unknown) => void) => {
          try {
            unlistens.push(await tev.listen(name, (e) => cb(e.payload)));
          } catch {
            /* browser preview: events unavailable */
          }
        };
        await on("privacy_changed", (v) => { if (mounted) setPrivacy(v === true); });
        await on("monitoring_changed", (v) => { if (mounted) setPaused(v !== true); });
        await on("hotkey_error", (v) => { if (mounted && typeof v === "string") showToast(v); });
        await on("title_fetch_result", (v) => {
          if (!mounted || typeof v !== "object" || v === null) return;
          const evt = v as { title?: unknown; message?: unknown };
          if (typeof evt.title === "string" && evt.title) {
            void reloadRef.current();
          } else if (typeof evt.message === "string" && evt.message) {
            showToast(evt.message);
          }
        });
      } catch {
        /* browser preview: events unavailable */
      }
    })();
    return () => {
      mounted = false;
      unlistens.forEach((u) => {
        try { u(); } catch { /* noop */ }
      });
    };
  }, []);

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
        try {
          const hasPw = await tauriInvoke<boolean>("vault_status");
          if (typeof hasPw === "boolean") setVaultHasPassword(hasPw);
        } catch {
          /* vault unavailable in preview */
        }
        await loadItems();
        try {
          const pending = await tauriInvoke<UpdateOutcome | null>("update_pending_result");
          if (pending && typeof pending.status === "string") {
            if (pending.status === "applied") {
              showToast(`✅ 업데이트가 완료되었습니다${pending.version ? ` (v${pending.version})` : ""}.`);
            } else {
              showToast(`업데이트 적용에 실패했습니다.${pending.message ? ` 오류: ${pending.message}` : ""}${pending.rolled_back ? " 이전 버전으로 복원했습니다." : ""}`);
            }
          }
        } catch {
          /* preview / staging unavailable */
        }
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
  reloadRef.current = () => loadItems();

  const refreshAfterWrite = async () => {
    if (showTrash) {
      await loadTrash();
    } else {
      await loadItems();
    }
    try {
      const cols = await tauriInvoke<Collection[]>("collections_list");
      if (Array.isArray(cols)) setCollections(cols);
    } catch { /* noop */ }
  };

  const doPin = async () => {
    if (!selectedItem) return;
    try {
      await tauriInvoke("history_toggle_pin", { id: selectedItem.id });
      await loadItems();
    } catch { showToast("고정 전환에 실패했습니다."); }
  };

  const doBookmark = async () => {
    if (!selectedItem) return;
    try {
      await tauriInvoke("history_toggle_bookmark", { id: selectedItem.id });
      await loadItems();
    } catch { showToast("북마크 전환에 실패했습니다."); }
  };

  const doFetchTitle = async () => {
    if (!selectedItem) return;
    try {
      const started = await tauriInvoke<boolean>("history_fetch_title", { id: selectedItem.id });
      if (started !== true) showToast("URL이 없어 제목 가져오기를 건너뜁니다.");
    } catch { showToast("제목 가져오기에 실패했습니다."); }
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
        setUpdateMsg(`최신 버전 사용 중 (v${res.current_version})`);
        showToast("현재 최신 버전을 사용 중입니다.");
        return;
      }
      setUpdateMsg(`새 버전 v${res.version} 발견`);
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
      showToast("업데이트 확인에 실패했습니다.");
      setUpdateMsg(null);
    } finally {
      setUpdateBusy(false);
    }
  };
  const doDelete = async () => {
    if (!selectedItem) return;
    if (!window.confirm("선택 항목을 휴지통으로 이동할까요?")) return;
    try {
      await tauriInvoke("history_delete", { id: selectedItem.id });
      setSelectedId(null);
      await loadItems();
    } catch { showToast("삭제에 실패했습니다."); }
  };

  const doCopy = async () => {
    if (!selectedItem) return;
    try {
      await navigator.clipboard.writeText(selectedItem.content);
      await tauriInvoke("history_mark_used", { id: selectedItem.id });
      await loadItems();
    } catch { showToast("복사에 실패했습니다."); }
  };

  const loadTrash = async () => {
    try {
      const rows = await tauriInvoke<TrashItem[]>("trash_list");
      setTrashItems(Array.isArray(rows) ? rows : []);
    } catch { showToast("휴지통을 불러오지 못했습니다."); }
  };

  const toggleTrashView = async () => {
    const next = !showTrash;
    setShowTrash(next);
    if (next) await loadTrash();
  };

  const doRestore = async (deletedId: number) => {
    try {
      await tauriInvoke("history_restore", { deleted_id: deletedId });
      await loadTrash();
    } catch { showToast("복원에 실패했습니다."); }
  };

  const doPermanentDelete = async (deletedId: number) => {
    if (!window.confirm("영구 삭제할까요? 되돌릴 수 없습니다.")) return;
    try {
      await tauriInvoke("history_delete_permanent", { deleted_id: deletedId });
      await loadTrash();
    } catch { showToast("영구 삭제에 실패했습니다."); }
  };

  const doPurgeTrash = async () => {
    try {
      const n = await tauriInvoke<number>("trash_purge_expired");
      showToast(typeof n === "number" ? `만료된 ${n}건을 정리했습니다.` : "정리했습니다.");
      await loadTrash();
    } catch { showToast("정리에 실패했습니다."); }
  };

  const openPalette = async () => {
    if (!selectedItem) return;
    try {
      const acts = await tauriInvoke<PaletteAction[]>("palette_actions");
      if (Array.isArray(acts) && acts.length > 0) {
        setPaletteActions(acts);
        setPaletteActionId(acts[0].id);
      }
      setPaletteResult(null);
      setPaletteOpen(true);
    } catch { showToast("작업 목록을 불러오지 못했습니다."); }
  };

  const runPalette = async () => {
    if (!selectedItem || !paletteActionId) return;
    try {
      const out = await tauriInvoke<string>("palette_execute", { item_id: selectedItem.id, action_id: paletteActionId });
      setPaletteResult(typeof out === "string" ? out : "완료");
      await loadItems();
    } catch { showToast("작업 실행에 실패했습니다."); }
  };

  const doExport = async (kind: string) => {
    try {
      if (kind === "json") downloadTextFile("smartclipboard.json", await tauriInvoke<string>("export_json"), "application/json");
      else if (kind === "csv") downloadTextFile("smartclipboard.csv", await tauriInvoke<string>("export_csv"), "text/csv");
      else downloadTextFile("smartclipboard.md", await tauriInvoke<string>("export_markdown"), "text/markdown");
    } catch { showToast("내보내기에 실패했습니다."); }
  };

  const doImportFile = async (file: File, kind: "json" | "csv") => {
    try {
      const text = await file.text();
      const res = await tauriInvoke<[number, number]>(kind === "json" ? "import_json" : "import_csv", { payload: text });
      showToast(Array.isArray(res) ? `가져오기 완료: ${res[0]}건` : "가져오기 완료");
      await refreshAfterWrite();
    } catch { showToast("가져오기에 실패했습니다."); }
  };

  const togglePrivacy = async () => {
    try {
      const next = await tauriInvoke<boolean>("privacy_set", { enabled: !privacy });
      if (typeof next === "boolean") setPrivacy(next);
    } catch { showToast("프라이버시 전환에 실패했습니다."); }
  };

  const togglePaused = async () => {
    try {
      const next = await tauriInvoke<boolean>("monitoring_set", { enabled: paused });
      if (typeof next === "boolean") setPaused(!next);
    } catch { showToast("모니터링 전환에 실패했습니다."); }
  };

  const doCollectionAdd = async () => {
    const name = newCollection.trim();
    if (!name) return;
    try {
      await tauriInvoke("collection_add", { name, icon: "📁", color: "#6366f1" });
      setNewCollection("");
      await refreshAfterWrite();
    } catch { showToast("컬렉션 추가에 실패했습니다."); }
  };

  const doCollectionDelete = async () => {
    if (activeCollectionId === null) return;
    if (!window.confirm("컬렉션을 삭제할까요? 소속 항목은 유지됩니다.")) return;
    try {
      await tauriInvoke("collection_delete", { id: activeCollectionId });
      setActiveCollectionId(null);
      await refreshAfterWrite();
    } catch { showToast("컬렉션 삭제에 실패했습니다."); }
  };

  const refreshVault = async (unlocked: boolean) => {
    try {
      const has = await tauriInvoke<boolean>("vault_status");
      if (typeof has === "boolean") setVaultHasPassword(has);
      if (unlocked) {
        const rows = await tauriInvoke<VaultItem[]>("vault_list");
        if (Array.isArray(rows)) setVaultItems(rows);
      }
    } catch { /* noop */ }
  };

  const doVaultOpen = async () => {
    if (!vaultPassword) { showToast("비밀번호를 입력하세요."); return; }
    try {
      if (!vaultHasPassword) {
        await tauriInvoke("vault_setup", { password: vaultPassword });
      }
      const ok = await tauriInvoke<boolean>("vault_unlock", { password: vaultPassword });
      if (ok === true) {
        setVaultUnlocked(true);
        setVaultPassword("");
        await refreshVault(true);
      } else {
        showToast("비밀번호가 일치하지 않습니다.");
      }
    } catch { showToast("보관함 열기에 실패했습니다."); }
  };

  const doVaultLock = async () => {
    try { await tauriInvoke("vault_lock"); } catch { /* noop */ }
    setVaultUnlocked(false);
    setVaultItems([]);
  };

  const doVaultAdd = async () => {
    if (!vaultLabel.trim() || !vaultSecret) { showToast("이름과 비밀을 입력하세요."); return; }
    try {
      await tauriInvoke("vault_add", { label: vaultLabel.trim(), secret: vaultSecret });
      setVaultLabel("");
      setVaultSecret("");
      await refreshVault(true);
    } catch { showToast("비밀 추가에 실패했습니다."); }
  };

  const doVaultReveal = async (id: number) => {
    try {
      await tauriInvoke("vault_reveal", { id });
      showToast("클립보드에 복사했습니다. 30초 뒤 자동 삭제됩니다.");
    } catch { showToast("복호화에 실패했습니다."); }
  };

  const doVaultDelete = async (id: number) => {
    if (!window.confirm("이 비밀을 삭제할까요?")) return;
    try {
      await tauriInvoke("vault_delete", { id });
      await refreshVault(true);
    } catch { showToast("비밀 삭제에 실패했습니다."); }
  };

  const doVaultChangePassword = async () => {
    if (!vaultPassword || !vaultNewPassword) { showToast("현재·새 비밀번호를 입력하세요."); return; }
    try {
      await tauriInvoke("vault_change_password", { current_password: vaultPassword, new_password: vaultNewPassword });
      setVaultPassword("");
      setVaultNewPassword("");
      showToast("마스터 비밀번호를 변경했습니다.");
    } catch { showToast("비밀번호 변경에 실패했습니다."); }
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

        {/* Capture Status */}
        <div className="px-2.5 py-1.5 rounded bg-theme-bg border border-theme-border text-xs flex flex-col gap-1.5">
          <div className="flex items-center gap-1.5 font-medium">
            <span className={`inline-block w-2 h-2 rounded-full ${privacy || paused ? "bg-red-400" : "bg-emerald-400 animate-pulse"}`}></span>
            <span className="text-theme-text">{privacy ? "프라이버시 모드" : paused ? "모니터링 일시정지" : "수집 중"}</span>
          </div>
          <div className="flex gap-1">
            <button onClick={togglePrivacy} className="flex-1 px-2 py-1 rounded bg-theme-card hover:bg-theme-hover border border-theme-border text-theme-muted">🔒 프라이버시</button>
            <button onClick={togglePaused} className="flex-1 px-2 py-1 rounded bg-theme-card hover:bg-theme-hover border border-theme-border text-theme-muted">⏸ 일시정지</button>
          </div>
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

        {/* Collection Add */}
        <div className="flex gap-1 text-xs">
          <input value={newCollection} onChange={(e) => setNewCollection(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter") void doCollectionAdd(); }} placeholder="새 컬렉션" className="flex-1 min-w-0 bg-theme-bg border border-theme-border rounded px-2 py-1.5 text-theme-text placeholder:text-theme-muted/60 outline-none focus:border-theme-accent" />
          <button onClick={() => void doCollectionAdd()} className="px-2.5 py-1.5 rounded bg-theme-card hover:bg-theme-hover border border-theme-border text-theme-text">＋</button>
        </div>

        {/* Theme Selector */}
        <div className="mt-auto pt-3 border-t border-theme-border flex items-center justify-between text-xs px-1">
          <span className="text-theme-muted">테마</span>
          <select
            value={theme}
            onChange={(e) => {
              setTheme(e.target.value);
              tauriInvoke("settings_set", { key: "theme", value: e.target.value }).catch(() => {});
            }}
            className="bg-theme-bg border border-theme-border rounded px-2 py-1 text-xs text-theme-text outline-none focus:border-theme-accent"
          >
            <option value="Dark">Dark</option>
            <option value="Light">Light</option>
            <option value="Ocean">Ocean</option>
            <option value="Purple">Purple</option>
            <option value="Midnight">Midnight</option>
          </select>
        </div>
        {/* App Update */}
        <div className="mt-2 pt-2 border-t border-theme-border flex flex-col gap-1 text-xs px-1">
          <button
            onClick={() => void doCheckUpdate()}
            disabled={updateBusy}
            className="px-2.5 py-1.5 rounded bg-theme-card hover:bg-theme-hover border border-theme-border text-theme-text text-left disabled:opacity-40"
          >
            🔄 업데이트 확인
          </button>
          {updateMsg && <span className="text-theme-muted">{updateMsg}</span>}
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

          {/* Action Toolbar */}
          <div className="flex gap-1 overflow-x-auto pb-1 text-xs">
            <button onClick={openPalette} disabled={!selectedItem} className="px-2.5 py-1 rounded-md whitespace-nowrap bg-theme-card hover:bg-theme-hover border border-theme-border text-theme-text disabled:opacity-40">⚡ 작업 실행 (Alt+A)</button>
            <button onClick={toggleTrashView} className="px-2.5 py-1 rounded-md whitespace-nowrap bg-theme-card hover:bg-theme-hover border border-theme-border text-theme-text">🗑 휴지통</button>
            <button onClick={() => setVaultOpen(true)} className="px-2.5 py-1 rounded-md whitespace-nowrap bg-theme-card hover:bg-theme-hover border border-theme-border text-theme-text">🔒 보안 보관함</button>
            {activeCollectionId !== null && (<button onClick={doCollectionDelete} className="px-2.5 py-1 rounded-md whitespace-nowrap bg-theme-card hover:bg-theme-hover border border-theme-border text-red-400">📁 현 컬렉션 삭제</button>)}
            <button onClick={() => doExport("json")} className="px-2.5 py-1 rounded-md whitespace-nowrap bg-theme-card hover:bg-theme-hover border border-theme-border text-theme-text">📤 JSON</button>
            <button onClick={() => doExport("csv")} className="px-2.5 py-1 rounded-md whitespace-nowrap bg-theme-card hover:bg-theme-hover border border-theme-border text-theme-text">📤 CSV</button>
            <button onClick={() => doExport("md")} className="px-2.5 py-1 rounded-md whitespace-nowrap bg-theme-card hover:bg-theme-hover border border-theme-border text-theme-text">📤 MD</button>
            <button onClick={() => jsonInput.current?.click()} className="px-2.5 py-1 rounded-md whitespace-nowrap bg-theme-card hover:bg-theme-hover border border-theme-border text-theme-text">📥 JSON 가져오기</button>
            <button onClick={() => csvInput.current?.click()} className="px-2.5 py-1 rounded-md whitespace-nowrap bg-theme-card hover:bg-theme-hover border border-theme-border text-theme-text">📥 CSV 가져오기</button>
          </div>

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
                <div className="flex gap-1.5 text-xs">
                  <button onClick={doPin} className="px-2.5 py-1.5 rounded-md bg-theme-card hover:bg-theme-hover border border-theme-border">{selectedItem.pinned ? "📌 고정 해제" : "📌 고정"}</button>
                  <button onClick={doBookmark} className="px-2.5 py-1.5 rounded-md bg-theme-card hover:bg-theme-hover border border-theme-border">{selectedItem.bookmark ? "⭐ 북마크 해제" : "⭐ 북마크"}</button>
                  <button onClick={doCopy} className="px-2.5 py-1.5 rounded-md bg-theme-card hover:bg-theme-hover border border-theme-border">📋 복사</button>
                  {(selectedItem.type === "TEXT" || selectedItem.type === "LINK") && (
                    <button onClick={doFetchTitle} className="px-2.5 py-1.5 rounded-md bg-theme-card hover:bg-theme-hover border border-theme-border">🌐 제목 가져오기</button>
                  )}
                  <button onClick={doDelete} className="px-2.5 py-1.5 rounded-md bg-theme-card hover:bg-theme-hover border border-theme-border text-red-400">🗑 삭제</button>
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

      {/* Toast */}
      {toast && (
        <div className="fixed bottom-4 left-1/2 -translate-x-1/2 px-4 py-2 rounded-lg bg-theme-card border border-theme-border text-sm text-theme-text shadow-lg z-50">
          {toast}
        </div>
      )}

      {/* Palette Panel */}
      {paletteOpen && selectedItem && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50" onClick={() => setPaletteOpen(false)}>
          <div className="w-[480px] max-w-[90vw] bg-theme-card border border-theme-border rounded-xl p-4 flex flex-col gap-3" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-semibold text-theme-text">⚡ 작업 실행</h3>
              <button onClick={() => setPaletteOpen(false)} className="text-theme-muted hover:text-theme-text">✕</button>
            </div>
            <p className="text-xs text-theme-muted truncate">대상: {selectedItem.content.slice(0, 80)}</p>
            <select value={paletteActionId} onChange={(e) => setPaletteActionId(e.target.value)} className="bg-theme-bg border border-theme-border rounded px-2 py-2 text-sm text-theme-text outline-none">
              {paletteActions.map((a) => (<option key={a.id} value={a.id}>{a.title} — {a.description}</option>))}
            </select>
            <button onClick={() => void runPalette()} className="px-4 py-2 bg-theme-accent text-white rounded-lg text-sm font-medium hover:opacity-90">실행</button>
            {paletteResult !== null && (<pre className="text-xs font-mono whitespace-pre-wrap bg-theme-bg border border-theme-border rounded p-2 max-h-48 overflow-auto text-theme-text">{paletteResult}</pre>)}
          </div>
        </div>
      )}

      {/* Trash Panel */}
      {showTrash && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50" onClick={() => void toggleTrashView()}>
          <div className="w-[560px] max-w-[92vw] max-h-[80vh] bg-theme-card border border-theme-border rounded-xl p-4 flex flex-col gap-3" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-semibold text-theme-text">🗑 휴지통 (7일 보관)</h3>
              <div className="flex gap-1.5">
                <button onClick={() => void doPurgeTrash()} className="px-2.5 py-1 rounded text-xs bg-theme-bg hover:bg-theme-hover border border-theme-border text-theme-text">만료 정리</button>
                <button onClick={() => void toggleTrashView()} className="px-2.5 py-1 rounded text-xs bg-theme-bg hover:bg-theme-hover border border-theme-border text-theme-text">닫기</button>
              </div>
            </div>
            <div className="overflow-y-auto flex flex-col gap-2">
              {trashItems.length === 0 && (<div className="text-sm text-theme-muted text-center py-6">휴지통이 비어 있습니다.</div>)}
              {trashItems.map((t) => (
                <div key={t.id} className="p-2.5 rounded bg-theme-bg border border-theme-border flex flex-col gap-1.5">
                  <p className="text-xs font-mono break-all text-theme-text/90 line-clamp-2">{t.content || "(내용 없음)"}</p>
                  <div className="flex items-center justify-between text-[11px] text-theme-muted">
                    <span>{t.type} · 삭제: {t.deleted_at}</span>
                    <span className="flex gap-1.5">
                      <button onClick={() => void doRestore(t.id)} className="px-2 py-1 rounded bg-theme-card hover:bg-theme-hover border border-theme-border text-theme-text">복원</button>
                      <button onClick={() => void doPermanentDelete(t.id)} className="px-2 py-1 rounded bg-theme-card hover:bg-theme-hover border border-theme-border text-red-400">영구 삭제</button>
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Vault Panel */}
      {vaultOpen && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50" onClick={() => setVaultOpen(false)}>
          <div className="w-[480px] max-w-[90vw] max-h-[80vh] overflow-y-auto bg-theme-card border border-theme-border rounded-xl p-4 flex flex-col gap-3" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-semibold text-theme-text">🔒 보안 보관함</h3>
              <button onClick={() => setVaultOpen(false)} className="text-theme-muted hover:text-theme-text">✕</button>
            </div>
            {!vaultUnlocked ? (
              <div className="flex flex-col gap-2">
                <input type="password" value={vaultPassword} onChange={(e) => setVaultPassword(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter") void doVaultOpen(); }} placeholder={vaultHasPassword ? "마스터 비밀번호" : "새 마스터 비밀번호 (8자 이상)"} className="bg-theme-bg border border-theme-border rounded px-2 py-2 text-sm text-theme-text outline-none" />
                <button onClick={() => void doVaultOpen()} className="px-4 py-2 bg-theme-accent text-white rounded-lg text-sm font-medium hover:opacity-90">{vaultHasPassword ? "잠금 해제" : "보관함 만들기"}</button>
              </div>
            ) : (
              <div className="flex flex-col gap-2">
                <div className="flex gap-1.5">
                  <input value={vaultLabel} onChange={(e) => setVaultLabel(e.target.value)} placeholder="이름" className="flex-1 min-w-0 bg-theme-bg border border-theme-border rounded px-2 py-1.5 text-xs text-theme-text outline-none" />
                  <input value={vaultSecret} onChange={(e) => setVaultSecret(e.target.value)} placeholder="비밀" className="flex-1 min-w-0 bg-theme-bg border border-theme-border rounded px-2 py-1.5 text-xs text-theme-text outline-none" />
                  <button onClick={() => void doVaultAdd()} className="px-2.5 py-1.5 rounded bg-theme-accent text-white text-xs">추가</button>
                </div>
                {vaultItems.map((v) => (
                  <div key={v.id} className="p-2 rounded bg-theme-bg border border-theme-border flex items-center justify-between text-xs">
                    <span className="text-theme-text font-medium truncate">{v.label}</span>
                    <span className="flex gap-1.5 shrink-0">
                      <button onClick={() => void doVaultReveal(v.id)} className="px-2 py-1 rounded bg-theme-card hover:bg-theme-hover border border-theme-border text-theme-text">복사</button>
                      <button onClick={() => void doVaultDelete(v.id)} className="px-2 py-1 rounded bg-theme-card hover:bg-theme-hover border border-theme-border text-red-400">삭제</button>
                    </span>
                  </div>
                ))}
                <div className="flex gap-1.5 mt-1">
                  <input type="password" value={vaultPassword} onChange={(e) => setVaultPassword(e.target.value)} placeholder="현재 비밀번호" className="flex-1 min-w-0 bg-theme-bg border border-theme-border rounded px-2 py-1.5 text-xs text-theme-text outline-none" />
                  <input type="password" value={vaultNewPassword} onChange={(e) => setVaultNewPassword(e.target.value)} placeholder="새 비밀번호" className="flex-1 min-w-0 bg-theme-bg border border-theme-border rounded px-2 py-1.5 text-xs text-theme-text outline-none" />
                  <button onClick={() => void doVaultChangePassword()} className="px-2.5 py-1.5 rounded bg-theme-card hover:bg-theme-hover border border-theme-border text-xs text-theme-text">변경</button>
                  <button onClick={() => void doVaultLock()} className="px-2.5 py-1.5 rounded bg-theme-card hover:bg-theme-hover border border-theme-border text-xs text-theme-text">잠금</button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      <input ref={jsonInput} type="file" accept=".json,application/json" className="hidden" onChange={(e) => { const f = e.target.files?.[0]; if (f) void doImportFile(f, "json"); e.target.value = ""; }} />
      <input ref={csvInput} type="file" accept=".csv,text/csv" className="hidden" onChange={(e) => { const f = e.target.files?.[0]; if (f) void doImportFile(f, "csv"); e.target.value = ""; }} />
    </div>
  );
}

import { useEffect, useRef, useState, type ReactNode } from "react";
import { Check, EyeOff, Lock, RefreshCw, Trash2 } from "lucide-react";
import type { Collection } from "../types";

export const THEMES = ["Dark", "Light", "Ocean", "Purple", "Midnight"];

interface Props {
  onClose: () => void;
  privacy: boolean;
  onTogglePrivacy: () => void;
  theme: string;
  onTheme: (theme: string) => void;
  onTrash: () => void;
  onVault: () => void;
  activeCollection: Collection | null;
  onAddCollection: (name: string) => void;
  onDeleteCollection: () => void;
  onExport: (kind: "json" | "csv" | "md") => void;
  onImport: (kind: "json" | "csv") => void;
  updateBusy: boolean;
  updateMsg: string | null;
  onCheckUpdate: () => void;
}

function Row({ onClick, icon, children, disabled }: { onClick: () => void; icon?: ReactNode; children: ReactNode; disabled?: boolean }) {
  return (
    <button onClick={onClick} disabled={disabled} className="w-full flex items-center gap-2 px-3 h-8 text-xs text-left hover:bg-theme-hover disabled:opacity-50">
      <span className="w-4 flex justify-center text-theme-muted">{icon}</span>
      {children}
    </button>
  );
}

const Label = ({ children }: { children: ReactNode }) => (
  <span className="w-14 shrink-0 text-xs text-theme-muted">{children}</span>
);

export default function AppMenu(props: Props) {
  const ref = useRef<HTMLDivElement>(null);
  const [newCollection, setNewCollection] = useState("");
  const { onClose } = props;

  useEffect(() => {
    const onDown = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) onClose();
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.stopPropagation();
        onClose();
      }
    };
    window.addEventListener("mousedown", onDown);
    window.addEventListener("keydown", onKey, true);
    return () => {
      window.removeEventListener("mousedown", onDown);
      window.removeEventListener("keydown", onKey, true);
    };
  }, [onClose]);

  const addCollection = () => {
    const name = newCollection.trim();
    if (!name) return;
    props.onAddCollection(name);
    setNewCollection("");
  };

  // Actions that open a dialog or a file picker dismiss the menu.
  const closing = (fn: () => void) => () => {
    onClose();
    fn();
  };

  return (
    <div ref={ref} className="absolute right-2 top-11 z-30 w-64 py-1 bg-theme-card border border-theme-border rounded-lg shadow-xl">
      <Row onClick={closing(props.onTrash)} icon={<Trash2 size={14} />}>휴지통</Row>
      <Row onClick={closing(props.onVault)} icon={<Lock size={14} />}>보안 보관함</Row>
      <Row onClick={props.onTogglePrivacy} icon={<EyeOff size={14} />}>
        <span className="flex-1">프라이버시 모드</span>
        {props.privacy && <Check size={14} className="text-theme-accent" />}
      </Row>

      <div className="my-1 border-t border-theme-border" />

      <div className="px-3 py-1 flex flex-col gap-1.5">
        <div className="flex items-center">
          <Label>테마</Label>
          <select value={props.theme} onChange={(e) => props.onTheme(e.target.value)} className="field flex-1 min-w-0">
            {THEMES.map((t) => (
              <option key={t} value={t}>{t}</option>
            ))}
          </select>
        </div>
        <div className="flex items-center">
          <Label>컬렉션</Label>
          <input
            value={newCollection}
            onChange={(e) => setNewCollection(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") addCollection();
            }}
            placeholder="새 컬렉션 이름 + Enter"
            className="field flex-1 min-w-0"
          />
        </div>
        {props.activeCollection && (
          <button onClick={closing(props.onDeleteCollection)} className="text-xs text-left text-red-400 hover:underline ml-14 truncate">
            “{props.activeCollection.name}” 삭제
          </button>
        )}
        <div className="flex items-center gap-1">
          <Label>내보내기</Label>
          <button onClick={closing(() => props.onExport("json"))} className="btn flex-1">JSON</button>
          <button onClick={closing(() => props.onExport("csv"))} className="btn flex-1">CSV</button>
          <button onClick={closing(() => props.onExport("md"))} className="btn flex-1">MD</button>
        </div>
        <div className="flex items-center gap-1">
          <Label>가져오기</Label>
          <button onClick={closing(() => props.onImport("json"))} className="btn flex-1">JSON</button>
          <button onClick={closing(() => props.onImport("csv"))} className="btn flex-1">CSV</button>
        </div>
      </div>

      <div className="my-1 border-t border-theme-border" />

      <Row onClick={props.onCheckUpdate} disabled={props.updateBusy} icon={<RefreshCw size={14} className={props.updateBusy ? "animate-spin" : ""} />}>
        {props.updateMsg ?? "업데이트 확인"}
      </Row>
    </div>
  );
}

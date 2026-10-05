import { useEffect, useState } from "react";
import type { HistoryItem } from "../types";
import { errorText, tauriInvoke } from "../lib/tauri";
import Modal from "./Modal";

interface PaletteAction {
  id: string;
  title: string;
  description: string;
  category: string;
  effect: "replace" | "copy" | "view";
}

const EFFECT_NOTE: Record<PaletteAction["effect"], string> = {
  replace: "항목과 클립보드에 반영했습니다.",
  copy: "결과를 클립보드에 복사했습니다. 원본 항목은 그대로입니다.",
  view: "",
};

interface Props {
  item: HistoryItem;
  onClose: () => void;
  onChanged: () => void;
}

export default function PaletteDialog({ item, onClose, onChanged }: Props) {
  const [actions, setActions] = useState<PaletteAction[]>([]);
  const [result, setResult] = useState<{ text: string; note: string; error?: boolean } | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    tauriInvoke<PaletteAction[]>("palette_actions")
      .then((acts) => setActions(Array.isArray(acts) ? acts : []))
      .catch(() => setResult({ text: "작업 목록을 불러오지 못했습니다.", note: "", error: true }));
  }, []);

  const run = async (action: PaletteAction) => {
    if (busy) return;
    setBusy(true);
    try {
      const out = await tauriInvoke<string>("palette_execute", { itemId: item.id, actionId: action.id });
      setResult({ text: typeof out === "string" ? out : "", note: EFFECT_NOTE[action.effect] ?? "" });
      if (action.effect === "replace") onChanged();
    } catch (err) {
      setResult({ text: errorText(err) || "작업 실행에 실패했습니다.", note: "", error: true });
    } finally {
      setBusy(false);
    }
  };

  return (
    <Modal title="변환" onClose={onClose}>
      <p className="text-xs text-theme-muted truncate">{item.content.trim().slice(0, 80)}</p>
      <div className="grid grid-cols-2 gap-1">
        {actions.map((a) => (
          <button
            key={a.id}
            onClick={() => void run(a)}
            disabled={busy}
            title={a.description}
            className="px-2.5 py-1.5 rounded text-xs text-left bg-theme-bg hover:bg-theme-hover border border-theme-border disabled:opacity-50"
          >
            {a.title}
          </button>
        ))}
      </div>
      {result && (
        <>
          <pre className={`text-xs font-mono whitespace-pre-wrap break-words bg-theme-bg border border-theme-border rounded p-2 max-h-40 overflow-auto select-text ${result.error ? "text-red-400" : ""}`}>
            {result.text}
          </pre>
          {result.note && <p className="text-[11px] text-theme-muted">{result.note}</p>}
        </>
      )}
    </Modal>
  );
}

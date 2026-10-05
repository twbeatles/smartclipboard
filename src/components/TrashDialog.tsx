import { useEffect, useState } from "react";
import { RotateCcw, Trash2 } from "lucide-react";
import type { TrashItem } from "../types";
import { relativeTime } from "../lib/format";
import { tauriInvoke } from "../lib/tauri";
import Modal from "./Modal";

interface Props {
  onClose: () => void;
  onRestored: () => void;
  showToast: (msg: string) => void;
}

export default function TrashDialog({ onClose, onRestored, showToast }: Props) {
  const [rows, setRows] = useState<TrashItem[]>([]);

  const load = async () => {
    try {
      const res = await tauriInvoke<TrashItem[]>("trash_list");
      setRows(Array.isArray(res) ? res : []);
    } catch {
      showToast("휴지통을 불러오지 못했습니다.");
    }
  };

  useEffect(() => {
    void load();
  }, []);

  const restore = async (deletedId: number) => {
    try {
      await tauriInvoke("history_restore", { deletedId });
      await load();
      onRestored();
    } catch {
      showToast("복원에 실패했습니다.");
    }
  };

  const remove = async (deletedId: number) => {
    if (!window.confirm("영구 삭제할까요? 되돌릴 수 없습니다.")) return;
    try {
      await tauriInvoke("history_delete_permanent", { deletedId });
      await load();
    } catch {
      showToast("영구 삭제에 실패했습니다.");
    }
  };

  return (
    <Modal title="휴지통" onClose={onClose} footer={<span className="text-theme-muted">삭제 후 7일이 지나면 자동으로 비워집니다.</span>}>
      {rows.length === 0 && <div className="text-xs text-theme-muted text-center py-6">휴지통이 비어 있습니다.</div>}
      {rows.map((t) => (
        <div key={t.id} className="flex items-center gap-2 h-9 pl-2.5 pr-1 rounded bg-theme-bg border border-theme-border">
          <span className="flex-1 min-w-0 truncate text-xs">{t.content.trim().replace(/\s+/g, " ") || "(내용 없음)"}</span>
          {t.deleted_at && <span className="text-[11px] text-theme-muted shrink-0">{relativeTime(t.deleted_at)}</span>}
          <button onClick={() => void restore(t.id)} className="icon-btn" title="복원">
            <RotateCcw size={13} />
          </button>
          <button onClick={() => void remove(t.id)} className="icon-btn hover:text-red-400" title="영구 삭제">
            <Trash2 size={13} />
          </button>
        </div>
      ))}
    </Modal>
  );
}

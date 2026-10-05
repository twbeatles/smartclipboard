import { useEffect, useState } from "react";
import { Copy, Trash2 } from "lucide-react";
import { errorText, tauriInvoke } from "../lib/tauri";
import Modal from "./Modal";

interface VaultItem {
  id: number;
  label: string;
  created_at: string;
}

interface Props {
  onClose: () => void;
  showToast: (msg: string) => void;
}

// The vault is unlocked only while this dialog is open: closing it locks the
// backend again, so the UI can never show a stale "unlocked" state.
export default function VaultDialog({ onClose, showToast }: Props) {
  const [hasPassword, setHasPassword] = useState<boolean | null>(null);
  const [unlocked, setUnlocked] = useState(false);
  const [items, setItems] = useState<VaultItem[]>([]);
  const [password, setPassword] = useState("");
  const [label, setLabel] = useState("");
  const [secret, setSecret] = useState("");
  const [changing, setChanging] = useState(false);
  const [newPassword, setNewPassword] = useState("");

  useEffect(() => {
    tauriInvoke<boolean>("vault_status")
      .then((has) => setHasPassword(has === true))
      .catch(() => setHasPassword(false));
    return () => {
      tauriInvoke("vault_lock").catch(() => {});
    };
  }, []);

  const loadItems = async () => {
    const rows = await tauriInvoke<VaultItem[]>("vault_list");
    setItems(Array.isArray(rows) ? rows : []);
  };

  const relock = () => {
    setUnlocked(false);
    setItems([]);
    setChanging(false);
  };

  const open = async () => {
    if (!password) return;
    try {
      if (!hasPassword) {
        if (password.length < 8) {
          showToast("마스터 비밀번호는 8자 이상이어야 합니다.");
          return;
        }
        await tauriInvoke("vault_setup", { password });
        setHasPassword(true);
      }
      const ok = await tauriInvoke<boolean>("vault_unlock", { password });
      if (ok === true) {
        setUnlocked(true);
        setPassword("");
        await loadItems();
      } else {
        showToast("비밀번호가 일치하지 않습니다.");
      }
    } catch (err) {
      showToast(errorText(err) || "보관함 열기에 실패했습니다.");
    }
  };

  const add = async () => {
    if (!label.trim() || !secret) {
      showToast("이름과 내용을 입력하세요.");
      return;
    }
    try {
      await tauriInvoke("vault_add", { label: label.trim(), secret });
      setLabel("");
      setSecret("");
      await loadItems();
    } catch {
      showToast("저장에 실패했습니다. 보관함을 다시 열어 주세요.");
      relock();
    }
  };

  const reveal = async (id: number) => {
    try {
      await tauriInvoke("vault_reveal", { id });
      showToast("복사했습니다. 30초 뒤 클립보드에서 지워집니다.");
    } catch {
      showToast("복호화에 실패했습니다. 보관함을 다시 열어 주세요.");
      relock();
    }
  };

  const remove = async (id: number) => {
    if (!window.confirm("이 항목을 삭제할까요?")) return;
    try {
      await tauriInvoke("vault_delete", { id });
      await loadItems();
    } catch {
      showToast("삭제에 실패했습니다.");
    }
  };

  const changePassword = async () => {
    if (!password || newPassword.length < 8) {
      showToast("현재 비밀번호와 8자 이상의 새 비밀번호를 입력하세요.");
      return;
    }
    try {
      await tauriInvoke("vault_change_password", { currentPassword: password, newPassword });
      setPassword("");
      setNewPassword("");
      setChanging(false);
      showToast("마스터 비밀번호를 변경했습니다.");
    } catch {
      showToast("비밀번호 변경에 실패했습니다.");
    }
  };

  if (!unlocked) {
    return (
      <Modal title="보안 보관함" onClose={onClose}>
        <input
          autoFocus
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") void open();
          }}
          placeholder={hasPassword ? "마스터 비밀번호" : "새 마스터 비밀번호 (8자 이상)"}
          className="field"
        />
        <button onClick={() => void open()} disabled={hasPassword === null} className="btn-primary justify-center">
          {hasPassword ? "잠금 해제" : "보관함 만들기"}
        </button>
      </Modal>
    );
  }

  return (
    <Modal
      title="보안 보관함"
      onClose={onClose}
      footer={
        changing ? (
          <div className="flex gap-1.5">
            <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} placeholder="현재 비밀번호" className="field flex-1 min-w-0" />
            <input type="password" value={newPassword} onChange={(e) => setNewPassword(e.target.value)} placeholder="새 비밀번호" className="field flex-1 min-w-0" />
            <button onClick={() => void changePassword()} className="btn">변경</button>
            <button onClick={() => { setChanging(false); setPassword(""); setNewPassword(""); }} className="btn">취소</button>
          </div>
        ) : (
          <div className="flex justify-between items-center">
            <button onClick={() => setChanging(true)} className="text-theme-muted hover:text-theme-text">비밀번호 변경</button>
            <span className="text-theme-muted">창을 닫으면 다시 잠깁니다.</span>
          </div>
        )
      }
    >
      <div className="flex gap-1.5">
        <input value={label} onChange={(e) => setLabel(e.target.value)} placeholder="이름" className="field flex-1 min-w-0" />
        <input
          type="password"
          value={secret}
          onChange={(e) => setSecret(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") void add();
          }}
          placeholder="내용"
          className="field flex-1 min-w-0"
        />
        <button onClick={() => void add()} className="btn-primary">추가</button>
      </div>
      {items.length === 0 && <div className="text-xs text-theme-muted text-center py-4">저장된 항목이 없습니다.</div>}
      {items.map((v) => (
        <div key={v.id} className="flex items-center gap-2 h-9 pl-2.5 pr-1 rounded bg-theme-bg border border-theme-border">
          <span className="flex-1 min-w-0 truncate text-xs font-medium">{v.label}</span>
          <button onClick={() => void reveal(v.id)} className="icon-btn" title="복사 (30초 뒤 자동 삭제)">
            <Copy size={13} />
          </button>
          <button onClick={() => void remove(v.id)} className="icon-btn hover:text-red-400" title="삭제">
            <Trash2 size={13} />
          </button>
        </div>
      ))}
    </Modal>
  );
}

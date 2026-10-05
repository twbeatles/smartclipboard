import { useEffect, type ReactNode } from "react";
import { X } from "lucide-react";

interface Props {
  title: string;
  onClose: () => void;
  children: ReactNode;
  footer?: ReactNode;
}

export default function Modal({ title, onClose, children, footer }: Props) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.stopPropagation();
        onClose();
      }
    };
    window.addEventListener("keydown", onKey, true);
    return () => window.removeEventListener("keydown", onKey, true);
  }, [onClose]);

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-40" onMouseDown={onClose}>
      <div
        role="dialog"
        aria-label={title}
        className="w-[440px] max-w-[92vw] max-h-[80vh] bg-theme-card border border-theme-border rounded-lg shadow-xl flex flex-col"
        onMouseDown={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between pl-4 pr-2 py-2 border-b border-theme-border">
          <h3 className="text-sm font-semibold">{title}</h3>
          <button onClick={onClose} className="icon-btn" title="닫기 (Esc)">
            <X size={15} />
          </button>
        </div>
        <div className="p-3 overflow-y-auto flex flex-col gap-2 min-h-0">{children}</div>
        {footer && <div className="px-3 py-2 border-t border-theme-border text-xs">{footer}</div>}
      </div>
    </div>
  );
}

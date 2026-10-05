import { Code, Image as ImageIcon, Link2, Palette, Paperclip, Type, type LucideIcon } from "lucide-react";
import type { HistoryItem, ItemType } from "../types";

export const TYPE_META: Record<ItemType, { label: string; Icon: LucideIcon }> = {
  TEXT: { label: "텍스트", Icon: Type },
  LINK: { label: "링크", Icon: Link2 },
  IMAGE: { label: "이미지", Icon: ImageIcon },
  CODE: { label: "코드", Icon: Code },
  COLOR: { label: "색상", Icon: Palette },
  FILE: { label: "파일", Icon: Paperclip },
};

// Labels double as the backend `type_filter` values.
export const TYPE_FILTERS = ["전체", "텍스트", "링크", "이미지", "코드", "색상", "파일"] as const;

const COLOR_RE = /^(#[0-9a-f]{3,8}|rgba?\([^)]*\)|hsla?\([^)]*\))$/i;

export function TypeIcon({ item, size = 14 }: { item: Pick<HistoryItem, "type" | "content">; size?: number }) {
  if (item.type === "COLOR" && COLOR_RE.test(item.content.trim())) {
    return (
      <span
        className="inline-block rounded-sm border border-theme-border shrink-0"
        style={{ width: size, height: size, background: item.content.trim() }}
      />
    );
  }
  const Icon = (TYPE_META[item.type] ?? TYPE_META.TEXT).Icon;
  return <Icon size={size} className="shrink-0" />;
}

// App timestamps are local "YYYY-MM-DD HH:MM:SS".
export function relativeTime(timestamp: string): string {
  const t = new Date(timestamp.replace(" ", "T")).getTime();
  if (Number.isNaN(t)) return timestamp;
  const diff = Math.floor((Date.now() - t) / 1000);
  if (diff < 60) return "방금";
  if (diff < 3600) return `${Math.floor(diff / 60)}분 전`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}시간 전`;
  if (diff < 86400 * 7) return `${Math.floor(diff / 86400)}일 전`;
  return timestamp.slice(0, 10);
}

// Single-line summary for list rows.
export function summarize(item: HistoryItem): string {
  if (item.type === "IMAGE") return item.content || "이미지";
  if (item.type === "FILE") {
    const names = item.content
      .split("\n")
      .filter(Boolean)
      .map((p) => p.split(/[\\/]/).pop() || p);
    return names.length > 1 ? `${names[0]} 외 ${names.length - 1}개` : names[0] || "(내용 없음)";
  }
  if (item.url_title) return item.url_title;
  return item.content.trim().replace(/\s+/g, " ").slice(0, 200) || "(내용 없음)";
}

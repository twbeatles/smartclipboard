export type ItemType = "TEXT" | "IMAGE" | "LINK" | "CODE" | "COLOR" | "FILE";

export interface HistoryItem {
  id: number;
  content: string;
  type: ItemType;
  timestamp: string;
  pinned: boolean;
  pin_order: number;
  use_count: number;
  bookmark: boolean;
  tags: string;
  note: string;
  url_title: string;
  collection_id: number | null;
  has_image: boolean;
}

export interface HistoryDetail extends HistoryItem {
  image_data_base64: string | null;
  file_path: string;
  file_signature: string;
}

export interface Collection {
  id: number;
  name: string;
  icon: string;
  color: string;
  created_at: string;
}

export interface Snippet {
  id: number;
  name: string;
  content: string;
  shortcut: string | null;
  category: string;
  created_at: string;
}

export interface TrashItem {
  id: number;
  original_id: number;
  content: string;
  type: ItemType;
  deleted_at: string;
  original_timestamp: string;
  tags: string;
}

export interface SettingsMap {
  [key: string]: string;
}

export interface SearchFilter {
  query: string;
  type_filter?: string;
  tag_filter?: string;
  bookmarked?: boolean;
  collection_id?: number | null;
  limit?: number;
}

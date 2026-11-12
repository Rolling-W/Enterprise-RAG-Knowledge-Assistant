// HTTP DTOs shared by the Sprint 4 backend and frontend.
// Keep display models in types.ts; do not add UI fields to these responses.
export type Role =
  | "admin"
  | "staff"
  | "user"
  // Legacy development adapter values retained during migration.
  | "Standard Staff"
  | "Department Manager"
  | "Executive";
export type PermissionLevel = 1 | 2 | 3;
export type DocumentStatus = "processing" | "indexed" | "failed" | "deleting";
export type DocumentAction =
  "read" | "change_permission" | "reindex" | "delete";
export type SearchMode = "hybrid" | "semantic" | "keyword";
export interface UserSummary {
  user_id: string;
  username: string;
  role: Role;
  department?: string;
  clearance?: number;
  permissions?: string[];
}
export interface TokenResponse {
  access_token: string;
  token_type: "bearer";
  expires_in: number;
  user: UserSummary;
}
export interface UploadResponse {
  document_id: string;
  filename: string;
  content_type: string;
  size_bytes: number;
  status: "queued" | DocumentStatus;
  message?: string;
  permission_level?: PermissionLevel;
  creator?: CreatorSummary;
  created_at?: string;
  updated_at?: string;
  available_actions?: DocumentAction[];
}
export interface SearchRequest {
  query: string;
  top_k?: number;
  search_mode?: SearchMode;
  filters?: Record<string, string | number>;
}
export interface CreatorSummary {
  user_id: string;
  display_name: string;
}
export interface DocumentSummary {
  document_id: string;
  filename: string;
  title: string;
  content_type: string;
  size_bytes: number;
  permission_level: PermissionLevel;
  creator: CreatorSummary;
  created_at: string;
  updated_at: string;
  status: DocumentStatus;
  available_actions: DocumentAction[];
}
export interface PaginatedDocuments {
  items: DocumentSummary[];
  page: number;
  page_size: number;
  total: number;
}
export interface DocumentDetail extends DocumentSummary {
  preview?: string;
  page_count?: number;
}
export interface DocumentQuery {
  page?: number;
  page_size?: number;
  sort_by?:
    "created_at" | "updated_at" | "filename" | "permission_level" | "status";
  sort_order?: "asc" | "desc";
  permission_level?: PermissionLevel;
  creator_id?: string;
  status?: DocumentStatus;
  q?: string;
}
export interface Page<T> {
  items: T[];
  page: number;
  page_size: number;
  total: number;
}
export interface SourceLocation {
  page: number | null;
  line_start: number | null;
  line_end: number | null;
}
export interface SearchResult {
  document_id: string;
  chunk_id: string;
  title: string;
  score: number;
  content: string;
  content_type: string;
  department_id?: string;
  clearance_level?: number;
  citation: SourceLocation;
  permission_level?: PermissionLevel;
}
export interface SearchResponse {
  query: string;
  search_mode: SearchMode;
  results: SearchResult[];
  total: number;
  request_id: string;
  elapsed_ms?: number;
}

export interface ScoreTrace {
  bm25_raw: number | null;
  bm25_rank: number | null;
  dense_raw: number | null;
  dense_rank: number | null;
  fusion: number | null;
  rerank: number | null;
  final: number | null;
}
export interface ScoringCandidate {
  document_id: string;
  chunk_id: string;
  permission_level: PermissionLevel;
  scores: ScoreTrace;
  final_rank: number;
}
export interface ScoringDebugResponse {
  query: string;
  search_mode: SearchMode;
  top_k: number;
  candidates: ScoringCandidate[];
  stages: Array<"bm25" | "dense" | "rrf" | "rerank">;
  timings_ms: Record<string, number>;
  request_id: string;
}
export interface ConversationSummary {
  conversation_id: string;
  title: string | null;
  created_at: string;
  updated_at: string;
}
export interface ConversationCitation extends SourceLocation {
  document_id: string;
  chunk_id: string;
  title: string;
  permission_level: PermissionLevel;
  unavailable?: boolean;
}
export interface ConversationMessage {
  message_id: string;
  sequence: number;
  role: "user" | "assistant";
  content: string;
  created_at: string;
  citations: ConversationCitation[];
}
export interface Conversation extends ConversationSummary {
  owner_id: string;
  messages: ConversationMessage[];
}

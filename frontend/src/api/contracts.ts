// HTTP DTOs based on architecture branch 5f4b950 (2026-10-10).
// Keep display models in types.ts; do not add UI fields to these responses.
export type Role = "Standard Staff" | "Department Manager" | "Executive";
export interface UserSummary {
  user_id: string;
  username: string;
  role: Role;
  department: string;
  clearance: number;
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
  status: "queued";
  message: string;
}
export interface SearchRequest {
  query: string;
  top_k?: number;
  search_mode?: "hybrid" | "semantic" | "keyword";
  filters?: Record<string, string>;
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
  department_id: string;
  clearance_level: number;
  citation: SourceLocation;
}
export interface SearchResponse {
  query: string;
  search_mode: "hybrid" | "semantic" | "keyword";
  results: SearchResult[];
  total: number;
  request_id: string;
}

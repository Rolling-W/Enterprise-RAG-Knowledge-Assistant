import type { TokenResponse, UserSummary } from "./api/contracts";
export type { Role } from "./api/contracts";
export interface User extends UserSummary {
  name: string;
  permissions: string[];
}
export interface Session extends TokenResponse {
  user: User;
}
export interface KnowledgeDocument {
  document_id: string;
  filename: string;
  format: "PDF" | "Markdown" | "Text";
  size_bytes: number;
  department: string;
  min_clearance: number;
  uploaded_at: string;
  status: "processing" | "ready" | "failed";
  description: string;
  preview: string;
  page_count?: number;
}
export interface Citation {
  id: string;
  document_id: string;
  title: string;
  page?: number;
  line_start?: number;
  line_end?: number;
  section?: string;
  content: string;
}
export interface AssistantResponse {
  answer: string;
  citations: Citation[];
  request_id: string;
}
export interface Message {
  id: string;
  kind: "user" | "assistant";
  content: string;
  citations?: Citation[];
  failed?: boolean;
}
export interface PreviewSelection {
  documentId: string;
  citation?: Citation;
}

import type {
  SearchResponse,
  TokenResponse,
  Role,
  ConversationMessage,
} from "./contracts";
import type { AssistantResponse, Citation, Session } from "../types";

const rolePermissions: Record<Role, string[]> = {
  admin: ["document:read", "document:upload", "document:manage"],
  staff: ["document:read", "document:upload"],
  user: ["document:read"],
  "Standard Staff": ["document:read"],
  "Department Manager": ["document:read", "document:upload"],
  Executive: ["document:read", "document:upload", "document:manage"],
};

export function toSession(response: TokenResponse): Session {
  return {
    ...response,
    user: {
      ...response.user,
      name: response.user.username.split("@")[0] || response.user.username,
      // UI visibility only. Backend remains responsible for authorization.
      permissions: [
        ...(response.user.permissions ?? rolePermissions[response.user.role]),
      ],
    },
  };
}

export function toAssistantResponse(
  response: SearchResponse,
): AssistantResponse {
  return {
    request_id: response.request_id,
    answer: response.results.length
      ? response.results.map((result) => result.content).join("\n\n")
      : "I couldn’t find supporting information in the documents available to your account. Try rephrasing your question or specifying the policy or topic you’re looking for.",
    citations: response.results.map((result) => ({
      id: result.chunk_id,
      document_id: result.document_id,
      title: result.title,
      score: result.score,
      content: result.content,
      permission_level: result.permission_level,
      page: result.citation.page ?? undefined,
      line_start: result.citation.line_start ?? undefined,
      line_end: result.citation.line_end ?? undefined,
    })),
  };
}

export function productRole(role: Role): "admin" | "staff" | "user" {
  if (role === "Executive" || role === "admin") return "admin";
  if (role === "Department Manager" || role === "staff") return "staff";
  return "user";
}

export function toMessages(
  messages: ConversationMessage[],
): import("../types").Message[] {
  return [...messages]
    .sort(
      (a, b) =>
        a.sequence - b.sequence || a.created_at.localeCompare(b.created_at),
    )
    .map((message) => ({
      id: message.message_id,
      kind: message.role,
      content: message.content,
      created_at: message.created_at,
      sequence: message.sequence,
      citations: message.citations.map((citation) => ({
        id: citation.chunk_id,
        document_id: citation.document_id,
        title: citation.unavailable ? "Unavailable source" : citation.title,
        permission_level: citation.permission_level,
        unavailable: citation.unavailable,
        page: citation.page ?? undefined,
        line_start: citation.line_start ?? undefined,
        line_end: citation.line_end ?? undefined,
        content: "",
      })),
    }));
}

export function citationLocation(citation: Citation): string {
  const parts: string[] = [];
  if (citation.page) parts.push(`Page ${citation.page}`);
  if (citation.line_start) {
    parts.push(
      citation.line_end && citation.line_end !== citation.line_start
        ? `Lines ${citation.line_start}–${citation.line_end}`
        : `Line ${citation.line_start}`,
    );
  }
  return parts.join(" · ") || citation.section || "Source excerpt";
}

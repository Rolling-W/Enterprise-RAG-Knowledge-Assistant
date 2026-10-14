import type { SearchResponse, TokenResponse, Role } from "./contracts";
import type { AssistantResponse, Citation, Session } from "../types";

const rolePermissions: Record<Role, string[]> = {
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
      permissions: [...rolePermissions[response.user.role]],
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
      content: result.content,
      page: result.citation.page ?? undefined,
      line_start: result.citation.line_start ?? undefined,
      line_end: result.citation.line_end ?? undefined,
    })),
  };
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

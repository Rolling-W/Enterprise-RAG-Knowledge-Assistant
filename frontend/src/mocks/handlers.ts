import type { KnowledgeDocument } from "../types";
import type {
  SearchRequest,
  SearchResult,
  UserSummary,
  TokenResponse,
  UploadResponse,
} from "../api/contracts";
import { fileContentType, validateFile } from "../uploadPolicy";
import { seedDocuments } from "./data";

type Scenario = "offline" | "server-error" | "empty";
interface MockOptions {
  latencyMs?: number;
  searchLatencyMs?: number;
  processingMs?: number;
}
const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
const validationError = (field: string, msg: string) =>
  json(
    {
      detail: [{ loc: ["body", field], msg, type: "value_error" }],
    },
    422,
  );
const delay = (ms: number) =>
  ms > 0
    ? new Promise((resolve) => globalThis.setTimeout(resolve, ms))
    : Promise.resolve();
function canRead(document: KnowledgeDocument, user: UserSummary) {
  return (
    document.min_clearance <= user.clearance &&
    (user.role === "Executive" ||
      document.department === "Global" ||
      document.department === user.department)
  );
}
async function readText(file: File): Promise<string> {
  if (file.text) return file.text();
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result));
    reader.onerror = () => reject(new Error("Unable to read the file."));
    reader.readAsText(file);
  });
}

// Isolated instances make tests independent of the default UI demo state.
export function createMockTransport(options: MockOptions = {}) {
  let documents = seedDocuments.map((document) => ({ ...document }));
  const sessions = new Map<string, { user: UserSummary; expiresAt: number }>();
  const timers = new Set<ReturnType<typeof setTimeout>>();
  const scenarios = new Map<string, Scenario>();
  const topics: Record<string, RegExp> = {
    "doc-handbook": /leave|vacation|benefit|time off|holiday|health|allowance/i,
    "doc-remote": /remote|hybrid|home|vpn/i,
    "doc-onboarding":
      /onboard|first week|new employee|training|security|account/i,
    "doc-manager": /manager|review|one.to.one|performance/i,
    "doc-strategy": /strategy|leadership|quarter|priority|priorities/i,
  };
  async function handler(
    path: string,
    init: RequestInit = {},
  ): Promise<Response> {
    const method = init.method ?? "GET";
    await delay(
      path.endsWith("/search")
        ? (options.searchLatencyMs ?? 1100)
        : (options.latencyMs ?? 450),
    );
    const scenario = scenarios.get(path);
    scenarios.delete(path);
    if (scenario === "offline") throw new TypeError("Network unavailable");
    if (scenario === "server-error")
      return json(
        { detail: "The service is temporarily unavailable. Please try again." },
        503,
      );
    if (path === "/api/v1/auth/login" && method === "POST") {
      let payload: { username?: string; password?: string };
      try {
        payload = JSON.parse(String(init.body));
      } catch {
        return validationError("body", "Invalid JSON");
      }
      if (
        !payload ||
        typeof payload.username !== "string" ||
        !payload.username.trim()
      )
        return validationError("username", "Username is required");
      if (typeof payload.password !== "string" || !payload.password.trim())
        return validationError("password", "Password is required");
      // Demo fixture; differs from the backend's permissive development login.
      if (payload.password !== "demo123")
        return json(
          { detail: "The email address or password is incorrect." },
          401,
        );
      const username = payload.username.trim().toLowerCase();
      const role =
        username === "executive@enterprise.local"
          ? "Executive"
          : username === "manager@enterprise.local"
            ? "Department Manager"
            : "Standard Staff";
      const user: UserSummary = {
        user_id: `demo-${role}`,
        username,
        role,
        department: role === "Executive" ? "Executive" : "General",
        clearance:
          role === "Executive" ? 3 : role === "Department Manager" ? 2 : 1,
      };
      const access_token = `mock-${crypto.randomUUID()}`;
      sessions.set(access_token, { user, expiresAt: Date.now() + 3600_000 });
      return json({
        access_token,
        token_type: "bearer",
        expires_in: 3600,
        user,
      } satisfies TokenResponse);
    }
    const token =
      new Headers(init.headers).get("Authorization")?.replace(/^Bearer /, "") ??
      "";
    const session = sessions.get(token);
    if (!session || session.expiresAt <= Date.now())
      return json(
        { detail: "Your session has ended. Please sign in again." },
        401,
      );
    const { user } = session;
    if (path === "/api/v1/auth/logout" && method === "POST") {
      sessions.delete(token);
      return json({ success: true });
    }
    if (path === "/api/v1/documents" && method === "GET")
      return json({
        documents:
          scenario === "empty"
            ? []
            : documents.filter((document) => canRead(document, user)),
      });
    if (path.startsWith("/api/v1/documents/") && method === "GET") {
      const document = documents.find(
        (item) =>
          item.document_id ===
          decodeURIComponent(path.slice("/api/v1/documents/".length)),
      );
      if (!document || !canRead(document, user))
        return json({ detail: "This document is unavailable." }, 404);
      return json(document);
    }
    if (path === "/api/v1/upload" && method === "POST") {
      if (user.role === "Standard Staff")
        return json({ detail: "Your role cannot upload documents." }, 403);
      const file = init.body instanceof FormData ? init.body.get("file") : null;
      if (!(file instanceof File))
        return validationError("file", "Choose a file to upload");
      const error = validateFile(file);
      if (error) return json({ detail: error }, 400);
      if (
        !["application/pdf", "text/markdown", "text/plain"].includes(file.type)
      )
        return json(
          { detail: "Only PDF, Markdown, and plain text files are supported." },
          400,
        );
      if (file.name.toLowerCase().includes("upload-error"))
        return json(
          { detail: "The upload could not be completed. Please try again." },
          503,
        );
      const type = fileContentType(file)!;
      const document: KnowledgeDocument = {
        document_id: `doc-${crypto.randomUUID()}`,
        filename: file.name,
        format:
          type === "application/pdf"
            ? "PDF"
            : type === "text/markdown"
              ? "Markdown"
              : "Text",
        size_bytes: file.size,
        department: user.department,
        min_clearance: user.clearance,
        uploaded_at: new Date().toISOString(),
        status: "processing",
        description: "Uploaded document.",
        preview:
          type === "application/pdf"
            ? "A text preview is not available for this document."
            : (await readText(file)).slice(0, 16000),
      };
      documents = [document, ...documents];
      const timer = globalThis.setTimeout(() => {
        document.status = file.name.toLowerCase().includes("processing-error")
          ? "failed"
          : "ready";
        timers.delete(timer);
      }, options.processingMs ?? 2200);
      timers.add(timer);
      return json(
        {
          document_id: document.document_id,
          filename: file.name,
          content_type: type,
          size_bytes: file.size,
          status: "queued",
          message: `Document queued for ${user.department} with clearance ${user.clearance}`,
        } satisfies UploadResponse,
        202,
      );
    }
    if (path === "/api/v1/search" && method === "POST") {
      let payload: SearchRequest;
      try {
        payload = JSON.parse(String(init.body));
      } catch {
        return validationError("body", "Invalid JSON");
      }
      if (
        !payload ||
        typeof payload.query !== "string" ||
        !payload.query.trim() ||
        payload.query.length > 500
      )
        return validationError(
          "query",
          "Enter a question between 1 and 500 characters",
        );
      const {
        query,
        top_k = 5,
        search_mode = "hybrid",
        filters = {},
      } = payload;
      if (!Number.isInteger(top_k) || top_k < 1 || top_k > 20)
        return validationError("top_k", "Must be between 1 and 20");
      if (!["hybrid", "semantic", "keyword"].includes(search_mode))
        return validationError("search_mode", "Invalid search mode");
      if (
        !filters ||
        typeof filters !== "object" ||
        Array.isArray(filters) ||
        Object.values(filters).some((value) => typeof value !== "string")
      )
        return validationError(
          "filters",
          "Expected an object with string values",
        );
      if (query.trim().toLowerCase() === "[error]")
        return json(
          {
            detail:
              "The assistant is temporarily unavailable. Please try again.",
          },
          503,
        );
      // Fictional retrieval fixtures; uploaded files are not indexed.
      const matches =
        scenario === "empty"
          ? []
          : documents.filter(
              (document) =>
                canRead(document, user) &&
                document.status === "ready" &&
                (!filters.department ||
                  document.department === filters.department) &&
                topics[document.document_id]?.test(query),
            );
      const pages: Record<string, number> = {
        "doc-handbook": 12,
        "doc-onboarding": 3,
        "doc-manager": 7,
        "doc-strategy": 4,
      };
      const results: SearchResult[] = matches
        .slice(0, top_k)
        .map((document) => ({
          document_id: document.document_id,
          chunk_id: `${document.document_id}-chunk-1`,
          title: document.filename,
          content: document.preview.split("\n\n").slice(2).join("\n\n"),
          score: 0.92,
          content_type:
            document.format === "PDF"
              ? "application/pdf"
              : document.format === "Markdown"
                ? "text/markdown"
                : "text/plain",
          department_id: document.department,
          clearance_level: document.min_clearance,
          citation: {
            page:
              document.format === "PDF"
                ? (pages[document.document_id] ?? 1)
                : null,
            line_start: null,
            line_end: null,
          },
        }));
      return json({
        query,
        search_mode,
        results,
        total: results.length,
        request_id: `req-${crypto.randomUUID()}`,
      });
    }
    return json({ detail: "The requested resource is unavailable." }, 404);
  }
  return {
    handler,
    next: (path: string, scenario: Scenario) => scenarios.set(path, scenario),
    reset: () => {
      timers.forEach((timer) => globalThis.clearTimeout(timer));
      timers.clear();
      sessions.clear();
      scenarios.clear();
      documents = seedDocuments.map((document) => ({ ...document }));
    },
  };
}

export const mockTransport = createMockTransport();
export const mockHandler = mockTransport.handler;

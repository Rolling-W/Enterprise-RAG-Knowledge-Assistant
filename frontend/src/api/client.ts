import { mockHandler } from "../mocks/handlers";
import { fileContentType } from "../uploadPolicy";
import { toSession } from "./adapters";
import type {
  SearchRequest,
  SearchResponse,
  TokenResponse,
  UploadResponse,
} from "./contracts";
import type { KnowledgeDocument } from "../types";

export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
  ) {
    super(message);
  }
}
export type ApiMode = "mock" | "live";
type Transport = (path: string, init?: RequestInit) => Promise<Response>;
interface ClientOptions {
  mode: ApiMode;
  baseUrl?: string;
  fetchTransport?: Transport;
  mockTransport?: Transport;
}

function errorMessage(body: unknown): string {
  const detail = (body as { detail?: unknown } | null)?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    const messages = detail.map((item) => {
      const entry = item as { loc?: unknown[]; msg?: string };
      return `${entry.loc?.slice(1).join(".") || "Request"}: ${entry.msg || "Invalid value"}`;
    });
    if (messages.length) return messages.join("; ");
  }
  return "Something went wrong. Please try again.";
}

export function createApiClient(options: ClientOptions) {
  const baseUrl = (options.baseUrl ?? "http://localhost:8000").replace(
    /\/+$/,
    "",
  );
  async function request<T>(
    path: string,
    init: RequestInit = {},
    token?: string,
  ): Promise<T> {
    const headers = new Headers(init.headers);
    if (token) headers.set("Authorization", `Bearer ${token}`);
    if (typeof init.body === "string")
      headers.set("Content-Type", "application/json");
    let response: Response;
    try {
      response =
        options.mode === "mock"
          ? await (options.mockTransport ?? mockHandler)(path, {
              ...init,
              headers,
            })
          : await (options.fetchTransport ?? fetch)(`${baseUrl}${path}`, {
              ...init,
              headers,
            });
    } catch {
      throw new ApiError(
        "Unable to connect. Check your connection and try again.",
        0,
      );
    }
    if (response.status === 204) return undefined as T;
    let body: unknown;
    try {
      body = await response.json();
    } catch {
      throw new ApiError(
        response.ok
          ? "The server returned an invalid response."
          : "The server is temporarily unavailable. Please try again.",
        response.status,
      );
    }
    if (!response.ok) throw new ApiError(errorMessage(body), response.status);
    return body as T;
  }
  return {
    mode: options.mode,
    login: async (username: string, password: string) =>
      toSession(
        await request<TokenResponse>("/api/v1/auth/login", {
          method: "POST",
          body: JSON.stringify({ username, password }),
        }),
      ),
    // No logout endpoint in the backend contract. Live logout clears local state.
    logout: (token: string) =>
      options.mode === "mock"
        ? request("/api/v1/auth/logout", { method: "POST" }, token)
        : Promise.resolve(),
    // Proposed document endpoints are available only in mock mode for now.
    documents: (token: string) =>
      options.mode === "mock"
        ? request<{ documents: KnowledgeDocument[] }>(
            "/api/v1/documents",
            {},
            token,
          )
        : Promise.reject(
            new ApiError(
              "The document library is not available yet. You can still upload documents.",
              501,
            ),
          ),
    document: (id: string, token: string) =>
      options.mode === "mock"
        ? request<KnowledgeDocument>(
            `/api/v1/documents/${encodeURIComponent(id)}`,
            {},
            token,
          )
        : Promise.reject(
            new ApiError(
              "The full document preview is not available yet.",
              501,
            ),
          ),
    upload: (file: File, token: string) => {
      const body = new FormData();
      // Browsers may omit Markdown MIME; the backend validates content_type.
      body.append(
        "file",
        new File([file], file.name, {
          type: fileContentType(file) ?? file.type,
        }),
        file.name,
      );
      return request<UploadResponse>(
        "/api/v1/upload",
        { method: "POST", body },
        token,
      );
    },
    search: (
      query: string,
      token: string,
      params: Omit<SearchRequest, "query"> = {},
    ) =>
      request<SearchResponse>(
        "/api/v1/search",
        {
          method: "POST",
          body: JSON.stringify({
            search_mode: "hybrid",
            top_k: 5,
            ...params,
            query,
          }),
        },
        token,
      ),
  };
}

const configuredMode = import.meta.env.VITE_API_MODE ?? "mock";
if (configuredMode !== "mock" && configuredMode !== "live")
  throw new Error("VITE_API_MODE must be mock or live.");
export const api = createApiClient({
  mode: configuredMode,
  baseUrl: import.meta.env.VITE_API_BASE_URL,
});

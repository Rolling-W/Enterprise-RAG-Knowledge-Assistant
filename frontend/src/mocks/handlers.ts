import type {
  DocumentDetail,
  DocumentSummary,
  PermissionLevel,
  SearchRequest,
  SearchResponse,
  UserSummary,
  Conversation,
  ConversationSummary,
  ScoringDebugResponse,
} from "../api/contracts";
import { productRole } from "../api/adapters";
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
const invalid = (field: string, msg: string) =>
  json({ detail: [{ loc: ["body", field], msg, type: "value_error" }] }, 422);
const missing = () =>
  json({ detail: "The requested resource is unavailable." }, 404);
const forbidden = () =>
  json({ detail: "Your account cannot perform this operation." }, 403);
const now = () => new Date().toISOString();
const delay = (ms: number) =>
  ms > 0
    ? new Promise((resolve) => globalThis.setTimeout(resolve, ms))
    : Promise.resolve();
function initialDocuments(): DocumentDetail[] {
  return seedDocuments.map((item) => ({
    document_id: item.document_id,
    filename: item.filename,
    title: item.filename,
    content_type:
      item.format === "PDF"
        ? "application/pdf"
        : item.format === "Markdown"
          ? "text/markdown"
          : "text/plain",
    size_bytes: item.size_bytes,
    permission_level: item.min_clearance as PermissionLevel,
    creator: { user_id: "demo-seed", display_name: "Demo administrator" },
    created_at: item.uploaded_at,
    updated_at: item.uploaded_at,
    status: "indexed",
    available_actions: [],
    preview: item.preview,
    page_count: item.page_count,
  }));
}

export function createMockTransport(options: MockOptions = {}) {
  let documents = initialDocuments();

  const documentDepartments = new Map(
    seedDocuments.map((item) => [item.document_id, item.department]),
  );
  const sessions = new Map<string, { user: UserSummary; expiresAt: number }>();
  const conversations = new Map<string, Conversation>();
  const timers = new Set<ReturnType<typeof setTimeout>>();
  const scenarios = new Map<string, Scenario>();
  const canRead = (document: DocumentSummary, user: UserSummary) => {
    if (productRole(user.role) === "admin") {
      return true;
    }

    const department = documentDepartments.get(document.document_id);

    return (
      document.permission_level <= (user.clearance ?? 0) &&
      (department === "Global" || department === user.department)
    );
  };
  const view = (
    document: DocumentDetail,
    user: UserSummary,
  ): DocumentDetail => ({
    ...document,
    available_actions:
      productRole(user.role) === "admin"
        ? document.status === "processing" || document.status === "deleting"
          ? ["read"]
          : ["read", "change_permission", "reindex", "delete"]
        : ["read"],
  });
  function paginate<T>(items: T[], params: URLSearchParams) {
    const page = Math.max(1, Number(params.get("page")) || 1),
      page_size = Math.min(
        100,
        Math.max(1, Number(params.get("page_size")) || 20),
      );
    return {
      items: items.slice((page - 1) * page_size, page * page_size),
      page,
      page_size,
      total: items.length,
    };
  }
  function startProcessing(document: DocumentDetail, failed = false) {
    document.status = "processing";
    const timer = globalThis.setTimeout(() => {
      document.status = failed ? "failed" : "indexed";
      document.updated_at = now();
      timers.delete(timer);
    }, options.processingMs ?? 1200);
    timers.add(timer);
  }
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
    const url = new URL(path, "http://mock.local"),
      route = url.pathname,
      params = url.searchParams;
    const method = init.method ?? "GET";
    await delay(
      route.endsWith("/search")
        ? (options.searchLatencyMs ?? 350)
        : (options.latencyMs ?? 100),
    );
    const scenario = scenarios.get(route);
    scenarios.delete(route);
    if (scenario === "offline") throw new TypeError("Network unavailable");
    if (scenario === "server-error")
      return json(
        { detail: "The service is temporarily unavailable. Please try again." },
        503,
      );
    let payload: Record<string, unknown> = {};
    if (typeof init.body === "string") {
      try {
        payload = JSON.parse(init.body);
      } catch {
        return invalid("body", "Invalid JSON");
      }
      if (!payload || typeof payload !== "object" || Array.isArray(payload))
        return invalid("body", "Expected an object");
    }
    if (route === "/api/v1/auth/login" && method === "POST") {
      if (typeof payload.username !== "string" || !payload.username.trim())
        return invalid("username", "Username is required");
      if (typeof payload.password !== "string" || !payload.password.trim())
        return invalid("password", "Password is required");
      if (payload.password !== "demo123")
        return json(
          { detail: "The email address or password is incorrect." },
          401,
        );
      const username = payload.username.trim().toLowerCase();

      const role =
      username === "executive@enterprise.local"
        ? "admin"
        : username === "manager@enterprise.local"
          ? "staff"
          : "user";

      const department = role === "admin" ? "Executive" : "General";

      const clearance = role === "admin" ? 3 : role === "staff" ? 2 : 1;

      const user: UserSummary = {
      user_id: "demo-" + username,
      username,
      role,
      department,
      clearance,
      permissions:
        role === "admin"
          ? ["document:read", "document:upload", "document:manage"]
          : role === "staff"
            ? ["document:read", "document:upload"]
            : ["document:read"],
      };

      const access_token = "mock-" + crypto.randomUUID();
      sessions.set(access_token, { user, expiresAt: Date.now() + 3600000 });
      return json({
        access_token,
        token_type: "bearer",
        expires_in: 3600,
        user,
      });
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
    const admin = productRole(user.role) === "admin";
    if (route === "/api/v1/auth/logout" && method === "POST") {
      sessions.delete(token);
      return json({});
    }
    if (route === "/api/v1/documents" && method === "GET") {
      let items =
        scenario === "empty"
          ? []
          : documents.filter((item) => canRead(item, user));
      const level = params.get("permission_level"),
        creator = params.get("creator_id"),
        status = params.get("status"),
        q = params.get("q")?.toLowerCase();
      items = items.filter(
        (item) =>
          (!level || item.permission_level === Number(level)) &&
          (!creator || item.creator.user_id === creator) &&
          (!status || item.status === status) &&
          (!q ||
            [item.filename, item.title, item.preview]
              .join(" ")
              .toLowerCase()
              .includes(q)),
      );
      const sort = params.get("sort_by") ?? "updated_at",
        direction = params.get("sort_order") === "asc" ? 1 : -1;
      const sortValue = (item: DocumentDetail) =>
        sort === "permission_level"
          ? item.permission_level
          : sort === "filename"
            ? item.filename
            : sort === "status"
              ? item.status
              : sort === "created_at"
                ? item.created_at
                : item.updated_at;
      items.sort((a, b) => {
        const x = sortValue(a),
          y = sortValue(b);
        return (
          (x < y
            ? -1
            : x > y
              ? 1
              : a.document_id.localeCompare(b.document_id)) * direction
        );
      });
      return json(
        paginate(
          items.map((item) => {
            const {
              preview: _preview,
              page_count: _pages,
              ...summary
            } = view(item, user);
            return summary;
          }),
          params,
        ),
      );
    }
    const chunkMatch = route.match(
      /^\/api\/v1\/documents\/([^/]+)\/chunks\/([^/]+)$/,
    );

    if (chunkMatch && method === "GET") {
      const documentId = decodeURIComponent(chunkMatch[1]);
      const chunkId = decodeURIComponent(chunkMatch[2]);

      const document = documents.find(
        (item) => item.document_id === documentId,
      );

      if (
        !document ||
        !canRead(document, user) ||
        document.status !== "indexed" ||
        chunkId !== `${documentId}-chunk-1` ||
        !document.preview
      ) {
        return missing();
      }

      return json({
        document_id: documentId,
        chunk_id: chunkId,
        content: document.preview,
      });
    }
    const docMatch = route.match(
      /^\/api\/v1\/documents\/([^/]+)(?:\/(permissions|reindex))?$/,
    );
    if (docMatch) {
      const document = documents.find(
        (item) => item.document_id === decodeURIComponent(docMatch[1]),
      );
      if (!document || !canRead(document, user)) return missing();
      const action = docMatch[2];
      if (method === "GET" && !action) return json(view(document, user));
      if (!admin) return forbidden();
      if (document.status === "processing" || document.status === "deleting")
        return json(
          {
            detail: "The document is being processed. Try again when complete.",
          },
          409,
        );
      if (method === "PATCH" && action === "permissions") {
        if (![1, 2, 3].includes(payload.permission_level as number))
          return invalid("permission_level", "Choose Level 1, 2 or 3");
        document.permission_level = payload.permission_level as PermissionLevel;
        document.updated_at = now();
        return json(view(document, user));
      }
      if (method === "POST" && action === "reindex") {
        startProcessing(document);
        return json(
          { document_id: document.document_id, status: "processing" },
          202,
        );
      }
      if (method === "DELETE" && !action) {
        documents = documents.filter((item) => item !== document);
        return new Response(null, { status: 204 });
      }
    }
    if (route === "/api/v1/upload" && method === "POST") {
      if (!user.permissions?.includes("document:upload")) return forbidden();
      const body = init.body instanceof FormData ? init.body : null;
      const file = body?.get("file");
      if (!(file instanceof File))
        return invalid("file", "Choose a file to upload");
      const rawLevel = body?.get("permission_level"),
        level =
          rawLevel === null || rawLevel === undefined ? 1 : Number(rawLevel);
      if (![1, 2, 3].includes(level))
        return invalid("permission_level", "Choose Level 1, 2 or 3");
      if (!admin && level !== 1) return forbidden();
      const error = validateFile(file);
      if (error) return json({ detail: error }, 400);
      if (file.name.includes("upload-error"))
        return json(
          { detail: "The upload could not be completed. Please try again." },
          503,
        );
      const readText = () =>
        file.text
          ? file.text()
          : new Promise<string>((resolve) => {
              const reader = new FileReader();
              reader.onload = () => resolve(String(reader.result));
              reader.readAsText(file);
            });
      const document: DocumentDetail = {
        document_id: "doc-" + crypto.randomUUID(),
        filename: file.name,
        title: file.name,
        content_type: fileContentType(file)!,
        size_bytes: file.size,
        permission_level: level as PermissionLevel,
        creator: {
          user_id: user.user_id,
          display_name: user.username.split("@")[0],
        },
        created_at: now(),
        updated_at: now(),
        status: "processing",
        available_actions: [],
        preview:
          fileContentType(file) === "application/pdf"
            ? "A text preview is not available for this demo PDF."
            : (await readText()).slice(0, 16000),
      };

      documentDepartments.set(document.document_id, user.department);

      documents.unshift(document);
      startProcessing(document, file.name.includes("processing-error"));
      return json(view(document, user), 202);

    }
    if (
      (route === "/api/v1/search" || route === "/api/v1/search/debug") &&
      method === "POST"
    ) {
      if (route.endsWith("/debug") && !admin) return forbidden();
      const {
        query,
        top_k = 5,
        search_mode = "hybrid",
        filters = {},
      } = payload as unknown as SearchRequest;
      if (typeof query !== "string" || !query.trim() || query.length > 500)
        return invalid(
          "query",
          "Enter a question between 1 and 500 characters",
        );
      if (!Number.isInteger(top_k) || top_k < 1 || top_k > 20)
        return invalid("top_k", "Must be between 1 and 20");
      if (!["hybrid", "semantic", "keyword"].includes(search_mode))
        return invalid("search_mode", "Invalid search mode");
      if (
        !filters ||
        typeof filters !== "object" ||
        Array.isArray(filters) ||
        Object.values(filters).some(
          (item) => !["string", "number"].includes(typeof item),
        )
      )
        return invalid("filters", "Expected string or numeric filters");
      if (query === "[error]")
        return json(
          {
            detail:
              "The assistant is temporarily unavailable. Please try again.",
          },
          503,
        );
      const matches =
        scenario === "empty"
          ? []
          : documents.filter(
              (item) =>
                canRead(item, user) &&
                item.status === "indexed" &&
                (!filters.permission_level ||
                  Number(filters.permission_level) === item.permission_level) &&
                (topics[item.document_id]?.test(query) ||
                  (!topics[item.document_id] &&
                    item.preview?.toLowerCase().includes(query.toLowerCase()))),
            );
      const pageNumbers: Record<string, number> = {
        "doc-handbook": 12,
        "doc-onboarding": 3,
        "doc-manager": 7,
        "doc-strategy": 4,
      };
      if (route.endsWith("/debug")) {
        const limit = payload.candidate_limit ?? 20;
        if (
          !Number.isInteger(limit) ||
          Number(limit) < 1 ||
          Number(limit) > 100
        )
          return invalid("candidate_limit", "Must be between 1 and 100");
        const result: ScoringDebugResponse = {
          query,
          search_mode,
          top_k,
          stages:
            search_mode === "hybrid"
              ? ["bm25", "dense", "rrf"]
              : search_mode === "keyword"
                ? ["bm25"]
                : ["dense"],
          candidates: matches.slice(0, Number(limit)).map((item, index) => ({
            document_id: item.document_id,
            chunk_id: item.document_id + "-chunk-1",
            permission_level: item.permission_level,
            final_rank: index + 1,
            scores: {
              bm25_raw: search_mode === "semantic" ? null : 4.21,
              bm25_rank: search_mode === "semantic" ? null : index + 1,
              dense_raw: search_mode === "keyword" ? null : 0.82,
              dense_rank: search_mode === "keyword" ? null : index + 1,
              fusion: search_mode === "hybrid" ? 0.0325 : null,
              rerank: null,
              final:
                search_mode === "hybrid"
                  ? 0.0325
                  : search_mode === "keyword"
                    ? 4.21
                    : 0.82,
            },
          })),
          timings_ms: {
            authorization_filter: 1,
            ...(search_mode !== "semantic" ? { bm25: 7 } : {}),
            ...(search_mode !== "keyword" ? { dense: 8 } : {}),
            ...(search_mode === "hybrid" ? { fusion: 1 } : {}),
            total: 18,
          },
          request_id: "req-" + crypto.randomUUID(),
        };
        return json(result);
      }
      const result: SearchResponse = {
        query,
        search_mode,
        total: Math.min(matches.length, top_k),
        elapsed_ms: 18,
        request_id: "req-" + crypto.randomUUID(),
        results: matches.slice(0, top_k).map((item) => ({
          document_id: item.document_id,
          chunk_id: item.document_id + "-chunk-1",
          title: item.title,
          content: item.preview ?? "",
          score: 0.92,
          content_type: item.content_type,
          permission_level: item.permission_level,
          citation: {
            page:
              item.content_type === "application/pdf"
                ? (pageNumbers[item.document_id] ?? 1)
                : null,
            line_start: null,
            line_end: null,
          },
        })),
      };
      return json(result);
    }
    if (route === "/api/v1/conversations") {
      if (method === "GET") {
        const items: ConversationSummary[] = [...conversations.values()]
          .filter((item) => item.owner_id === user.user_id)
          .sort((a, b) => b.updated_at.localeCompare(a.updated_at))
          .map(
            ({ messages: _messages, owner_id: _owner, ...summary }) => summary,
          );
        return json(paginate(scenario === "empty" ? [] : items, params));
      }
      if (method === "POST") {
        const conversation: Conversation = {
          conversation_id: "conv-" + crypto.randomUUID(),
          owner_id: user.user_id,
          title: typeof payload.title === "string" ? payload.title : null,
          created_at: now(),
          updated_at: now(),
          messages: [],
        };
        conversations.set(conversation.conversation_id, conversation);
        const {
          messages: _messages,
          owner_id: _owner,
          ...summary
        } = conversation;
        return json(summary, 201);
      }
    }
    const chatMatch = route.match(
      /^\/api\/v1\/conversations\/([^/]+)(?:\/(messages))?$/,
    );
    if (chatMatch) {
      const conversation = conversations.get(decodeURIComponent(chatMatch[1]));
      if (!conversation || conversation.owner_id !== user.user_id)
        return missing();
      if (method === "GET" && !chatMatch[2]) {
        return json({
          ...conversation,
          messages: conversation.messages.map((message) => {
            const citations = message.citations.map((citation) => {
              const document = documents.find(
                (item) => item.document_id === citation.document_id,
              );
              return !document || !canRead(document, user)
                ? {
                    ...citation,
                    title: "Unavailable source",
                    unavailable: true,
                  }
                : citation;
            });
            return {
              ...message,
              content:
                message.role === "assistant" &&
                citations.some((item) => item.unavailable)
                  ? "Some source material is no longer available. Ask again to retrieve currently permitted information."
                  : message.content,
              citations,
            };
          }),
        });
      }
      if (method === "DELETE" && !chatMatch[2]) {
        conversations.delete(conversation.conversation_id);
        return new Response(null, { status: 204 });
      }
      if (method === "POST" && chatMatch[2]) {
        if (
          typeof payload.content !== "string" ||
          !payload.content.trim() ||
          payload.content.length > 500
        )
          return invalid(
            "content",
            "Enter a message between 1 and 500 characters",
          );
        const search = await handler("/api/v1/search", {
          method: "POST",
          headers: init.headers,
          body: JSON.stringify({ query: payload.content }),
        });
        if (!search.ok) return search;
        // Re-check ownership after asynchronous retrieval: deletion may have happened in flight.
        if (!conversations.has(conversation.conversation_id)) return missing();
        const results: SearchResponse = await search.json();
        const sequence = conversation.messages.length + 1;
        conversation.messages.push(
          {
            message_id: "msg-" + crypto.randomUUID(),
            sequence,
            role: "user",
            content: payload.content,
            created_at: now(),
            citations: [],
          },
          {
            message_id: "msg-" + crypto.randomUUID(),
            sequence: sequence + 1,
            role: "assistant",
            content: results.results.length
              ? results.results.map((item) => item.content).join("\n\n")
              : "I couldn’t find supporting information in the documents available to your account.",
            created_at: now(),
            citations: results.results.map((item) => ({
              document_id: item.document_id,
              chunk_id: item.chunk_id,
              title: item.title,
              permission_level: item.permission_level!,
              ...item.citation,
              score: item.score,
            })),
          },
        );
        conversation.updated_at = now();
        return json({ messages: conversation.messages.slice(-2) });
      }
    }
    return missing();
  }
  return {
    handler,
    next: (path: string, scenario: Scenario) => scenarios.set(path, scenario),
    reset: () => {
      timers.forEach((timer) => globalThis.clearTimeout(timer));
      timers.clear();
      sessions.clear();
      scenarios.clear();
      conversations.clear();
      documents = initialDocuments();
    },
  };
}
export const mockTransport = createMockTransport();
export const mockHandler = mockTransport.handler;

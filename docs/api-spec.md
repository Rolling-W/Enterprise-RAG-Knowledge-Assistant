# REST API Contract

FastAPI's `/openapi.json` describes the routes in the running backend. This
document defines the desired cross-layer DTO and behavior contract. Sprint 4
routes are now present on merged `main` via PR #7; presence alone does not
establish conformance to the rules in [rbac-security.md](./rbac-security.md).
The acceptance record identifies remaining gaps and verification status.

## Conventions

- Base URL: `http://localhost:8000`; API prefix: `/api/v1`.
- Protected requests use `Authorization: Bearer <token>`.
- `401`: missing/invalid/expired token. `403`: operation is forbidden.
- `404`: absent or inaccessible resource (same response to prevent existence
  disclosure). `409`: conflicting state. `422`: invalid request.
- JSON timestamps are RFC 3339 UTC. IDs are opaque strings. Lists use
  `page` (1-based, default 1) and `page_size` (default 20, max 100), and return
  `items`, `page`, `page_size`, `total`.
- See [rbac-security.md](./rbac-security.md) for the role matrix and mandatory
  server-side enforcement.

## Shared DTOs

### Authenticated user summary

```json
{
  "user_id": "user_123",
  "username": "manager@enterprise.local",
  "role": "staff",
  "clearance_level": 2,
  "department_id": "General",
  "permissions": ["document:read", "document:upload"]
}
```

`clearance_level` is user-only and derives from the authenticated role:
admin=3, staff=2, user=1. It is compared by the backend with each document's
`permission_level`; it is not copied into document or citation DTOs.

### Document summary

```json
{
  "document_id": "doc_abc123",
  "filename": "Employee_Handbook.pdf",
  "title": "Employee Handbook",
  "content_type": "application/pdf",
  "size_bytes": 18240,
  "department_id": "General",
  "permission_level": 1,
  "creator": {"user_id": "user_123", "display_name": "A. User"},
  "created_at": "2026-10-30T15:20:00Z",
  "updated_at": "2026-10-30T15:25:00Z",
  "status": "indexed",
  "available_actions": ["read", "reindex"]
}
```

`department_id` is the document's audience scope. `permission_level` is an
integer `1..3`; default is 1. `status` is one of
`processing`, `indexed`, `failed`, or `deleting`. `available_actions` is the
server-calculated set from the current principal and resource state. It is a
UI hint; every operation still performs authorization on the server.

### Citation and search result

```json
{
  "document_id": "doc_abc123",
  "chunk_id": "chunk_001",
  "title": "Employee_Handbook.pdf",
  "department_id": "General",
  "permission_level": 1,
  "content": "Employees receive 23 days of annual leave.",
  "content_type": "application/pdf",
  "score": 0.92,
  "citation": {"page": 12, "line_start": null, "line_end": null}
}
```

Citation coordinates are nullable: PDFs typically provide `page`; text sources
may provide `line_start` and `line_end`. Search results never contain a chunk
that failed the caller's server-side permission filter.

## Authentication

### `POST /api/v1/auth/login` (existing development adapter)

Request: `{"username":"demo@enterprise.local","password":"password"}`.
Response includes `access_token`, `token_type`, `expires_in`, and a user
summary with `user_id`, `username`, `role` (`admin|staff|user`), and
`permissions`. The current mock login is not production authentication.

## Documents

### `POST /api/v1/upload` — existing route; Sprint 4 contract update

Multipart fields: `file` (required), `department_id` (required), and
`permission_level` (optional integer `1..3`, default 1). Server derives actor,
product role, and user clearance from the token. Admin may choose levels 1–3;
staff may upload level 1 only; user receives 403. Attempts by staff to assign
level 2/3 receive 403. The server validates `department_id` against a
server-owned allowlist and the caller's assignment authority; the client must
not invent department names. The exact allowlist and which non-admin roles may
assign `Global` or another department remain a policy decision and must be
settled before this route is implemented. Response `202` returns the created
document summary, including its assigned department and permission level,
creator, timestamps, status, and available actions.

### `GET /api/v1/documents` — implemented on main; conformance pending

Query parameters: `page`, `page_size`, `sort_by` (`created_at|updated_at|
filename|permission_level|status`), `sort_order` (`asc|desc`), optional
`department_id`, `permission_level`, `creator_id`, `status`, and `q` (title,
filename, tags, or indexed keywords). Server applies the user's clearance and
department visibility before caller filters and pagination. Filters can only
narrow that set. A requested level outside the caller's clearance or a
department outside the caller's scope returns an empty set; it never widens
visibility.

### `GET /api/v1/documents/{document_id}` — implemented on main; conformance pending

Returns one document summary and any permitted detail fields, including
`department_id` and `permission_level`. Returns 404 for both missing and
inaccessible IDs.

### `PATCH /api/v1/documents/{document_id}/permissions` — implemented on main; conformance pending

Admin only. Request: `{"permission_level":2}`. Validates `1..3`, updates
catalog metadata and all indexed chunk payloads as one logical operation,
updates `updated_at`, and returns the document summary. If index metadata
cannot be updated consistently, fail closed and report an error rather than
returning a partially successful response.

### `POST /api/v1/documents/{document_id}/reindex` — implemented on main; conformance pending

Admin only. Rebuilds chunks/vector records using the catalog's current
permission level and source metadata. Response `202`:
`{"document_id":"doc_abc123","status":"processing"}`.

### `DELETE /api/v1/documents/{document_id}` — implemented on main; conformance pending

Admin only. Removes source metadata, vectors, and related search-index records.
Response `204` only after all required stores confirm deletion. Missing and
inaccessible IDs return 404.

## Search and scoring diagnostics

### `POST /api/v1/search` — existing route; Sprint 4 contract update

Request:

```json
{
  "query": "employee benefits",
  "top_k": 5,
  "search_mode": "hybrid",
  "filters": {"permission_level": 1, "department_id": "Global"}
}
```

`top_k` is `1..20`; mode is `hybrid`, `semantic`, or `keyword`. The user
clearance and document department checks are applied server-side before
retrieval; filters only narrow that authorized set. Response:

```json
{
  "query": "employee benefits",
  "search_mode": "hybrid",
  "results": [],
  "total": 0,
  "request_id": "req_abc123",
  "elapsed_ms": 18
}
```

### `POST /api/v1/search/debug` — implemented on main; conformance pending (admin only)

Accepts the same query parameters plus `candidate_limit` (1..100). Debug is
kept separate from ordinary search to avoid accidental disclosure and latency
cost. It returns only candidates the caller is authorized to read:

```json
{
  "query": "employee benefits",
  "search_mode": "hybrid",
  "top_k": 5,
  "candidates": [
    {
      "document_id": "doc_abc123",
      "chunk_id": "chunk_001",
      "permission_level": 1,
      "scores": {
        "bm25_raw": 4.21,
        "bm25_rank": 2,
        "dense_raw": 0.82,
        "dense_rank": 1,
        "fusion": 0.0325,
        "rerank": null,
        "final": 0.0325
      },
      "final_rank": 1
    }
  ],
  "stages": ["bm25", "dense", "rrf"],
  "timings_ms": {"authorization_filter": 1, "bm25": 7, "dense": 8, "fusion": 1, "total": 18},
  "request_id": "req_abc123"
}
```

`bm25_raw`, `dense_raw`, `fusion`, `rerank`, and `final` are nullable numbers;
rank fields are nullable positive integers. For inactive stages, return null
score/rank and omit the stage from `stages`. Candidate order is ascending
`final_rank`; `top_k` identifies the returned final results while
`candidate_limit` bounds pre-final candidates. `timings_ms` contains measured
non-negative durations. Do not return content, IDs, filter reasons, or counts
for unauthorized documents. Reserve `rerank` for a future cross-encoder or
LLM reranker and optional future `explanation` for a concise, non-sensitive
stage rationale; neither implies that the model is enabled today.

## Conversation persistence

### `POST /api/v1/conversations` — implemented on main; conformance pending

Creates a conversation owned by the authenticated user. Optional request:
`{"title":"Benefits question"}`. Response:
`{"conversation_id":"conv_123","title":"Benefits question","created_at":"...","updated_at":"..."}`.

### `GET /api/v1/conversations` — implemented on main; conformance pending

Returns only the caller's conversations, newest `updated_at` first, paginated.

### `POST /api/v1/conversations/{conversation_id}/messages` — implemented on main; conformance pending

Adds a user message to an owned conversation. Request:
`{"content":"How much annual leave do employees receive?"}`. The API assigns
`message_id`, `sequence`, `role=user`, and `created_at`; clients cannot submit
assistant messages or forge citation records. The assistant turn and its
server-resolved citations are persisted by the chat/retrieval service before
the completed turn is returned to the client. Every append updates the
conversation's `updated_at`.

### `GET /api/v1/conversations/{conversation_id}` — implemented on main; conformance pending

Returns conversation metadata (`conversation_id`, `owner_id`, `title`,
`created_at`, `updated_at`) and ordered messages. Message shape:

```json
{
  "message_id": "msg_123",
  "sequence": 2,
  "role": "assistant",
  "content": "Employees receive 23 days of annual leave.",
  "created_at": "2026-10-30T15:30:00Z",
  "citations": [
    {"document_id":"doc_abc123","chunk_id":"chunk_001","title":"Employee_Handbook.pdf","permission_level":1,"page":12,"line_start":null,"line_end":null}
  ]
}
```

Messages are ordered by `sequence`, then `created_at`; sequence is unique
within a conversation. Citations preserve their source identifiers and
coordinates. On restore, re-check current access before exposing source
content; retain citation identity/coordinates and mark an inaccessible source
unavailable without leaking its content. Conversation access is owner-only
unless an explicit future sharing policy is added.

### `DELETE /api/v1/conversations/{conversation_id}` — implemented on main; conformance pending

Deletes the caller's conversation and its messages; return 204 on success and
404 for absent or non-owned conversations. Archive is not included in this
contract; add it only with an agreed persistence semantics.

## Implementation status and source of truth

The current `main` baseline is merge commit `92bfc08` (PR #7). The backend now
implements document catalog, permission changes, re-index/delete, scoring
debug, conversation persistence, and citation preview routes. It still uses
`clearance` as the user-side code/DTO field and assigns an uploaded document to
the uploader's department; there is no upload `department_id` selection yet.
Treat those as known contract gaps, not as evidence that permission levels
and department scope are the same dimension. Track exact acceptance evidence
in [sprint-4-acceptance.md](./sprint-4-acceptance.md).

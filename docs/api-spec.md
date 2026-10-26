# REST API Contract

FastAPI publishes the executable contract at `/openapi.json`, Swagger UI at
`/docs`, and ReDoc at `/redoc`.

## Conventions

- Base URL: `http://localhost:8000`
- API prefix: `/api/v1`
- Protected requests send `Authorization: Bearer <signed-jwt>`.
- Invalid or expired tokens return `401`; insufficient permissions return `403`.
- Validation failures use FastAPI's standard `422` response shape.
- See [rbac-security.md](./rbac-security.md) for the permission matrix and
  JWT claim rules.

## Authentication

### `POST /api/v1/auth/login`

The development adapter accepts non-empty credentials and assigns a role based
on the username. Production authentication must be provided by the identity
provider.

Request:

```json
{
  "username": "manager@enterprise.local",
  "password": "password"
}
```

Response `200`:

```json
{
  "access_token": "<signed-jwt>",
  "token_type": "bearer",
  "expires_in": 3600,
  "user": {
    "user_id": "user_abc123",
    "username": "manager@enterprise.local",
    "role": "Department Manager",
    "department": "General",
    "clearance": 2
  }
}
```

The client must attach `access_token` to every protected request:

```http
Authorization: Bearer <signed-jwt>
```

## Document ingestion

### `POST /api/v1/upload`

Uploads one document as `multipart/form-data`. The request requires a valid
token with `document:upload`; the backend takes the document department and
clearance from verified token claims, not from a client-supplied role field.

Form fields:

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `file` | file | yes | PDF, Markdown, or plain text document |

Response `202` (the document is parsed, chunked, embedded, and indexed before
the response is returned):

```json
{
  "document_id": "doc_abc123",
  "filename": "Employee_Handbook.pdf",
  "content_type": "application/pdf",
  "size_bytes": 18240,
  "status": "indexed",
  "message": "Indexed 3 chunks for General with clearance 2"
}
```

## Hybrid retrieval

### `POST /api/v1/search`

Requires a valid token with `document:read`. Retrieval must apply the
authenticated user's clearance and department policy before returning ranked
snippets.

Request:

```json
{
  "query": "employee benefits",
  "top_k": 5,
  "search_mode": "hybrid",
  "filters": {
    "department": "HR"
  }
}
```

`top_k` is constrained to `1..20`; `search_mode` is one of `hybrid`,
`semantic`, or `keyword`.

Response `200`:

```json
{
  "query": "employee benefits",
  "search_mode": "hybrid",
  "results": [
    {
      "document_id": "doc_001",
      "chunk_id": "chunk_001",
      "title": "Employee_Handbook.pdf",
      "score": 0.92,
      "content": "Sample retrieved chunk text...",
      "content_type": "application/pdf",
      "department_id": "HR",
      "clearance_level": 1,
      "citation": {
        "page": 12,
        "line_start": 45,
        "line_end": 49
      }
    }
  ],
  "total": 1,
  "request_id": "req_abc123"
}
```

## Frontend integration

Set `VITE_API_BASE_URL=http://localhost:8000`. Keep the token in the client
auth store and attach it through one `fetch`/Axios adapter rather than passing
credentials through individual components. The local Vite origin
`http://localhost:5173` is allowed by CORS.

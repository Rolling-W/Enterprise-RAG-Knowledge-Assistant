# Enterprise RBAC and JWT Security Design

## Role and permission matrix

| Role | Clearance | Read permitted documents | Upload documents | Manage documents/access | Scope |
| --- | ---: | :---: | :---: | :---: | --- |
| Executive | 3 | Yes | Yes | Yes | All departments |
| Department Manager | 2 | Yes | Yes | No | Assigned department |
| Standard Staff | 1 | Yes | No | No | Documents visible at clearance 1 |

Clearance is a data-sensitivity level, not a replacement for permissions:
the request must pass both the operation permission check and the document
clearance/department filter. A future retrieval adapter should apply these
checks before ranking results, not after snippets have been returned.

## JWT payload

The access token is signed with `HS256` in the development scaffold. Production
deployment should use a managed key or asymmetric signing keys and rotate them
without changing the client contract.

```json
{
  "iss": "enterprise-rag-api",
  "sub": "user_abc123",
  "username": "manager@enterprise.local",
  "role": "Department Manager",
  "department": "General",
  "clearance": 2,
  "permissions": ["document:read", "document:upload"],
  "iat": 1727520000,
  "exp": 1727523600,
  "jti": "unique-token-id"
}
```

### Claim rules

- `iss` must match the configured issuer.
- `sub` is the stable User identifier.
- `role`, `department`, `clearance`, and `permissions` are signed server
  claims; the frontend must treat them as read-only display metadata.
- `iat` and `exp` limit token lifetime to one hour in the scaffold.
- `jti` supports future revocation/audit tracking.
- The backend validates the signature, algorithm, issuer, expiration, and
  required claim shape before constructing the authenticated User.

## Request contract

```http
Authorization: Bearer <signed-jwt>
```

`POST /api/v1/search` requires a valid token and applies the token's clearance
to retrieval. `POST /api/v1/upload` additionally requires
`document:upload`. The client no longer submits `user_role`; the backend takes
the department and clearance from the verified token.

Unauthenticated requests return `401`. Authenticated users without the
required permission return `403`. Invalid request bodies continue to return
FastAPI's standard `422` response.

## Development users

The mock login endpoint accepts non-empty credentials to keep frontend work
unblocked. It assigns roles by username:

- `executive@enterprise.local` -> Executive
- `manager@enterprise.local` -> Department Manager
- any other non-empty username -> Standard Staff

This is intentionally a development adapter and must be replaced by the
identity provider before production use. Set `JWT_SECRET` and `JWT_ISSUER`
through environment variables; never commit a production signing secret.

## Qdrant payload schema

The `enterprise_documents` collection uses 384-dimensional cosine vectors.
Every chunk payload must contain these access-control fields:

| Field | Type | Meaning |
| --- | --- | --- |
| `document_id` | keyword | Stable source document identifier |
| `chunk_id` | keyword | Stable chunk identifier |
| `department` | keyword | Owning department, or `Global` |
| `min_clearance` | integer | Minimum clearance required to retrieve the chunk |
| `content_type` | keyword | Source MIME type |
| `title` | keyword | Display title |
| `content` | text | Chunk text used for citation |
| `page`, `line_start`, `line_end` | integer | Citation coordinates |

`department` and `min_clearance` are indexed payload fields. The retrieval
adapter must pass the RBAC filter into Qdrant's vector search before ranking:

- `min_clearance <= user.clearance`
- non-Executive users additionally match their department or `Global`
- Executive users may search all departments, subject to clearance

The implementation lives in `backend/qdrant_schema.py`; collection creation
is explicit through `ensure_collection(client)` so application startup does not
silently create or mutate infrastructure when Qdrant is unavailable.

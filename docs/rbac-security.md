# Authorization and Document Visibility

This document is the authorization source of truth for the demo roles. The API
derives the caller's identity and permissions from the authenticated session.
Frontend controls are presentation only; every protected operation is checked
by the server.

## Terms and independent access dimensions

- `clearance_level` belongs to the authenticated user. It is the highest
  document permission level that user may read.
- `permission_level` belongs to a document. It classifies that document's
  sensitivity and is stored with its catalog record and indexed chunks.
- The server compares the user's `clearance_level` with the document's
  `permission_level`. Do not put both values on one entity or use one as a
  synonym for the other.
- `department_id` belongs to a document. It identifies the department scope
  assigned to that document; it is separate from sensitivity level.

The level comparison is necessary but does not by itself grant visibility.
Department policy is an independent visibility condition. A document is
readable only when both the level comparison and the department rule pass.

## Demo role matrix

| Level | Classification |
| ---: | --- |
| 1 | General internal material for users with clearance 1 or higher |
| 2 | Restricted material for users with clearance 2 or higher |
| 3 | Highly restricted material for users with clearance 3 |

| Display role | Product role | User clearance | Readable levels | Upload levels |
| --- | --- | ---: | --- | --- |
| Executive | `admin` | 3 | 1–3 | 1–3 |
| Department Manager | `staff` | 2 | 1–2 | 1 only |
| Standard Staff | `user` | 1 | 1 only | None |

Document listing, metadata, details, search results, and citation content all
use the same effective visibility rule; a metadata-only response does not
bypass either access dimension.

Only `admin` may change a document's permission level, re-index or delete a
document, or inspect per-candidate scoring diagnostics. `staff` and `user`
cannot gain higher clearance by submitting a role, clearance, permission, or
department value in a request.

## Department visibility

The existing demo rule is retained until the team explicitly changes it:

- `admin` may read documents from every department.
- `staff` and `user` may read documents assigned to their own department or
  the `Global` department, subject to their clearance level.
- Department filters may narrow the caller's authorized results; they may
  never widen them.
- A document's department must be assigned explicitly and consistently in
  catalog metadata and every indexed chunk. Upload must not silently infer
  document ownership from the uploader's department.

The exact allowed-department choices for upload are not yet settled. Until
that policy is agreed and represented by a server-side allowlist, the server
must reject an absent or unauthorized `department_id`; the client must not
invent department names. In particular, selecting `Global` or another team's
department must require an explicit server authorization rule.

## Enforcement requirements

- Validate the bearer token and operation permission on every protected route.
  Return `401` for missing or invalid credentials and `403` for a caller who
  lacks permission to perform the operation.
- Apply both the clearance and department conditions before retrieval ranking,
  snippets, citations, candidate diagnostics, counts, and pagination. Repeat
  the checks for direct document detail and citation-chunk requests.
- Effective level rule: `document.permission_level <= user.clearance_level`.
  The role matrix determines the user's clearance; caller-supplied filters can
  only narrow the server-authorized set.
- Return the same `404` for an absent and an inaccessible document. Do not
  reveal its existence, title, creator, counts, citation, content, or the
  reason an access check failed.
- Store `permission_level` and `department_id` in the document catalog and
  copy both to every indexed chunk. Missing or inconsistent metadata fails
  closed until the document is repaired or re-indexed.
- Only `admin` may assign permission levels 2 or 3, change a level, re-index,
  delete, or inspect scoring diagnostics. `staff` uploads are limited to
  level 1; `user` cannot upload.
- A deletion is complete only when catalog metadata, source content, vectors,
  and related search-index records are removed. Partial failure must be
  visible and retryable, never reported as success.

## Identity and audit

The authenticated identity supplies a stable user ID, product role, user
clearance, department membership, issuer, and expiry. Never trust identity or
authorization fields supplied by the client. Audit document creation,
permission changes, re-indexing, and deletion with actor, document, relevant
old/new values, timestamp, and outcome.

On merged `main` (`92bfc08`), the demo role-to-clearance mapping matches the
matrix above and the backend compares that user-side value with each
document's `permission_level`. The code and token still call the user field
`clearance`; the upload route also assigns department from the uploader and
does not accept a document `department_id`. These are naming and department
assignment gaps against this contract. The current development login is not
production authentication. Persistent audit storage and production identity
provisioning remain deployment work.

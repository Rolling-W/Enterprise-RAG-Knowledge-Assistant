# Document Permission Model and RBAC

This document defines the Sprint 4 authorization contract. The API server is
the authority for both operation permissions and document visibility. A UI
may hide unavailable actions, but it must not make authorization decisions.

## Permission levels

`permission_level` is a document sensitivity classification, not a user role
or an operation permission.

| Level | Meaning | Default |
| ---: | --- | :---: |
| 1 | General internal material suitable for ordinary authenticated users | Yes |
| 2 | Restricted material for explicitly authorized administrators | No |
| 3 | Highly restricted material for explicitly authorized administrators | No |

If upload omits `permission_level`, the server assigns level 1. The server
rejects values outside `1..3`; it never infers a higher level from a client
role field. New documents and existing documents without a recorded level
must be treated as level 1 until an administrator explicitly reclassifies
them. This migration default preserves access without silently widening
access to restricted content.

## Role and action matrix

The product roles for this contract are `admin`, `staff`, and `user`. Roles
and permissions come from the authenticated server-side identity; clients
cannot set or override them in a request body, query string, or upload form.

| Action / visibility | Admin | Staff | User |
| --- | :---: | :---: | :---: |
| Read/search level 1 | Yes | Yes | Yes |
| Read/search level 2 | Yes | Yes | No |
| Read/search level 3 | Yes | No | No |
| Upload | Yes (levels 1–3) | Yes (level 1 only) | No |
| List and view document metadata | All documents | Levels 1–2 | Level 1 only |
| Change permission level | Yes | No | No |
| Re-index or delete | Yes | No | No |
| View scoring debug details | Yes | No | No |

`staff` can access level 1 and level 2 documents, but cannot access
level 3 documents. Staff may upload level 1 documents only.

`user` can access level 1 documents only and cannot upload documents.

### Department-Based Visibility

Sprint 4 preserves the department-based filtering implemented in Sprint 3.

- Admin can access authorized documents across all departments.
- Staff can access level 1–2 documents belonging to their own
  department or the Global department.
- User can access level 1 documents belonging to their own
  department or the Global department.
- Staff can upload level 1 documents only.
- Department visibility and permission-level restrictions must both
  be enforced before search ranking and result generation.
- Missing or invalid required access-control metadata must deny access.
- Advanced cross-department sharing and custom department permissions
  are deferred to future sprints.

For the repository's current demo identities, the target adapter mapping is
`Executive` → `admin`, `Department Manager` → `staff`, and `Standard Staff` →
`user`. This mapping is a role translation only: all non-admin users have the
same level-1 visibility ceiling. The adapter must not use the old numeric
`clearance` value as a substitute for `permission_level`.

## Enforcement requirements

- Validate the bearer token and operation permission on every protected
  endpoint. Return `401` for missing/invalid credentials and `403` for an
  authenticated principal lacking the operation permission.
- Apply the document visibility filter in the database/vector query before
  ranking, snippet construction, citation generation, or debug serialization.
  Repeat the check before returning document details or changing/deleting a
  document; do not rely on a filtered list or a hidden UI button.
- Visibility predicate:
  - `admin`: permission_level in 1..3
  - `staff`: permission_level in 1..2
  - `user`: permission_level = 1
  - Caller-supplied filters may narrow visibility but never widen it.
  Staff and user do not receive level 2/3 results. A caller-supplied filter
  may narrow this set but may never widen it.
- Do not disclose existence, title, creator, counts, citations, or filter
  reasons for a document the caller cannot see. Return the same not-found
  response for an absent document and an inaccessible document.
- Only admin may assign levels 2 or 3, change a document's level, re-index,
  delete, or inspect per-candidate scoring diagnostics. Staff uploads are
  forced to level 1 even if a request attempts another value.
- Keep document metadata in the relational/document catalog and copy
  `permission_level` to every indexed chunk payload. A mismatch or missing
  payload level fails closed for retrieval until repaired/re-indexed.
- Deletion is complete only after catalog metadata, all vector chunks, and
  related search/index records are removed. If any step fails, return an
  error and record enough server-side state to retry; do not report success.

## Token and audit claims

The token contains stable `sub`, product `role`, and server-issued `permissions`
plus issuer and expiry claims. Do not accept a role, permission, owner, or
level claim from an untrusted client. Audit document creation, permission
changes, re-indexing, and deletion with actor, document, old/new level where
applicable, timestamp, and outcome.

The current repository has a development-only mock login and an older
`clearance`-based implementation. Those are scaffold behavior, not the
Sprint 4 contract. Production identity and persistent audit storage remain
deployment requirements.

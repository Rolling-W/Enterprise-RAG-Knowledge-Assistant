# Sprint 4 Acceptance Plan and Integration Snapshot

Sprint window: 2026-10-29 to 2026-11-11  
Snapshot: 2026-11-09  
Owner: Ruolin Wang — Project Manager and Lead Architect

## Acceptance cases

Run these against the integrated backend with isolated test data and three
authenticated principals (`admin`, `staff`, `user`). Each row is a release
gate; record the run ID, build/commit, and evidence when executed.

| ID | Area | Setup / action | Expected result |
| --- | --- | --- | --- |
| RBAC-01 | Authentication | Call protected route without token, with malformed token, and expired token | Each returns 401; no data returned |
| RBAC-02 | Upload default | Admin uploads without `permission_level` | Stored level is 1 and appears in upload/document response |
| RBAC-03 | Upload validation | Upload with level 0, 4, or non-integer value | 422; no catalog/vector record created |
| RBAC-04 | Upload boundary | Staff uploads level 1, then attempts level 2/3 | Level 1 succeeds; level 2/3 returns 403; no restricted record created |
| RBAC-05 | Role boundary | User attempts upload and all management routes | 403; no state changes |
| RBAC-06 | Search visibility | Seed matching documents at levels 1, 2, and 3 across Finance, Engineering, and Global departments; search as each role | Admin sees levels 1–3 across all departments; staff sees levels 1–2 in their own department and Global; user sees level 1 in their own department and Global only |
| RBAC-07 | Search paths | Repeat RBAC-06 with keyword, dense/semantic, and hybrid search | Same role-authorized document set in every mode; filter runs before ranking/snippet creation |
| RBAC-08 | Caller filters | Staff requests level 3; user requests level 2/3; callers attempt to widen their authorized scope | Unauthorized levels return an empty set or 403; filters never expand visibility |
| RBAC-09 | Metadata disclosure | Request list, search, debug, or direct detail for a document above the caller's authorized level | No title, creator, citation, count, content, or existence leak; inaccessible detail is indistinguishable from absent (404) |
| DOC-01 | Listing | List with pagination, each supported sort, status, creator, permission level, and text query | Stable ordering, correct totals/pages; all results remain authorized |
| DOC-02 | Detail | Read an authorized document and an absent/restricted ID | Authorized DTO includes level, creator, timestamps, status, and server actions; both inaccessible cases return same 404 |
| DOC-03 | Permission change | Admin changes level 1 to 2 and back; staff/user attempt change | Admin update is reflected in catalog and every chunk before success; other roles get 403 |
| DOC-04 | Re-index | Admin re-indexes a document after level change; other roles attempt | Rebuilt chunk metadata matches catalog; only admin can trigger |
| DOC-05 | Delete | Admin deletes a multi-chunk document; retry after a simulated partial-store failure | Success only after catalog, vectors, and related index records are gone; failure is visible/retryable and not reported as success |
| SCORE-01 | Debug schema | Admin debugs keyword, semantic, and hybrid queries | Candidate list, active-stage scores/ranks, fusion/final rank, top-k and non-negative timings validate against schema |
| SCORE-02 | Debug authorization | Staff/user call debug; admin query matches restricted and public documents | Staff/user get 403; admin candidates are authorized; no rejected-document payload is serialized |
| CHAT-01 | Persistence | Create conversation and append user/assistant messages with citations | Owner, timestamps, order, and citation IDs/coordinates persist |
| CHAT-02 | Restore | Load an existing conversation after new messages | Messages restore in stable sequence and citations point to the same source chunk/coordinates |
| CHAT-03 | Ownership/delete | Another user loads/deletes conversation; owner deletes it | Non-owner receives 404; owner gets 204 and messages are removed |
| CHAT-04 | Citation access drift | Staff saves a conversation citing a level 2 document; admin reclassifies the document to level 3; staff restores the conversation | Message remains ordered; citation is marked unavailable without exposing restricted source information |
| INT-01 | Cross-layer contract | Upload, list, search, detail, change permission, re-index, delete; create and restore conversation | API DTOs and UI agree on fields/actions; no stale citation or action after state changes |

## Integration/security execution record

### Architecture deliverables

| Deliverable | Source of truth | Status at snapshot |
| --- | --- | --- |
| Permission matrix and level semantics | [rbac-security.md](./rbac-security.md) | Defined |
| Upload, document, search, scoring, and conversation DTOs | [api-spec.md](./api-spec.md) and `frontend/src/api/contracts.ts` | Defined; backend targets marked |
| Acceptance and security test cases | This document, RBAC-01 through INT-01 | Defined; execution pending integration |
| Integration sign-off report | This document | Not passed; current implementation boundary recorded below |

The architecture contract is intentionally ahead of the implementation: the
backend must not advertise a target route until its authorization and
integration tests exist. Frontend types accept the new DTO fields while
retaining legacy development fields during the migration from clearance-based
demo identities to `admin|staff|user`.

### Snapshot from repository inspection

At the snapshot date, repository routes and tests provide an initial scaffold:

- Implemented routes: `POST /api/v1/auth/login`, `POST /api/v1/upload`, and
  `POST /api/v1/search`.
- Existing integration tests exercise a mock login, upload, all three search
  modes, citations, unauthenticated search, upload denial for Standard Staff,
  and a department-filter denial for the Department Manager.
- Search applies a clearance/department Qdrant filter before semantic or BM25
  ranking. This is useful baseline coverage, but it is not the Sprint 4
  `permission_level` contract.
- Current implementation assigns upload clearance from the caller token and
  has no request field for explicit permission level. The mock Department
  Manager is clearance 2; Standard Staff is clearance 1 and cannot upload.
  This does not establish the Sprint 4 staff level-1 upload behavior or the
  new admin/staff/user matrix.
- No document list/detail/update/re-index/delete routes, scoring debug route,
  persistent conversation routes, or corresponding integration tests are
  present at this snapshot.

### Result

**Sprint 4 integration acceptance: NOT PASSED.** The implemented surface does
not yet cover the acceptance contract above, so the Sprint cannot be signed
off from the current checkout. I attempted the existing suite with
`python -m unittest discover -s backend/tests -v`; the `python` command is not
available in this Windows environment. Retried with the configured Codex
Python runtime; test discovery stopped before execution because `fastapi` and
`unstructured` are not installed there. Thus no runtime acceptance result is
available. This is an environment/test prerequisite blocker, not a claim that
the missing features failed a runtime test. Rerun once dependencies are
available and backend/UI integration lands; replace this snapshot with actual
run results.

### Handoff and exit criteria

1. Ray implements server-side role/level enforcement, document management,
   debug scoring schema, and persisted conversation APIs.
2. Yunting consumes the shared DTOs and action affordances; UI role checks are
   presentation only.
3. Run every applicable case above against the integrated build. Attach
   automated test names or request/response evidence and record failures.
4. Close the sprint only when all release-gate cases pass, including all three
   retrieval modes and citation restore/access-drift checks.

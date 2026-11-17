# Sprint 4 Acceptance Plan and Integration Status

Sprint window: 2026-10-29 to 2026-11-11  
Review update: 2026-11-14
Owner: Ruolin Wang — Project Manager and Lead Architect

## Acceptance cases

Run these against the integrated backend with isolated test data and three
authenticated principals: Executive (`admin`), Department Manager (`staff`),
and Standard Staff (`user`). Each row is a release gate; record the run ID,
build/commit, and evidence when executed.

| ID | Area | Setup / action | Expected result |
| --- | --- | --- | --- |
| RBAC-01 | Authentication | Call protected route without token, with malformed token, and expired token | Each returns 401; no data returned |
| RBAC-02 | Upload default | Executive (`admin`) uploads without `permission_level` and supplies an authorized `department_id` | Stored level is 1; supplied department and level appear in response and catalog |
| RBAC-03 | Upload validation | Upload with level 0, 4, or non-integer value | 422; no catalog/vector record created |
| RBAC-04 | Upload boundary | Department Manager (`staff`) uploads level 1, then attempts level 2/3; Standard Staff (`user`) attempts level 1 | Manager level 1 succeeds; manager level 2/3 and all Standard Staff uploads return 403; no unauthorized record is created |
| RBAC-05 | Department assignment | Upload with an allowed, missing, unknown, and unauthorized department | Allowed assignment is persisted identically in catalog and vector payloads; invalid or unauthorized assignments fail without partial records |
| RBAC-06 | Role boundary | Standard Staff (`user`) attempts upload and all management routes | 403; no state changes |
| RBAC-07 | Search visibility | Seed matching docs at levels 1, 2, 3 across own, other, and Global departments; search as each role | Executive sees levels 1–3 across departments; Department Manager sees levels 1–2 in own/Global; Standard Staff sees level 1 in own/Global |
| RBAC-08 | Search paths | Repeat RBAC-07 with keyword, dense/semantic, and hybrid search | Same authorized document set in every mode; both access dimensions apply before ranking/snippet creation |
| RBAC-09 | Caller filters | Callers request levels above clearance or departments outside their visibility | Filter narrows to empty or returns 403; never expands visibility |
| RBAC-10 | Metadata disclosure | Request list, search, debug, or direct detail for a restricted document | No title, creator, citation, count, content, or existence leak; detail is indistinguishable from absent (404) |
| DOC-01 | Listing | List with pagination, each supported sort, status, creator, department, permission level, and text query | Stable ordering, correct totals/pages; all results remain authorized |
| DOC-02 | Detail | Read an authorized document and an absent/restricted ID | Authorized DTO includes department, permission level, creator, timestamps, status, and server actions; both inaccessible cases return same 404 |
| DOC-03 | Permission change | Admin changes level 1 to 2 and back; staff/user attempt change | Admin update is reflected in catalog and every chunk before success; other roles get 403 |
| DOC-04 | Re-index | Admin re-indexes a document after level change; other roles attempt | Rebuilt chunk metadata matches catalog; only admin can trigger |
| DOC-05 | Delete | Admin deletes a multi-chunk document; retry after a simulated partial-store failure | Success only after catalog, vectors, and related index records are gone; failure is visible/retryable and not reported as success |
| SCORE-01 | Debug schema | Admin debugs keyword, semantic, and hybrid queries | Candidate list, active-stage scores/ranks, fusion/final rank, top-k and non-negative timings validate against schema |
| SCORE-02 | Debug authorization | Staff/user call debug; admin query matches restricted and public documents | Staff/user get 403; admin candidates are authorized; no rejected-document payload is serialized |
| CHAT-01 | Persistence | Create conversation and append user/assistant messages with citations | Owner, timestamps, order, and citation IDs/coordinates persist |
| CHAT-02 | Restore | Load an existing conversation after new messages | Messages restore in stable sequence and citations point to the same source chunk/coordinates |
| CHAT-03 | Ownership/delete | Another user loads/deletes conversation; owner deletes it | Non-owner receives 404; owner gets 204 and messages are removed |
| CHAT-04 | Citation access drift | Revoke a cited document after conversation save, then restore conversation | Message remains ordered; inaccessible source is marked unavailable and its content is not exposed |
| INT-01 | Cross-layer contract | Upload with explicit department and permission, list, search, detail, change permission, re-index, delete; create and restore conversation | API DTOs and UI agree on fields/actions; no stale citation or action after state changes |

## Integration/security execution record

### Architecture deliverables

| Deliverable | Source of truth | Status on merged `main` |
| --- | --- | --- |
| Permission matrix and level semantics | [rbac-security.md](./rbac-security.md) | Defined |
| Upload, document, search, scoring, and conversation DTOs | [api-spec.md](./api-spec.md) and `frontend/src/api/contracts.ts` | Defined; merged routes need conformance checks |
| Acceptance and security test cases | This document, RBAC-01 through INT-01 | Defined; merged baseline execution pending |
| Integration sign-off report | This document | Not passed; remaining gaps recorded below |

PR #7 is merged on `main` at `92bfc08`. Its backend now implements the Sprint 4
catalog, search/debug, conversation, and citation routes, but this updated
acceptance plan has not been run against that merged commit. Frontend unit
tests and mock flows do not establish backend authorization. `clearance_level`
is the user attribute; `permission_level` and `department_id` are document
attributes. The current upload route sets document department from the
uploader and the frontend has no department selector. The rule for which
departments each role may assign remains open, so RBAC-05 and INT-01 cannot
pass until it is decided, implemented, and tested.

### Snapshot from repository inspection

At merged `main` (`92bfc08`), repository routes include:

- Implemented routes: login, upload, document catalog/detail, permission
  changes, re-index/delete, citation previews, search/debug, and conversation
  persistence.
- The backend compares a user-side clearance value with document
  `permission_level`, and applies department visibility separately. The user
  field is still named `clearance` in the current DTO/token rather than the
  canonical contract name `clearance_level`.
- Upload accepts `permission_level` but has no `department_id` form field;
  backend assigns the uploader's department. Frontend has no department
  selector. This prevents explicitly assigning a level-compliant document to
  another authorized department.
- Current department checks restrict non-admin visibility to own department
  and `Global`; an integration test expects a Manager to receive 404 for an
  Executive-department citation. That verifies the present policy but does not
  settle upload assignment or cross-department sharing policy.
- PR #7's description reports backend/frontend tests and a fresh local setup
  check. The review environment independently ran the frontend from the PR
  head: 61 tests passed, and TypeScript plus production build passed. It could
  not run Python or Docker integration checks; no independent full-stack
  result is recorded here.

### Result

**Integration acceptance: NOT PASSED against merged `main` (`92bfc08`).** The
frontend checks passed against PR head `95d68d1`, but the full acceptance plan
has not been rerun after merge. The review environment could not execute
Python or Docker, so PostgreSQL/Qdrant/OpenAI integration remains unverified
here. The checked-in CI workflow runs frontend production build and backend
Python compilation; it does not run frontend tests or backend integration
tests. Record new results against the exact commit and service setup when run.

### Handoff and exit criteria

1. Agree and document which departments each role may assign during upload,
   including whether `Global` and cross-department assignment are allowed.
2. Align backend and frontend contracts with the independent user clearance,
   document permission, and document department attributes.
3. Run every applicable case above against the integrated build. Attach
   automated test names or request/response evidence and record failures.
4. Close acceptance only when all release gates pass, including all three
   retrieval modes and citation restore/access-drift checks.

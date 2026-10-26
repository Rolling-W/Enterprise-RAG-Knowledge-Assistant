# Frontend Sprint 2 integration notes

## Current integration — October 26, 2026

Backend commit `6399a19` from `ruolin/sprint2-architecture-qdrant` is merged into
`yunting-dev`. The earlier October 14 assessment below is historical.

- Frontend defaults to `live`; Docker Compose also sets `VITE_API_MODE=live`.
  Set `VITE_API_MODE=mock` explicitly for the independent demo.
- Upload returns `202` with `status: indexed` after synchronous ingestion.
  The frontend displays indexing completion and the backend's chunk-count message.
  `queued` remains supported for the asynchronous mock workflow.
- Search shows the backend score as a raw decimal, and the selector sends
  `keyword`, `semantic`, or `hybrid`. Retries retain the original mode.
- All protected HTTP requests notify the auth store on 401, even for non-JSON
  bodies. Only the matching token is invalidated; a delayed response for an old
  session cannot clear a newer login. Login failures and 403 do not sign out.
- Source cards use the document and chunk identifiers together as React keys,
  since the integrated backend can reuse chunk identifiers across documents.
- Document list/status and original-file preview endpoints remain unavailable.
  Live citation drawers display the returned excerpt and coordinates.

### Verification

Run `npm run check` inside `frontend` for component/application integration tests,
TypeScript and production build. These tests require no running backend.

With backend dependencies and `httpx` installed, run from the repository root:

```sh
python -m unittest discover -s backend/tests -v
```

These tests run real FastAPI login, upload, parsing, indexing, all three retrieval
modes, citation metadata and RBAC responses against isolated in-memory Qdrant.
Only the Qdrant connection factory is replaced. They do not validate a Docker
deployment or a networked Qdrant server, PDF viewer navigation, or retrieval quality.

For a full deployment, run `docker compose up --build`, open
`http://localhost:5173`, sign in as Manager, upload a Markdown/TXT file containing
a unique phrase, then search it in each mode. Confirm the indexing success, score,
content and source coordinates. The executable API contract is `/openapi.json`.

## Historical assessment — October 14, 2026

Reviewed October 14, 2026. Frontend remains Vite + React + TypeScript + SCSS.

## References and scope

- Local/main baseline: `09487cd`, September 28, 2026.
- Architecture reference: `5f4b950`, October 10, 2026, on `ruolin/sprint2-architecture-qdrant`.
- RAG reference: `d8fbe6e`, October 13, 2026, on `rag-dev`.

The architecture branch updates the public search DTO. The RAG branch adds parsing/chunking/retrieval internals, but does not change `backend/main.py` or the API spec relative to main. Both branches were inspected via fetched Git objects; they were not merged into the user's current working files.

`frontend/src/api/contracts.ts` models the architecture branch's login, upload, and search HTTP shapes. `frontend/src/api/adapters.ts` converts these into UI display models. Generated OpenAPI is available from a running backend at `/openapi.json`; it remains the executable source of truth for future integration.

## Implemented frontend behavior

| Area | Behavior |
| --- | --- |
| Shell | Existing login, protected routes, sidebar, topbar, responsive SCSS retained |
| Upload | Independent `FileUpload` with selection/drop, validation, remove, busy/success/failure states, and callbacks |
| HTTP | Environment-selected mock/live transport, one Bearer/JSON adapter, multipart MIME normalization, readable 401/403/422/server/network errors |
| Chat | Search DTO converted to retrieved text and chunk citations; page/line metadata may be absent; retries and new conversations supported |
| Mock | Login/search/upload responses follow the reference shapes; resettable sessions/documents/timers; one-shot failure/empty scenarios |
| Tests | API, Mock, component and application workflow tests run without FastAPI, Qdrant, or an LLM |

## API boundaries and pending agreements

| Endpoint | Status |
| --- | --- |
| `POST /api/v1/auth/login` | Existing backend contract, including `expires_in` |
| `POST /api/v1/upload` | Existing single-file multipart contract, complete `202 queued` response |
| `POST /api/v1/search` | Architecture contract with `results`, `document_id`, `chunk_id`, content and citation metadata |
| `GET /api/v1/documents` | Proposed Mock-only extension; list/status polling needs backend agreement |
| `GET /api/v1/documents/{id}` | Proposed Mock-only extension; full preview needs backend agreement |
| `POST /api/v1/auth/logout` | Mock-only session revocation; live logout is local |
| Chat generation/streaming | No agreed endpoint; frontend currently displays retrieved excerpts |

The backend login response does not contain `name` or `permissions`. The UI uses the username's local part as a display name and derives control visibility from the documented role matrix. This never grants server-side permissions. Executive includes read, upload and manage permissions in the display model, though no management UI is added in this sprint.

The reference search result uses `department_id` and `clearance_level`, whereas RAG's internal `DocumentChunk` still uses `department` and `min_clearance`. Frontend follows the public API shape; internal model mapping remains backend work. Main's old `doc_id` search response is not the reference contract for live mode.

The 10 MB/non-empty upload policy is retained from the existing frontend as a product constraint. The backend scaffold currently validates MIME types but does not enforce that same size limit. This needs team agreement before describing the limit as a shared backend rule. The client normalizes PDF/Markdown/TXT MIME types based on the supported extension because browsers may omit Markdown MIME; backend parsing and validation remain authoritative.

Mock login uses `demo123` to exercise invalid-credential UI. The development backend currently accepts non-empty passwords. This deliberate fixture difference is separate from response contract alignment. Mock tokens are session-map identifiers, not signed JWTs; sessions expire after one hour.

Sample retrieval topics are deterministic fictional fixtures. Uploaded documents are listed and their processing completion/failure is simulated, but they are not actually parsed/indexed for search. Source previews are excerpts, not rendered PDF pages or precise highlights. Missing page/line coordinates display `Source excerpt`; no coordinates are invented.

## Acceptance walkthrough

1. `cd frontend`, `npm install`, `npm run dev`; no backend services required.
2. Sign in as Manager; navigate between assistant and document library.
3. Select/drop a non-empty PDF, MD or TXT; upload and observe Processing → Ready. Try invalid, empty, oversized, or multiple files.
4. Include `upload-error` or `processing-error` in a filename to exercise the two failure stages.
5. Ask about annual leave or remote work; open a source and close with Escape. Ask an unrelated question for empty retrieval; submit `[error]` for failure/retry.
6. Sign in as Staff: upload controls are absent; Manager/Executive-only documents are unavailable.
7. Run `npm run check` for independent tests, TypeScript and production build.
8. For live checks, use a backend exposing the architecture contract, set `VITE_API_MODE=live` and `VITE_API_BASE_URL`, restart Vite. Verify login/upload/search; document list/status and full preview await backend endpoints.

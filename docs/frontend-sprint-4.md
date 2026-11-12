# Sprint 4 frontend delivery

Date: November 12, 2026. Baseline: main at 5e21045.
This document records frontend implementation and its backend dependencies.
It does not replace the cross-layer release gates in sprint-4-acceptance.md.

## Implemented

- Upload permission selector: Level 1 default, admin Levels 1-3, staff Level 1,
  user read-only. Multipart requests include permission_level.
- Real document API client and library: server pagination, sorting, title/filename/
  keyword query, level/creator/status filters, details, permission changes,
  re-index, confirmed deletion and processing polling. Mutation buttons use
  each document's available_actions. Failures retain the dialog for retry.
- Saved conversations: owner-scoped history with pagination, lazy creation on
  first send, message append, reload in sequence order, citation coordinates,
  timestamps and confirmed deletion. Reload follows successful append so the
  client does not depend on an unspecified append-response shape.
- Request guards prevent stale search/restore responses from overwriting the
  selected conversation. Ambiguous saved-message failures require reload rather
  than automatically resubmitting the message.
- Citation source drawer loads current authorized document details before
  showing cached source text. A 403/404 hides that text. Restored unavailable
  citations retain coordinates, use a generic label and cannot be opened.
  No score or snippet is invented when the saved-message DTO lacks it.
- Admin-only development scoring inspector: query, mode, top-k, candidate limit,
  raw scores and ranks, fusion/rerank/final score, final ranking and timings.
  Null stages display a dash. Mock scores/timings are explicitly simulated.
  Production builds omit the inspector entry.
- Authentication consumes server-issued permissions when supplied, including
  an empty set; legacy identity permissions remain a presentation fallback.
  Role labels use User / Staff / Admin; legacy identity mapping is preserved.
- Updated mock transport and component/API/workflow tests cover the new contract.
  Mock authorization is a UI test fixture, not production security.

## Run and demo

From frontend:

    npm install
    npm run check
    npm run dev

Live remains the default. For an independent demo, set VITE_API_MODE=mock in
frontend/.env.local, then restart Vite. Restore VITE_API_MODE=live for integration.

Development shortcuts (password demo123):

| Shortcut | Existing development email | Product role | Visibility / upload |
| --- | --- | --- | --- |
| User | staff@enterprise.local | user | Level 1 / no upload |
| Staff | manager@enterprise.local | staff | Level 1 / Level 1 upload |
| Admin | executive@enterprise.local | admin | Levels 1-3 / Levels 1-3 upload |

The current backend still returns legacy identity names and uses the older
clearance policy. Its identity and authorization implementation must be updated
to the product roles above. A UI mapping cannot enforce the new server policy.

Mock catalog/history are in browser memory and reset on a full reload. They
remain available across page navigation and signing in again within the same
mock runtime. Persistent storage across restarts belongs to the backend.
Login itself remains in memory, so a browser reload requires signing in again.

## Integration requirements for Ray

Implement the routes and authorization in docs/api-spec.md:

- Upload must validate/store permission_level and return the assigned level.
  The old upload backend ignores the new multipart field and derives clearance
  from the token; the frontend cannot guarantee Level 1 behavior against it.
- GET documents returns items/page/page_size/total. Summary fields include
  permission_level, creator, created_at, updated_at, status and available_actions.
  Detail may supply preview as an authorized plain-text excerpt; original PDF
  download/render/navigation is not defined by the current API contract.
- PATCH permissions, POST reindex and DELETE document must update all stores
  consistently and reject unauthorized callers on the server.
- Conversation append accepts only user content. The frontend sends {content},
  then GETs the conversation after the completed turn is persisted. It never
  submits assistant messages or citation records.
- The message contract has no search_mode field. Saved conversations therefore
  use server retrieval settings; explicit keyword/semantic/hybrid selection is
  available in search-only mode. Add a shared message-request extension before
  enabling per-turn retrieval mode selection for saved conversations.
- Restore must recheck source access, set citation.unavailable, redact source
  metadata/content as required, and prevent saved assistant text from revealing
  revoked content. Frontend cannot reconstruct server authorization.
- Search debug must enforce admin access and exclude unauthorized candidates,
  metadata, filter reasons and counts. LLM/rerank functionality is not fabricated.

If conversation creation returns 404/405/501, the UI explicitly switches to
unsaved search against the real search endpoint. It never substitutes mock data.
Other creation failures stay visible and do not silently switch modes.
Missing document/history APIs show unavailable states with retry.

## Validation

Final frontend check on November 12, 2026: all 61 tests across five files passed;
TypeScript and the Vite production build passed. git diff --check also passed.

Run npm run check for automated frontend checks. Workflow coverage includes:

- Role-dependent upload controls, explicit level submission and denied operations.
- Backend action hints, server-side query parameters, document/history pagination.
- Details, permission updates, re-index, deletion confirmation, failed-delete retry.
- Saved-message order/citations, navigation/restore, delete and access drift.
- Expired-token handling, empty/network/forbidden/not-found states.
- Late responses, original unsaved retry mode, ambiguous message delivery.
- Stage-aware scoring diagnostics and inactive-stage null values.

Browser review used an isolated mock Vite instance on 127.0.0.1:5175. Desktop and
390px responsive views, saved-message creation and history/citation recovery were
checked. This is frontend verification, not an integrated backend security pass.
The local backend at localhost:8000 was not running during final inspection.

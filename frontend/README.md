# Enterprise RAG frontend

A capstone frontend built with React, TypeScript, Vite, and SCSS. Live API mode is the default and uses the merged FastAPI backend and Qdrant. An explicit mock mode is available for independent UI demos and tests.

## Run locally

```sh
cd frontend
npm install
npm run dev
```

Open http://localhost:5173. To check a production build, run `npm run build`.

## Independent tests

```sh
npm test             # Run all tests once, with no backend services
npm run test:watch   # Watch while developing
npm run check        # Tests, TypeScript check, and production build
```

Vitest 2 is used with the existing Vite 5 project, following the [Vitest setup guide](https://v2.vitest.dev/guide/). React component tests use [Testing Library](https://testing-library.com/docs/react-testing-library/setup/) and jsdom.

Tests cover the HTTP contract, JSON/Bearer headers, multipart MIME handling, validation errors, isolated Mock data, authorization, upload processing, the upload component, protected routes, navigation, source previews, and chat retry/late-response behavior.

## Mock and live API modes

Copy `.env.example` to `.env.local`. Set `VITE_API_MODE=live` (default) or explicitly choose `VITE_API_MODE=mock`, and set `VITE_API_BASE_URL` for live requests. Restart Vite after changing these values. An existing `.env.local` with `mock` still overrides the default. Docker Compose explicitly uses live mode.

The backend branch through commit `6399a19` has been merged into `yunting-dev`. Login returns a signed JWT; upload parses and indexes documents before returning `202` with `status: indexed`; search returns real indexed excerpts, scores, and citation coordinates. See [frontend integration notes](../docs/frontend-integration.md) for verification and remaining API boundaries.

Live mode supports login, upload, and retrieval through real `fetch` requests. The search selector supports hybrid, semantic, and keyword requests, and each source shows its raw retrieval score. Retrying preserves the failed request's mode. Protected 401 responses clear the matching session and redirect to login; 403 errors keep the session and display the backend message. Upload completion distinguishes indexed documents from queued uploads. The document library is unavailable until the backend supplies list/status endpoints. Clicking a live search citation shows its returned excerpt, location metadata, and score. Live logout clears the local session. Live failures never fall back to mock data.

## Pages

- `/#/login`: email and password sign-in, role shortcuts, loading and error states.
- `/#/assistant`: questions, retrieved excerpts, citations, copy, empty and error states.
- `/#/documents`: file selection/drop, mock processing, document search, and source previews.

Routes use HashRouter so the built app can work on static hosting without route rewrites. Login and conversation state are in browser memory; refreshing requires signing in again. Live uploads remain in Qdrant. Mock documents reset on refresh. Starting a new assistant page resets its conversation.

## Development test accounts

The interface uses regular product language and does not display mock badges. The sign-in page pre-fills the manager account and password, and Staff / Manager / Executive shortcuts fill the corresponding credentials without automatically signing in. These accounts are for local development only.

Mock accounts use password **demo123**. The development backend accepts non-empty passwords; it is not a production identity provider.

| Email                      | Role               | Accessible sample documents |
| -------------------------- | ------------------ | --------------------------- |
| staff@enterprise.local     | Standard Staff     | 3; read-only                |
| manager@enterprise.local   | Department Manager | 4; read and upload          |
| executive@enterprise.local | Executive          | 5; read and upload          |

The mock transport applies department/clearance rules for lists, previews, and sample answers. These are demonstration rules in a browser, not production authorization.

## Demo interactions

- Ask about leave/benefits, remote work, onboarding, manager reviews, or leadership strategy. The Mock returns fictional retrieved snippets with role-appropriate citations. The UI displays those snippets; the search contract does not provide an LLM-generated answer.
- Ask an unrelated question to see an unsupported-answer state.
- Submit `[error]` to simulate a failed search.
- Use a wrong password to simulate failed login.
- Upload one non-empty `.pdf`, `.md`, or `.txt` file up to 10 MB. Files are received, then marked ready after mock processing.
- Include `upload-error` in a filename to simulate an upload failure.
- Include `processing-error` in a filename to simulate a processing failure.
- Unsupported or empty files are rejected. Search the library for an unknown name to see an empty state.

Text/Markdown uploads can show a plain text excerpt. Uploaded PDFs are not parsed, and uploads are not indexed for question answering. Source previews display sample text and citation metadata, not actual rendered PDF pages or precise highlights.

## Source structure

The interface uses Google Sans, matching the font family declared in VizWork. Variable font files (weights 400–700, Latin and Latin Extended) are bundled in `public/fonts` and loaded locally through `src/styles/fonts.scss`. The font is distributed under the SIL Open Font License; its license is included in `public/fonts/OFL.txt`. Source: https://github.com/googlefonts/googlesans and Google Fonts.

```text
src/
  api/contracts.ts        # HTTP response/request types from the architecture contract
  api/client.ts           # Mock/live transport, authentication headers, error parsing
  api/adapters.ts         # HTTP DTO to session/chat display models
  components/FileUpload.tsx # Independent upload UI; onUpload/onUploaded callbacks
  components/             # Shared navigation, icons, and source drawer
  context/AuthContext.tsx # In-memory authentication state
  mocks/data.ts           # Fictional sample documents
  mocks/handlers.ts       # Isolated transport instances, reset, scenario injection
  pages/                  # LoginPage, AssistantPage, DocumentsPage
  styles/main.scss        # Theme, components, and responsive layouts
  types.ts                # Frontend display models
  uploadPolicy.ts         # Shared file validation and MIME normalization
  test/                   # Test setup and literal contract fixtures
```

For isolated test scenarios, create a transport with `createMockTransport({ latencyMs: 0, searchLatencyMs: 0 })`, pass its `handler` to `createApiClient({ mode: "mock", mockTransport: transport.handler })`, and call `reset()` after each test. `next(path, "server-error" | "offline" | "empty")` injects a one-request scenario. Empty scenarios apply to search and document listing. Processing timers are also cleared by reset.

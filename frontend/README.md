# Enterprise RAG frontend

React, TypeScript, Vite and SCSS frontend for the enterprise knowledge assistant.

## Run

From this directory:

    npm install
    npm run dev

Open http://localhost:5173. Run npm run check for tests, TypeScript and the
production build. Live API mode is the default. Copy .env.example to .env.local
and set VITE_API_MODE=mock for an independent demo; restart Vite after changes.

## Sprint 4

- Upload with a default Level 1 permission selector.
- Document search, server pagination/sorting/filters, details, permission updates,
  re-indexing and confirmed deletion using backend-provided available_actions.
- Saved conversation history, restore with ordered messages/citations and delete.
- Citation page/line coordinates and unavailable-source states.
- Admin-only development scoring diagnostics; production hides the inspector.
- User / Staff / Admin shortcuts with password demo123. For existing demo emails,
  staff@enterprise.local maps to user, manager@enterprise.local to staff and
  executive@enterprise.local to admin.

Routes use HashRouter: /#/login, /#/assistant and /#/documents. Login is in memory.
Saved history is loaded from the backend after signing in. Mock catalog/history
are in memory and reset when the page fully reloads.

The current backend has login/upload/search but still needs the Sprint 4
document catalog, permission, debug and conversation implementation. Missing
APIs show explicit unavailable states. Unsupported conversation creation
switches to clearly marked search-only mode, using real retrieval in live mode.
Saved messages currently use server retrieval settings because the message
contract accepts content only. Search-only mode supports keyword/semantic/hybrid.

See [Sprint 4 frontend delivery](../docs/frontend-sprint-4.md) for API dependencies,
verification, compatibility details and the handoff checklist. The source of
truth for target endpoints is [api-spec.md](../docs/api-spec.md).

## Independent testing

    npm test
    npm run test:watch
    npm run check

Tests use Vitest and Testing Library with isolated mock transports. They do not
require FastAPI, Qdrant or an LLM, and do not establish server security or durable
storage correctness. The mock supports deterministic offline/server-error/empty
scenarios and simulated indexing. Text uploads support simple fixture matching;
PDF parsing, rendered PDF pages and real ranking are backend integration work.

Google Sans font files are bundled under public/fonts with their OFL license.

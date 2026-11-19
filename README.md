# Enterprise RAG Knowledge Assistant

Enterprise RAG Knowledge Assistant ingests internal PDF, Markdown, and text documents, performs role-aware semantic retrieval, and generates grounded answers with document and line citations.

## Technology Stack

- Frontend: React, TypeScript, Vite
- Backend: Python 3.11, FastAPI
- Databases: PostgreSQL, Qdrant
- Retrieval: vector search and BM25 hybrid retrieval
- Answer generation: Ollama or OpenAI API
- Deployment: Docker Compose

## Services and Ports

| Service | URL or port | Description |
| --- | --- | --- |
| Frontend | http://localhost:5173 | Web application |
| Backend API | http://localhost:8000 | FastAPI backend |
| Swagger | http://localhost:8000/docs | API documentation |
| Health check | http://localhost:8000/health | Backend and database status |
| Qdrant | http://localhost:6333/dashboard | Vector database dashboard |
| PostgreSQL | localhost:5433 | Database |
| Ollama | http://localhost:11434 | Local model API, optional |

## Quick Start with Docker

Docker Compose is the recommended deployment method.

### 1. Create the environment file

Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

Linux or macOS:

```bash
cp .env.example .env
```

Do not commit `.env` or real API keys.

### 2. Start without local Ollama

Use this mode on machines without NVIDIA GPU support or when users prefer only an online model:

```bash
docker compose up -d
```

Set cloud credentials in `.env`:

```env
LLM_MODE=cloud
LLM_CLOUD_FALLBACK=true
OPENAI_API_KEY=YOUR_OPENAI_API_KEY
OPENAI_MODEL=gpt-4.1-mini
LLM_TIMEOUT_SECONDS=30
```

### 3. Start with local Ollama

On a machine with NVIDIA GPU support:

```bash
docker compose --profile local-llm up -d
```

This profile starts Ollama and downloads the default model:

```text
qwen2.5:7b-instruct-q4_K_M
```

Recommended `.env` configuration:

```env
LLM_MODE=auto
LLM_LOCAL_ENABLED=auto
LLM_CLOUD_FALLBACK=true
OLLAMA_BASE_URL=http://ollama:11434/v1
OLLAMA_MODEL=qwen2.5:7b-instruct-q4_K_M
OPENAI_API_KEY=YOUR_OPENAI_API_KEY
OPENAI_MODEL=gpt-4.1-mini
LLM_TIMEOUT_SECONDS=30
```

The default Docker configuration has been tested with an NVIDIA GeForce RTX 4060 Laptop GPU and the Q4_K_M 7B model.

## Answer Generation Routing

The backend uses the following routing behavior:

| Setting | Behavior |
| --- | --- |
| `LLM_MODE=auto` | Prefer reachable local Ollama, then fall back to the cloud API |
| `LLM_MODE=local` | Use only local Ollama |
| `LLM_MODE=cloud` | Use only the configured cloud API |
| `LLM_MODE=none` | Disable answer generation |
| `LLM_LOCAL_ENABLED=true` | Force local Ollama attempts |
| `LLM_LOCAL_ENABLED=false` | Skip local Ollama |
| `LLM_LOCAL_ENABLED=auto` | Probe Ollama; fall back to NVIDIA GPU detection if it is unavailable |
| `LLM_CLOUD_FALLBACK=false` | Do not automatically call the cloud API after a local failure |

Local and cloud providers share the same grounded-answer prompt and return concise answers based only on authorized retrieved excerpts.

If no provider is available, the backend returns a clear service error rather than fabricating an answer.

## Local Ollama Management

List downloaded models:

```bash
curl http://localhost:11434/api/tags
```

Pull another model:

```bash
docker exec erag-ollama ollama pull qwen2.5:7b-instruct-q4_K_M
```

Set it in `.env`:

```env
OLLAMA_MODEL=MODEL_NAME
```

Then restart the backend:

```bash
docker compose up -d --build backend
```

Stop local LLM containers:

```bash
docker compose --profile local-llm down ollama ollama-init
```

Stop the complete Docker stack:

```bash
docker compose down
```

To remove persistent databases and downloaded Ollama models:

```bash
docker compose down -v
```

## Manual Python and Frontend Development

The full Docker stack is the recommended setup. For local development outside Docker:

### Backend

Requires Python 3.11:

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r backend/requirements.txt
python -m uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

PostgreSQL and Qdrant must be available, and the `.env` database URL must use the host ports:

```env
DATABASE_URL=postgresql+psycopg://erag:erag_local@localhost:5433/erag
QDRANT_HOST=localhost
QDRANT_PORT=6333
```

### Frontend

Requires Node.js and npm:

```bash
cd frontend
npm install
npm run dev
```

Frontend: http://localhost:5173

## Testing

Backend routing tests:

```bash
docker compose exec backend python -m unittest backend.tests.test_answer_generation_service -v
```

Frontend tests:

```bash
cd frontend
npm test -- --run
npm run build
```

## Troubleshooting

### Ollama does not appear in Docker

Start the project with the local profile:

```bash
docker compose --profile local-llm up -d
```

The Ollama service is intentionally not started by plain `docker compose up -d`.

### Ollama uses CPU instead of GPU

Verify Docker Desktop can see the NVIDIA GPU and check:

```bash
nvidia-smi
docker compose config
```

For CPU-only machines, use:

```env
LLM_MODE=cloud
LLM_LOCAL_ENABLED=false
OPENAI_API_KEY=YOUR_OPENAI_API_KEY
```

Then start normally:

```bash
docker compose up -d
```

### Cloud API is not configured

Set `OPENAI_API_KEY` in `.env`, or set:

```env
LLM_MODE=none
```

### Rebuild after code changes

```bash
docker compose up -d --build
```

For the local Ollama profile:

```bash
docker compose --profile local-llm up -d --build
```

## Documentation

- [API specification](docs/api-spec.md)
- [RBAC security](docs/rbac-security.md)
- [Sprint 4 acceptance](docs/sprint-4-acceptance.md)
- [Architecture and integration documentation](docs/)

## Team

- Ruolin Wang: Project Manager and Lead Architect
- Yen-Jui (Ray) Liang: Backend and RAG AI Engineer
- Yunting Ma: Full-Stack and Frontend Lead Engineer

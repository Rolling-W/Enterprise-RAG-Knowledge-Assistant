# Enterprise RAG Knowledge Assistant

An enterprise-grade AI knowledge management and retrieval platform designed to securely index, search, and synthesize internal multi-format documentation with vector-level Role-Based Access Control (RBAC) and interactive page/line citations.

## 🔗 Quick Links
- **Jira Management Board**: [Jira Board](https://ruolinw95.atlassian.net/jira/software/projects/ERAG/boards/1)
- **Course**: CS Capstone Project - Clark University

## 👥 Team Members & Roles
- **Ruolin Wang**: Project Manager & Lead Architect
- **Yen-Jui (Ray) Liang**: Backend & RAG AI Engineer
- **Yunting Ma**: Full-Stack & Frontend Lead Engineer

## 🛠️ Tech Stack
- **Backend**: Python 3.11, FastAPI, Qdrant Vector DB, Rank-BM25, LangChain
- **Frontend**: React.js, TypeScript, Tailwind CSS, Vite
- **DevOps**: Docker, Docker Compose, GitHub Actions

## 🧩 Project Goals
- Enable secure enterprise document ingestion from PDF, Markdown, and text-based files
- Build a semantic retrieval pipeline with reranking and grounded citations
- Support role-aware search experiences for different user groups
- Deliver a production-ready local development scaffold for demo and future iteration

## 🏗️ Repository Structure
```text
Enterprise-RAG-Knowledge-Assistant/
├── README.md
├── .gitignore
├── .env.example
├── docker-compose.yml
├── docs/
│   ├── architecture.png
│   └── api-spec.md
├── backend/
│   ├── main.py
│   ├── requirements.txt
│   └── Dockerfile
└── frontend/
    ├── package.json
    ├── src/
    │   ├── App.tsx
    │   └── main.tsx
    └── Dockerfile
```


## 🚀 Quick Start (Local Setup)


### 1. Install Dependencies

Requires Python 3.11, Node.js/npm, and Docker.

```bash
# Clone the repository
git clone https://github.com/Rolling-W/Enterprise-RAG-Knowledge-Assistant.git
cd Enterprise-RAG-Knowledge-Assistant

python3.11 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt

cd frontend
npm install
cd ..
```


### 2. Configure Environment

```bash
cp .env.example .env
```

Edit `.env` and replace `YOUR_OPENAI_API_KEY` with your own OpenAI API key.

### 3. Start PostgreSQL & Qdrant

```bash
docker compose up -d postgres qdrant
```

### 4. Initialize Databases

Load environment variables in the terminal:

```bash
set -a
source .env
set +a
```

Run database migrations and initialize Qdrant:

```bash
alembic upgrade head
python -m backend.init_qdrant
```

### 5. Start Backend

In the same terminal:

```bash
python -m uvicorn backend.main:app --reload
```

Backend: http://localhost:8000

### 6. Start Frontend

Open another terminal:

```bash
cd frontend
npm run dev
```

Frontend: http://localhost:5173

Qdrant Dashboard: http://localhost:6333/dashboard

### Notes

- Never commit `.env` or real API keys.
- Run `alembic upgrade head` after pulling database schema changes.
- OpenAI API access is required for LLM-generated answers.
- Department-based document access control is pending Sprint 5 policy alignment.


## 🔍 Sample API

```http
GET /health
POST /api/v1/auth/login
POST /api/v1/upload
POST /api/v1/search
```

## 📄 Documentation
- See [docs/api-spec.md](docs/api-spec.md) for the REST interface contract.
- See [docs/rbac-security.md](docs/rbac-security.md) for the Sprint 4 permission model.
- See [docs/sprint-4-acceptance.md](docs/sprint-4-acceptance.md) for acceptance cases and the integration snapshot.
- Once the backend is running, use the generated [Swagger UI](http://localhost:8000/docs)
  or [OpenAPI JSON](http://localhost:8000/openapi.json) as the executable contract.
- Architecture diagrams and planning notes are kept under the [docs](docs) directory.

## ✅ Assignment 3 Scaffold Status
This repository is initialized as a clean engineering scaffold for the course assignment, with:
- a structured project layout
- a sample FastAPI backend
- a React + TypeScript frontend starter
- Docker-based local deployment support
- documentation and environment templates

## Sprint 1 Notes
- Initial backend and frontend scaffold prepared for assignment review.
- Docker Compose and sample API routes are included for local demo.
- Repository structure follows a clear engineering workflow suitable for future feature development.

## 🤝 Contributing
This project is being developed by the team listed above. Contributions should follow a clear PR workflow and maintain a clean engineering structure.

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

```bash
# Clone the repository
git clone https://github.com/Rolling-W/Enterprise-RAG-Knowledge-Assistant.git
cd Enterprise-RAG-Knowledge-Assistant

# Run the full stack with Docker Compose
docker compose up --build
```

Once the stack is up:
- Backend API: http://localhost:8000
- Frontend UI: http://localhost:5173
- Qdrant Dashboard: http://localhost:6333/dashboard

## 🔍 Sample API

```http
GET /health
POST /api/v1/search
```

## 📄 Documentation
- See [docs/api-spec.md](docs/api-spec.md) for the REST interface contract.
- Architecture diagrams and planning notes are kept under the [docs](docs) directory.

## ✅ Assignment 3 Scaffold Status
This repository is initialized as a clean engineering scaffold for the course assignment, with:
- a structured project layout
- a sample FastAPI backend
- a React + TypeScript frontend starter
- Docker-based local deployment support
- documentation and environment templates

## 🤝 Contributing
This project is being developed by the team listed above. Contributions should follow a clear PR workflow and maintain a clean engineering structure.

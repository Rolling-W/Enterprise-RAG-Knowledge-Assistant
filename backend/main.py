from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="Enterprise RAG Knowledge Assistant API",
    version="1.0.0",
    description="Scaffold backend for enterprise knowledge retrieval and RAG demo"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def read_root():
    return {"message": "Enterprise RAG API is running"}


@app.get("/health")
def health_check():
    return {"status": "healthy", "database": "Qdrant Ready"}


@app.post("/api/v1/search")
def mock_search(query: str, user_role: str = "Standard"):
    return {
        "query": query,
        "user_role": user_role,
        "results": [
            {
                "doc_id": "doc_001",
                "title": "Employee_Handbook.pdf",
                "score": 0.92,
                "content": "Sample retrieved chunk text for internal enterprise policy and onboarding guidance.",
                "citation": {"page": 12, "line": 45},
            }
        ],
    }

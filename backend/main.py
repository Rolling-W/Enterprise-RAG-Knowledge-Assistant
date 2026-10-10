import os
from datetime import datetime, timedelta, timezone
from typing import Annotated
from uuid import uuid4

import jwt
from fastapi import Depends, FastAPI, File, HTTPException, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import InvalidTokenError
from pydantic import BaseModel, Field

try:
    from .qdrant_schema import COLLECTION_NAME
except ImportError:
    from qdrant_schema import COLLECTION_NAME


class ErrorResponse(BaseModel):
    detail: str


class UserSummary(BaseModel):
    user_id: str
    username: str
    role: str
    department: str
    clearance: int = Field(ge=1, le=3)


class TokenResponse(BaseModel):
    access_token: str = Field(description="Signed JWT for the Authorization header")
    token_type: str = "bearer"
    expires_in: int = Field(description="Token lifetime in seconds")
    user: UserSummary


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, examples=["demo@enterprise.local"])
    password: str = Field(min_length=1, examples=["password"])


class AuthenticatedUser(UserSummary):
    permissions: list[str]


class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=500, examples=["employee benefits"])
    top_k: int = Field(default=5, ge=1, le=20)
    search_mode: str = Field(default="hybrid", pattern="^(hybrid|semantic|keyword)$")
    filters: dict[str, str] = Field(default_factory=dict)


class Citation(BaseModel):
    page: int | None = Field(default=None, ge=1)
    line_start: int | None = Field(default=None, ge=1)
    line_end: int | None = Field(default=None, ge=1)


class Chunk(BaseModel):
    """Shared ingestion, retrieval, and frontend display representation."""

    chunk_id: str
    document_id: str
    title: str
    content: str
    content_type: str
    department_id: str
    clearance_level: int = Field(ge=1, le=3)
    citation: Citation

    def to_qdrant_payload(self) -> dict[str, str | int | None]:
        """Flatten the API chunk representation into the Qdrant payload shape."""
        return {
            "chunk_id": self.chunk_id,
            "document_id": self.document_id,
            "department_id": self.department_id,
            "clearance_level": self.clearance_level,
            "content_type": self.content_type,
            "title": self.title,
            "content": self.content,
            "page": self.citation.page,
            "line_start": self.citation.line_start,
            "line_end": self.citation.line_end,
        }


class SearchResult(Chunk):
    score: float = Field(ge=0, le=1)


class SearchResponse(BaseModel):
    query: str
    search_mode: str
    results: list[SearchResult]
    total: int
    request_id: str


class UploadResponse(BaseModel):
    document_id: str
    filename: str
    content_type: str
    size_bytes: int = Field(ge=0)
    status: str = "queued"
    message: str


class HealthResponse(BaseModel):
    status: str
    database: str


JWT_SECRET = os.getenv("JWT_SECRET", "development-only-secret-change-me-32")
JWT_ISSUER = os.getenv("JWT_ISSUER", "enterprise-rag-api")
JWT_ALGORITHM = "HS256"
ROLE_PERMISSIONS = {
    "Executive": (3, ["document:read", "document:upload", "document:manage"]),
    "Department Manager": (2, ["document:read", "document:upload"]),
    "Standard Staff": (1, ["document:read"]),
}
DEMO_USERS = {
    "executive@enterprise.local": ("Executive", "Executive"),
    "manager@enterprise.local": ("Department Manager", "General"),
}

app = FastAPI(
    title="Enterprise RAG Knowledge Assistant API",
    version="1.0.0",
    description="REST contract for the React client and FastAPI backend.",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
bearer_scheme = HTTPBearer(auto_error=False)


def create_access_token(username: str) -> tuple[str, AuthenticatedUser]:
    role, department = DEMO_USERS.get(username, ("Standard Staff", "General"))
    clearance, permissions = ROLE_PERMISSIONS[role]
    user = AuthenticatedUser(
        user_id=f"user_{uuid4().hex[:12]}",
        username=username,
        role=role,
        department=department,
        clearance=clearance,
        permissions=permissions,
    )
    now = datetime.now(timezone.utc)
    claims = {
        "iss": JWT_ISSUER,
        "sub": user.user_id,
        "username": user.username,
        "role": user.role,
        "department": user.department,
        "clearance": user.clearance,
        "permissions": user.permissions,
        "iat": now,
        "exp": now + timedelta(hours=1),
        "jti": uuid4().hex,
    }
    return jwt.encode(claims, JWT_SECRET, algorithm=JWT_ALGORITHM), user


def require_user(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None, Depends(bearer_scheme)
    ],
) -> AuthenticatedUser:
    if credentials is None:
        raise HTTPException(status_code=401, detail="Bearer token required")
    try:
        claims = jwt.decode(
            credentials.credentials,
            JWT_SECRET,
            algorithms=[JWT_ALGORITHM],
            issuer=JWT_ISSUER,
        )
        return AuthenticatedUser(
            user_id=claims["sub"],
            username=claims["username"],
            role=claims["role"],
            department=claims["department"],
            clearance=claims["clearance"],
            permissions=claims["permissions"],
        )
    except (InvalidTokenError, KeyError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=401, detail="Invalid or expired bearer token") from exc


def require_upload_permission(
    user: Annotated[AuthenticatedUser, Depends(require_user)],
) -> AuthenticatedUser:
    if "document:upload" not in user.permissions:
        raise HTTPException(status_code=403, detail="Document upload permission required")
    return user


@app.get("/", include_in_schema=False)
def read_root() -> dict[str, str]:
    return {"message": "Enterprise RAG API is running"}


@app.get("/health", response_model=HealthResponse, tags=["system"])
def health_check() -> HealthResponse:
    return HealthResponse(status="healthy", database=f"Qdrant collection: {COLLECTION_NAME}")


@app.post(
    "/api/v1/auth/login",
    response_model=TokenResponse,
    responses={401: {"model": ErrorResponse}},
    tags=["auth"],
)
def login(payload: LoginRequest) -> TokenResponse:
    if not payload.username.strip() or not payload.password.strip():
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token, user = create_access_token(payload.username)
    return TokenResponse(access_token=token, expires_in=3600, user=user)


@app.post(
    "/api/v1/upload",
    response_model=UploadResponse,
    status_code=status.HTTP_202_ACCEPTED,
    responses={400: {"model": ErrorResponse}, 401: {"model": ErrorResponse}, 403: {"model": ErrorResponse}},
    tags=["documents"],
)
async def upload_document(
    file: Annotated[UploadFile, File(description="PDF, Markdown, or plain text document")],
    user: Annotated[AuthenticatedUser, Depends(require_upload_permission)],
) -> UploadResponse:
    supported_types = {"application/pdf", "text/markdown", "text/plain"}
    if file.content_type not in supported_types:
        raise HTTPException(status_code=400, detail="Only PDF, Markdown, and plain text files are supported")
    content = await file.read()
    return UploadResponse(
        document_id=f"doc_{uuid4().hex[:12]}",
        filename=file.filename or "unnamed",
        content_type=file.content_type,
        size_bytes=len(content),
        message=f"Document queued for {user.department} with clearance {user.clearance}",
    )


@app.post(
    "/api/v1/search",
    response_model=SearchResponse,
    responses={401: {"model": ErrorResponse}},
    tags=["search"],
)
def search(
    payload: SearchRequest,
    user: Annotated[AuthenticatedUser, Depends(require_user)],
) -> SearchResponse:
    result = SearchResult(
        chunk_id="chunk_001",
        document_id="doc_001",
        title="Employee_Handbook.pdf",
        score=0.92,
        content="Sample retrieved chunk text for internal enterprise policy and onboarding guidance.",
        content_type="application/pdf",
        department_id="General",
        clearance_level=1,
        citation=Citation(page=12, line_start=45, line_end=49),
    )
    results = [result] if user.clearance >= 1 else []
    return SearchResponse(
        query=payload.query,
        search_mode=payload.search_mode,
        results=results[: payload.top_k],
        total=len(results),
        request_id=f"req_{uuid4().hex[:12]}",
    )

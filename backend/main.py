import os
from datetime import datetime, timedelta, timezone
from typing import Annotated, Literal
from uuid import NAMESPACE_URL, uuid4, uuid5
import logging

import jwt
from fastapi import Depends, FastAPI, File, Form, HTTPException, Query, UploadFile, status, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import InvalidTokenError
from pydantic import BaseModel, Field

from datetime import datetime
from sqlalchemy.orm import Session

from backend.database.connection import get_db
from backend.database.models import Document
from backend.rag_service import search_debug as retrieve_debug
from backend.services.answer_generation_service import generate_answer
from backend.services.conversation_service import (
    create_conversation,
    list_conversations,
    get_conversation,
    list_conversation_messages,
    list_conversation_citations,
    add_user_message,
    add_assistant_message,
    delete_conversation,
)
from backend.services.document_service import (
    create_document,
    update_document_status,
    list_searchable_document_ids,
    list_documents,
)
from backend.services.document_permission_service import (
    change_document_permission,
    DocumentNotClaimableError,
)
from backend.services.document_reindex_service import (
    claim_document_for_reindex,
    run_document_reindex,
)
from backend.services.document_delete_service import (
    delete_document,
    DocumentNotDeletableError,
)

try:
    from .qdrant_schema import COLLECTION_NAME, create_client
    from .rag_service import ingest, delete_document_points, search as retrieve
except ImportError:
    from qdrant_schema import COLLECTION_NAME, create_client
    from rag_service import ingest, delete_document_points, search as retrieve


logger = logging.getLogger(__name__)

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
    permission_level: int = Field(ge=1, le=3)
    citation: Citation

    def to_qdrant_payload(self) -> dict[str, str | int | None]:
        """Flatten the API chunk representation into the Qdrant payload shape."""
        return {
            "chunk_id": self.chunk_id,
            "document_id": self.document_id,
            "department_id": self.department_id,
            "permission_level": self.permission_level,
            "content_type": self.content_type,
            "title": self.title,
            "content": self.content,
            "page": self.citation.page,
            "line_start": self.citation.line_start,
            "line_end": self.citation.line_end,
        }


class SearchResult(Chunk):
    score: float = Field(
        description="Raw relevance score from the retrieval pipeline"
    )


class SearchResponse(BaseModel):
    query: str
    search_mode: str
    results: list[SearchResult]
    total: int
    request_id: str


class SearchDebugRequest(SearchRequest):
    """Search parameters with an additional debug candidate limit."""

    candidate_limit: int = Field(default=50, ge=1, le=100)


class SearchDebugScores(BaseModel):
    """Scores and ranks from individual retrieval stages."""

    bm25_raw: float | None = None
    bm25_rank: int | None = Field(default=None, ge=1)

    dense_raw: float | None = None
    dense_rank: int | None = Field(default=None, ge=1)

    fusion: float | None = None
    rerank: float | None = None
    final: float | None = None


class SearchDebugCandidate(BaseModel):
    """Authorized candidate with scoring details."""

    document_id: str
    chunk_id: str
    permission_level: int = Field(ge=1, le=3)
    scores: SearchDebugScores
    final_rank: int = Field(ge=1)


class SearchDebugResponse(BaseModel):
    """Debug response without document content."""

    query: str
    search_mode: str
    top_k: int
    candidates: list[SearchDebugCandidate]
    stages: list[str]
    timings_ms: dict[str, Annotated[float, Field(ge=0)]]
    request_id: str


class UploadResponse(BaseModel):
    document_id: str
    filename: str
    content_type: str
    size_bytes: int = Field(ge=0)
    status: str = "queued"
    message: str


class DocumentCreator(BaseModel):
    user_id: str
    display_name: str


class DocumentSummary(BaseModel):
    document_id: str
    filename: str
    title: str
    content_type: str
    size_bytes: int = Field(ge=0)
    permission_level: int = Field(ge=1, le=3)
    creator: DocumentCreator
    created_at: datetime
    updated_at: datetime
    status: Literal["processing", "indexed", "failed", "deleting"]
    available_actions: list[str]


class DocumentListResponse(BaseModel):
    items: list[DocumentSummary]
    total: int = Field(ge=0)
    page: int = Field(ge=1)
    page_size: int = Field(ge=1)
    total_pages: int = Field(ge=0)


class DocumentReindexResponse(BaseModel):
    document_id: str
    status: Literal["processing"]


class DocumentPermissionUpdateRequest(BaseModel):
    permission_level: int = Field(ge=1, le=3)


class HealthResponse(BaseModel):
    status: str
    database: str


class CreateConversationRequest(BaseModel):
    title: str | None = Field(default=None, max_length=255)


class ConversationResponse(BaseModel):
    conversation_id: str
    title: str | None
    created_at: datetime
    updated_at: datetime


class ConversationListResponse(BaseModel):
    items: list[ConversationResponse]
    total: int
    page: int
    page_size: int


class ConversationCitationResponse(BaseModel):
    document_id: str
    chunk_id: str
    title: str
    permission_level: int = Field(ge=1, le=3)
    page: int | None = None
    line_start: int | None = None
    line_end: int | None = None
    unavailable: bool | None = None


class ConversationMessageResponse(BaseModel):
    message_id: str
    sequence: int
    role: Literal["user", "assistant"]
    content: str
    created_at: datetime
    citations: list[ConversationCitationResponse]


class ConversationDetailResponse(ConversationResponse):
    owner_id: str
    messages: list[ConversationMessageResponse]


class AddMessageRequest(BaseModel):
    content: str = Field(min_length=1)


JWT_SECRET = os.getenv("JWT_SECRET", "development-only-secret-change-me-32")
JWT_ISSUER = os.getenv("JWT_ISSUER", "enterprise-rag-api")
JWT_ALGORITHM = "HS256"
ROLE_PERMISSIONS = {
    "Executive": (3, ["document:read", "document:upload", "document:manage"]),
    "Department Manager": (2, ["document:read", "document:upload"]),
    "Standard Staff": (1, ["document:read"]),
}
PRODUCT_ROLE_MAP = {
    "Executive": "admin",
    "Department Manager": "staff",
    "Standard Staff": "user",
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
        user_id=f"user_{uuid5(NAMESPACE_URL, f'enterprise-rag:{username}').hex}",
        username=username,
        role=PRODUCT_ROLE_MAP[role],
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


def require_read_permission(
    user: Annotated[AuthenticatedUser, Depends(require_user)],
) -> AuthenticatedUser:
    if "document:read" not in user.permissions:
        raise HTTPException(status_code=403, detail="Document read permission required")
    return user


def require_manage_permission(
    user: Annotated[AuthenticatedUser, Depends(require_user)],
) -> AuthenticatedUser:
    """Allow document management operations for admins only."""

    if (
        user.role != "admin"
        or "document:manage" not in user.permissions
    ):
        raise HTTPException(
            status_code=403,
            detail="Document management permission required",
        )

    return user


def document_to_summary(
    document: Document,
    *,
    available_actions: list[str],
) -> DocumentSummary:
    """Convert PostgreSQL document metadata to the shared API DTO."""

    return DocumentSummary(
        document_id=document.document_id,
        filename=document.filename,
        title=document.title,
        content_type=document.content_type,
        size_bytes=document.size_bytes,
        permission_level=document.permission_level,
        creator=DocumentCreator(
            user_id=document.creator_id,
            display_name=document.creator_display_name,
        ),
        created_at=document.created_at,
        updated_at=document.updated_at,
        status=document.status,
        available_actions=available_actions,
    )


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
    "/api/v1/conversations",
    response_model=ConversationResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["conversations"],
)
def create_conversation_endpoint(
    payload: CreateConversationRequest,
    current_user: AuthenticatedUser = Depends(require_user),
    db: Session = Depends(get_db),
) -> ConversationResponse:
    conversation = create_conversation(
        db,
        owner_id=current_user.user_id,
        title=payload.title,
    )

    return ConversationResponse(
        conversation_id=conversation.conversation_id,
        title=conversation.title,
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
    )


@app.get(
    "/api/v1/conversations",
    response_model=ConversationListResponse,
    tags=["conversations"],
)
def list_conversations_endpoint(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_user: AuthenticatedUser = Depends(require_user),
    db: Session = Depends(get_db),
) -> ConversationListResponse:
    conversations, total = list_conversations(
        db,
        owner_id=current_user.user_id,
        page=page,
        page_size=page_size,
    )

    return ConversationListResponse(
        items=[
            ConversationResponse(
                conversation_id=conversation.conversation_id,
                title=conversation.title,
                created_at=conversation.created_at,
                updated_at=conversation.updated_at,
            )
            for conversation in conversations
        ],
        total=total,
        page=page,
        page_size=page_size,
    )



@app.get(
    "/api/v1/conversations/{conversation_id}",
    response_model=ConversationDetailResponse,
    tags=["conversations"],
)
def get_conversation_endpoint(
    conversation_id: str,
    current_user: AuthenticatedUser = Depends(require_user),
    db: Session = Depends(get_db),
) -> ConversationDetailResponse:

    # Step 1: Verify conversation ownership.
    conversation = get_conversation(
        db,
        conversation_id=conversation_id,
        owner_id=current_user.user_id,
    )

    if conversation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found",
        )

    # Step 2: Restore messages and their saved citations.
    messages = list_conversation_messages(
        db,
        conversation_id=conversation_id,
        owner_id=current_user.user_id,
    )

    saved_citations = list_conversation_citations(
        db,
        conversation_id=conversation_id,
        owner_id=current_user.user_id,
    )

    # Step 3: Recheck current document permissions.
    allowed_document_ids = set()

    if saved_citations:
        allowed_document_ids = set(
            list_searchable_document_ids(
                db,
                clearance_level=current_user.clearance,
                department_id=current_user.department,
                is_admin=current_user.role == "admin",
            )
        )

    # Step 4: Group citations by their message ID.
    citations_by_message = {}

    for citation in saved_citations or []:
        is_available = citation.document_id in allowed_document_ids

        citation_response = ConversationCitationResponse(
            document_id=citation.document_id,
            chunk_id=citation.chunk_id,
            title=(
                citation.title
                if is_available
                else "Unavailable source"
            ),
            permission_level=citation.permission_level,
            page=citation.page,
            line_start=citation.line_start,
            line_end=citation.line_end,
            unavailable=not is_available,
        )

        citations_by_message.setdefault(
            citation.message_id, []
        ).append(citation_response)

    # Step 5: Return ordered messages with restored citations.
    return ConversationDetailResponse(
        conversation_id=conversation.conversation_id,
        owner_id=conversation.owner_id,
        title=conversation.title,
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
        messages=[
            ConversationMessageResponse(
                message_id=message.message_id,
                sequence=message.sequence,
                role=message.role,
                content=message.content,
                created_at=message.created_at,
                citations=citations_by_message.get(
                    message.message_id, []
                ),
            )
            for message in (messages or [])
        ],
    )



@app.post(
    "/api/v1/conversations/{conversation_id}/messages",
    response_model=ConversationMessageResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["conversations"],
)
def add_message_endpoint(
    conversation_id: str,
    payload: AddMessageRequest,
    current_user: AuthenticatedUser = Depends(require_user),
    db: Session = Depends(get_db),
) -> ConversationMessageResponse:

    if not payload.content.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Message content cannot be empty",
        )

    message = add_user_message(
        db,
        conversation_id=conversation_id,
        owner_id=current_user.user_id,
        content=payload.content,
    )

    if message is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found",
        )

    return ConversationMessageResponse(
        message_id=message.message_id,
        sequence=message.sequence,
        role="user",
        content=message.content,
        created_at=message.created_at,
        citations=[],
    )


@app.post(
    "/api/v1/conversations/{conversation_id}/generate",
    response_model=ConversationMessageResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["conversations"],
)
def generate_conversation_answer_endpoint(
    conversation_id: str,
    current_user: AuthenticatedUser = Depends(require_read_permission),
    db: Session = Depends(get_db),
) -> ConversationMessageResponse:

    # Step 1: Verify conversation ownership.
    conversation = get_conversation(
        db,
        conversation_id=conversation_id,
        owner_id=current_user.user_id,
    )

    if conversation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found",
        )

    # Step 2: Find the latest user message.
    messages = list_conversation_messages(
        db,
        conversation_id=conversation_id,
        owner_id=current_user.user_id,
    )

    if not messages or messages[-1].role != "user":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No unanswered user message found",
        )

    question = messages[-1].content.strip()

    if len(question) > 500:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Question exceeds the 500-character search limit",
        )

    # Step 3: Reuse the existing authorized Search Pipeline.
    search_response = search(
        payload=SearchRequest(
            query=question,
            top_k=5,
            search_mode="hybrid",
        ),
        user=current_user,
        db=db,
    )

    # Step 4: Build context from authorized search results.
    context_parts = []
    citations = []

    for index, result in enumerate(search_response.results, start=1):
        context_parts.append(
            f"[Source {index}]\n"
            f"Document: {result.title}\n"
            f"Content:\n{result.content}"
        )

        citations.append(
            {
                "document_id": result.document_id,
                "chunk_id": result.chunk_id,
                "title": result.title,
                "permission_level": result.permission_level,
                "page": result.citation.page,
                "line_start": result.citation.line_start,
                "line_end": result.citation.line_end,
            }
        )

    context = "\n\n---\n\n".join(context_parts)

    # Step 5: Generate a grounded answer.
    try:
        answer = generate_answer(
            question=question,
            context=context,
        )
    except Exception as exc:
        logger.exception("Answer generation failed")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Answer generation service is unavailable",
        ) from exc

    # Step 6: Persist the assistant message and retrieved sources.
    message = add_assistant_message(
        db,
        conversation_id=conversation_id,
        owner_id=current_user.user_id,
        content=answer,
        citations=citations,
    )

    if message is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found",
        )

    # Step 7: Return the persisted assistant message.
    return ConversationMessageResponse(
        message_id=message.message_id,
        sequence=message.sequence,
        role="assistant",
        content=message.content,
        created_at=message.created_at,
        citations=[
            ConversationCitationResponse(
                **citation,
                unavailable=False,
            )
            for citation in citations
        ],
    )


@app.delete(
    "/api/v1/conversations/{conversation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["conversations"],
)
def delete_conversation_endpoint(
    conversation_id: str,
    current_user: AuthenticatedUser = Depends(require_user),
    db: Session = Depends(get_db),
) -> None:

    deleted = delete_conversation(
        db,
        conversation_id=conversation_id,
        owner_id=current_user.user_id,
    )

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found",
        )


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
    db: Annotated[Session, Depends(get_db)],
    permission_level: Annotated[int, Form(ge=1, le=3)] = 1,
) -> UploadResponse:
    supported_types = {
        "application/pdf",
        "text/markdown",
        "text/plain",
    }

    if file.content_type not in supported_types:
        raise HTTPException(
            status_code=400,
            detail="Only PDF, Markdown, and plain text files are supported",
        )

    content = await file.read()
    if not content:
        raise HTTPException(
            status_code=400,
            detail="Uploaded document is empty",
        )

    if user.role == "staff" and permission_level != 1:
        raise HTTPException(
            status_code=403,
            detail="Staff can only upload Level 1 documents",
        )

    document_id = f"doc_{uuid4().hex[:12]}"
    filename = file.filename or "unnamed"

    # Step 1: Save metadata and original content in PostgreSQL.
    try:
        create_document(
            db,
            document_id=document_id,
            filename=filename,
            title=filename,
            content_type=file.content_type,
            content=content,
            department_id=user.department,
            permission_level=permission_level,
            creator_id=user.user_id,
            creator_display_name=user.username,
        )
    except Exception as exc:
        logger.exception("Failed to save document %s", document_id)
        raise HTTPException(
            status_code=503,
            detail="Document metadata storage is unavailable",
        ) from exc

    # Step 2: Index the document in Qdrant.
    client = None
    indexing_completed = False

    try:
        client = create_client()

        chunk_count = ingest(
            client,
            document_id=document_id,
            filename=filename,
            content_type=file.content_type,
            content=content,
            department_id=user.department,
            permission_level=permission_level,
        )

        indexing_completed = True

        # Step 3: Mark the document as indexed.
        update_document_status(
            db,
            document_id=document_id,
            status="indexed",
        )

    except Exception as exc:
        logger.exception("Document indexing failed: %s", document_id)

        # Remove any Qdrant points written before the failure.
        if client is not None:
            try:
                delete_document_points(
                    client,
                    document_id=document_id,
                )
            except Exception:
                logger.exception(
                    "Qdrant cleanup failed for %s",
                    document_id,
                )

        # Preserve the document record for failure inspection/retry.
        try:
            update_document_status(
                db,
                document_id=document_id,
                status="failed",
            )
        except Exception:
            logger.exception(
                "Failed to update status for %s",
                document_id,
            )

        if not indexing_completed and isinstance(
            exc, (RuntimeError, ValueError)
        ):
            raise HTTPException(
                status_code=400,
                detail=str(exc),
            ) from exc

        raise HTTPException(
            status_code=503,
            detail="Document indexing or storage is unavailable",
        ) from exc

    return UploadResponse(
        document_id=document_id,
        filename=filename,
        content_type=file.content_type,
        size_bytes=len(content),
        status="indexed",
        message=(
            f"Indexed {chunk_count} chunks for "
            f"{user.department} with permission level "
            f"{permission_level}"
        ),
    )


@app.get(
    "/api/v1/documents",
    response_model=DocumentListResponse,
    tags=["documents"],
)
def list_documents_endpoint(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    sort_by: Literal[
        "created_at",
        "updated_at",
        "filename",
        "permission_level",
        "status",
    ] = "created_at",
    sort_order: Literal["asc", "desc"] = "desc",
    permission_level: int | None = Query(
        default=None, ge=1, le=3
    ),
    creator_id: str | None = None,
    status: Literal[
        "processing", "indexed", "failed", "deleting"
    ] | None = None,
    q: str | None = None,
    current_user: AuthenticatedUser = Depends(
        require_read_permission
    ),
    db: Session = Depends(get_db),
) -> DocumentListResponse:
    documents, total = list_documents(
        db,
        clearance_level=current_user.clearance,
        department_id=current_user.department,
        is_admin=current_user.role == "admin",
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_order=sort_order,
        permission_level=permission_level,
        creator_id=creator_id,
        status=status,
        q=q,
    )

    items = []
    for document in documents:
        actions = []

        if document.status == "indexed":
            actions.append("read")

        if (
            current_user.role == "admin"
            and document.status in ("indexed", "failed")
            and document.permission_update_target is None
        ):
            actions.append("reindex")

        items.append(
            document_to_summary(
                document,
                available_actions=actions,
            )
        )

    return DocumentListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=(total + page_size - 1) // page_size,
    )


@app.get(
    "/api/v1/documents/{document_id}",
    response_model=DocumentSummary,
    tags=["documents"],
)
def get_document_detail(
    document_id: str,
    current_user: AuthenticatedUser = Depends(
        require_read_permission
    ),
    db: Session = Depends(get_db),
) -> DocumentSummary:
    """Return document metadata only when visible to the caller."""

    document = db.get(Document, document_id)

    if document is None:
        raise HTTPException(
            status_code=404,
            detail="Document not found",
        )

    # Permission level must be within the caller's clearance.
    if document.permission_level > current_user.clearance:
        raise HTTPException(
            status_code=404,
            detail="Document not found",
        )

    # Non-admin users can only access their own department
    # or documents shared with Global.
    if current_user.role != "admin":
        if document.department_id not in (
            current_user.department,
            "Global",
        ):
            raise HTTPException(
                status_code=404,
                detail="Document not found",
            )

        # Do not expose metadata while permissions are changing.
        if document.permission_update_target is not None:
            raise HTTPException(
                status_code=404,
                detail="Document not found",
            )

    actions = []

    if document.status == "indexed":
        actions.append("read")

    if (
        current_user.role == "admin"
        and document.status in ("indexed", "failed")
        and document.permission_update_target is None
    ):
        actions.append("reindex")

    return document_to_summary(
        document,
        available_actions=actions,
    )


@app.post(
    "/api/v1/documents/{document_id}/reindex",
    response_model=DocumentReindexResponse,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["documents"],
)
def reindex_document_endpoint(
    document_id: str,
    background_tasks: BackgroundTasks,
    user: Annotated[
        AuthenticatedUser,
        Depends(require_manage_permission),
    ],
    db: Annotated[Session, Depends(get_db)],
) -> DocumentReindexResponse:
    """Schedule document reindexing (admin only)."""

    document = db.get(Document, document_id)

    if document is None:
        raise HTTPException(
            status_code=404,
            detail="Document not found",
        )

    try:
        claimed = claim_document_for_reindex(
            db,
            document_id=document_id,
        )
    except Exception as exc:
        logger.exception(
            "Failed to schedule document reindex: %s",
            document_id,
        )
        raise HTTPException(
            status_code=503,
            detail="Document reindex service is unavailable",
        ) from exc

    if not claimed:
        raise HTTPException(
            status_code=409,
            detail="Document is not available for reindexing",
        )

    background_tasks.add_task(
        run_document_reindex,
        document_id,
    )

    return DocumentReindexResponse(
        document_id=document_id,
        status="processing",
    )


@app.delete(
    "/api/v1/documents/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["documents"],
)
def delete_document_endpoint(
    document_id: str,
    user: Annotated[
        AuthenticatedUser,
        Depends(require_manage_permission),
    ],
    db: Annotated[Session, Depends(get_db)],
) -> None:
    """Permanently delete a document (admin only)."""

    document = db.get(Document, document_id)

    if document is None:
        raise HTTPException(
            status_code=404,
            detail="Document not found",
        )

    try:
        delete_document(
            db,
            document_id=document_id,
        )

    except DocumentNotDeletableError as exc:
        raise HTTPException(
            status_code=409,
            detail="Document is not available for deletion",
        ) from exc

    except Exception as exc:
        logger.exception(
            "Document deletion failed: %s",
            document_id,
        )

        raise HTTPException(
            status_code=503,
            detail="Document deletion is unavailable",
        ) from exc


@app.patch(
    "/api/v1/documents/{document_id}/permissions",
    response_model=DocumentSummary,
)
def update_document_permissions(
    document_id: str,
    payload: DocumentPermissionUpdateRequest,
    user: Annotated[
        AuthenticatedUser,
        Depends(require_manage_permission),
    ],
    db: Annotated[Session, Depends(get_db)],
) -> DocumentSummary:
    """Update a document's permission level (admin only)."""

    try:
        updated_document = change_document_permission(
            db,
            create_client(),
            document_id=document_id,
            new_permission_level=payload.permission_level,
        )

    except DocumentNotClaimableError as exc:
        try:
            document = db.get(Document, document_id)
        except Exception as db_exc:
            logger.exception("Document lookup failed: %s", document_id)
            raise HTTPException(
                status_code=503,
                detail="Document service is unavailable",
            ) from db_exc

        if document is None:
            raise HTTPException(
                status_code=404,
                detail="Document not found",
            ) from exc

        raise HTTPException(
            status_code=409,
            detail="Document is not available for permission update",
        ) from exc

    except Exception as exc:
        logger.exception(
            "Document permission update failed: %s",
            document_id,
        )
        raise HTTPException(
            status_code=503,
            detail="Document permission update is unavailable",
        ) from exc

    return document_to_summary(
        updated_document,
        available_actions=["read", "reindex"],
    )


@app.post(
    "/api/v1/search",
    response_model=SearchResponse,
    responses={401: {"model": ErrorResponse}},
    tags=["search"],
)
def search(
    payload: SearchRequest,
    user: Annotated[AuthenticatedUser, Depends(require_read_permission)],
    db: Annotated[Session, Depends(get_db)],
) -> SearchResponse:
    department_filter = payload.filters.get("department")
    if department_filter and user.role != "admin" and department_filter not in {user.department, "Global"}:
        raise HTTPException(status_code=403, detail="Department filter is outside your access scope")

    try:
        # Step 1: PostgreSQL determines which documents are searchable.
        allowed_document_ids = list_searchable_document_ids(
            db,
            clearance_level=user.clearance,
            department_id=user.department,
            is_admin=user.role == "admin",
            department_filter=department_filter,
        )

        # Step 2: Search Qdrant only within the authorized documents.
        if allowed_document_ids:
            points = retrieve(
                create_client(),
                query=payload.query,
                top_k=payload.top_k,
                mode=payload.search_mode,
                clearance_level=user.clearance,
                department_id=user.department,
                is_executive=user.role == "admin",
                department_filter=department_filter,
                allowed_document_ids=allowed_document_ids,
            )
        else:
            points = []

    except Exception as exc:
        logger.exception("Document search failed")
        raise HTTPException(
            status_code=503,
            detail="Search service is unavailable",
        ) from exc

    results = []
    for point in points:
        data = point.payload or {}
        results.append(
            SearchResult(
                chunk_id=str(data["chunk_id"]),
                document_id=str(data["document_id"]),
                title=str(data.get("title", "")),
                score=float(point.score),
                content=str(data.get("content", "")),
                content_type=str(data.get("content_type", "text/plain")),
                department_id=str(data["department_id"]),
                permission_level=int(data["permission_level"]),
                citation=Citation(
                    page=data.get("page"),
                    line_start=data.get("line_start"),
                    line_end=data.get("line_end"),
                ),
            )
        )
    return SearchResponse(
        query=payload.query,
        search_mode=payload.search_mode,
        results=results,
        total=len(results),
        request_id=f"req_{uuid4().hex[:12]}",
    )


@app.post(
    "/api/v1/search/debug",
    response_model=SearchDebugResponse,
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
    },
    tags=["search"],
)
def search_debug_endpoint(
    payload: SearchDebugRequest,
    user: Annotated[AuthenticatedUser, Depends(require_manage_permission)],
    db: Annotated[Session, Depends(get_db)],
) -> SearchDebugResponse:
    """Return scoring details for authorized search candidates (admin only)."""
    from time import perf_counter

    started = perf_counter()

    department_filter = payload.filters.get("department")

    try:
        # PostgreSQL determines which documents are searchable.
        auth_started = perf_counter()

        allowed_document_ids = list_searchable_document_ids(
            db,
            clearance_level=user.clearance,
            department_id=user.department,
            is_admin=user.role == "admin",
            department_filter=department_filter,
        )

        authorization_ms = (
            perf_counter() - auth_started
        ) * 1000

        # Qdrant searches only the authorized document IDs.
        if allowed_document_ids:
            client = create_client()
            try:
                candidates, stages, timings = retrieve_debug(
                    client,
                    query=payload.query,
                    top_k=payload.top_k,
                    candidate_limit=payload.candidate_limit,
                    mode=payload.search_mode,
                    clearance_level=user.clearance,
                    department_id=user.department,
                    is_executive=user.role == "admin",
                    department_filter=department_filter,
                    allowed_document_ids=allowed_document_ids,
                )
            finally:
                client.close()
        else:
            candidates = []
            stages = []
            timings = {
                "authorization_filter": 0.0,
                "bm25": 0.0,
                "dense": 0.0,
                "fusion": 0.0,
                "rerank": 0.0,
            }

        timings["authorization_filter"] += authorization_ms
        timings["total"] = (perf_counter() - started) * 1000

    except Exception as exc:
        logger.exception("Search Debug failed")
        raise HTTPException(
            status_code=503,
            detail="Search Debug service is unavailable",
        ) from exc

    return SearchDebugResponse(
        query=payload.query,
        search_mode=payload.search_mode,
        top_k=payload.top_k,
        candidates=candidates,
        stages=stages,
        timings_ms=timings,
        request_id=f"req_{uuid4().hex[:12]}",
    )

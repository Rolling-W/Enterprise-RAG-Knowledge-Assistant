from sqlalchemy import func, or_, select, update
from sqlalchemy.orm import Session

from backend.database.models import Document, DocumentSource


def create_document(
    db: Session,
    *,
    document_id: str,
    filename: str,
    title: str,
    content_type: str,
    content: bytes,
    department_id: str,
    permission_level: int,
    creator_id: str,
    creator_display_name: str,
) -> Document:
    """Store document metadata and original content atomically."""

    if permission_level not in (1, 2, 3):
        raise ValueError("Permission level must be 1, 2, or 3")

    if not content:
        raise ValueError("Document content cannot be empty")

    document = Document(
        document_id=document_id,
        filename=filename,
        title=title,
        content_type=content_type,
        size_bytes=len(content),
        department_id=department_id,
        permission_level=permission_level,
        creator_id=creator_id,
        creator_display_name=creator_display_name,
        status="processing",
    )

    source = DocumentSource(
        document_id=document_id,
        source_content=content,
    )

    try:
        db.add(document)
        db.add(source)
        db.commit()
        db.refresh(document)
    except Exception:
        db.rollback()
        raise

    return document


def update_document_status(
    db: Session,
    *,
    document_id: str,
    status: str,
) -> Document:
    """Update the indexing status of an existing document."""

    allowed_statuses = {
        "processing",
        "indexed",
        "failed",
        "deleting",
    }

    if status not in allowed_statuses:
        raise ValueError(f"Invalid document status: {status}")

    document = db.get(Document, document_id)

    if document is None:
        raise ValueError(f"Document not found: {document_id}")

    try:
        document.status = status
        db.commit()
        db.refresh(document)
    except Exception:
        db.rollback()
        raise

    return document


def claim_document_for_permission_update(
    db: Session,
    *,
    document_id: str,
    new_permission_level: int,
) -> bool:
    """Atomically claim an indexed document for a permission update."""

    if not document_id:
        raise ValueError("document_id cannot be empty")

    if new_permission_level not in (1, 2, 3):
        raise ValueError("Invalid new permission level")

    try:
        statement = (
            update(Document)
            .where(
                Document.document_id == document_id,
                Document.status == "indexed",
                Document.permission_update_target.is_(None),
            )
            .values(
                status="processing",
                permission_update_target=new_permission_level,
            )
            .returning(Document.document_id)
        )

        updated_id = db.scalar(statement)

        if updated_id is None:
            db.rollback()
            return False

        db.commit()
        return True

    except Exception:
        db.rollback()
        raise


def finish_document_permission_update(
    db: Session,
    *,
    document_id: str,
    expected_permission_level: int,
    new_permission_level: int,
    target_permission_level: int,
) -> Document | None:
    """Complete or safely restore a claimed permission update."""

    if not document_id:
        raise ValueError("document_id cannot be empty")

    if expected_permission_level not in (1, 2, 3):
        raise ValueError("Invalid expected permission level")

    if new_permission_level not in (1, 2, 3):
        raise ValueError("Invalid new permission level")

    if target_permission_level not in (1, 2, 3):
        raise ValueError("Invalid target permission level")

    if new_permission_level not in (
        expected_permission_level,
        target_permission_level,
    ):
        raise ValueError("Invalid permission update completion")

    try:
        statement = (
            update(Document)
            .where(
                Document.document_id == document_id,
                Document.status == "processing",
                Document.permission_level == expected_permission_level,
                Document.permission_update_target
                == target_permission_level,
            )
            .values(
                permission_level=new_permission_level,
                status="indexed",
                permission_update_target=None,
            )
            .returning(Document.document_id)
        )

        updated_id = db.scalar(statement)

        if updated_id is None:
            db.rollback()
            return None

        db.commit()

        document = db.get(Document, document_id)
        db.refresh(document)

        return document

    except Exception:
        db.rollback()
        raise


def list_searchable_document_ids(
    db: Session,
    *,
    clearance_level: int,
    department_id: str,
    is_admin: bool = False,
    department_filter: str | None = None,
) -> list[str]:
    """Return document IDs that are indexed and visible to the user."""

    if clearance_level not in (1, 2, 3):
        raise ValueError("Invalid clearance level")

    query = select(Document.document_id).where(
        Document.status == "indexed",
        Document.permission_level <= clearance_level,
    )

    # Non-admin users can only access their own department
    # or documents shared with Global.
    if not is_admin:
        query = query.where(
            or_(
                Document.department_id == department_id,
                Document.department_id == "Global",
            )
        )

    # An explicit department filter can only narrow the result.
    if department_filter:
        query = query.where(
            Document.department_id == department_filter
        )

    return list(db.scalars(query).all())


def list_documents(
    db: Session,
    *,
    clearance_level: int,
    department_id: str,
    is_admin: bool = False,
    page: int = 1,
    page_size: int = 20,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    permission_level: int | None = None,
    creator_id: str | None = None,
    status: str | None = None,
    q: str | None = None,
) -> tuple[list[Document], int]:
    """List visible catalog documents with filters and pagination."""

    if clearance_level not in (1, 2, 3):
        raise ValueError("Invalid clearance level")

    if page < 1 or not 1 <= page_size <= 100:
        raise ValueError("Invalid pagination")

    sort_columns = {
        "created_at": Document.created_at,
        "updated_at": Document.updated_at,
        "filename": Document.filename,
        "permission_level": Document.permission_level,
        "status": Document.status,
    }

    if sort_by not in sort_columns:
        raise ValueError("Invalid sort field")

    if sort_order not in ("asc", "desc"):
        raise ValueError("Invalid sort order")

    if permission_level is not None and permission_level not in (1, 2, 3):
        raise ValueError("Invalid permission level")

    allowed_statuses = {"processing", "indexed", "failed", "deleting"}
    if status is not None and status not in allowed_statuses:
        raise ValueError("Invalid document status")

    # Apply visibility restrictions before any user filters.
    query = select(Document).where(
        Document.permission_level <= clearance_level
    )

    if not is_admin:
        query = query.where(
            or_(
                Document.department_id == department_id,
                Document.department_id == "Global",
            ),
            # Hide documents undergoing permission changes.
            Document.permission_update_target.is_(None),
        )

    if permission_level is not None:
        query = query.where(Document.permission_level == permission_level)

    if creator_id is not None:
        query = query.where(Document.creator_id == creator_id)

    if status is not None:
        query = query.where(Document.status == status)

    if q and q.strip():
        pattern = f"%{q.strip()}%"
        query = query.where(
            or_(
                Document.title.ilike(pattern),
                Document.filename.ilike(pattern),
            )
        )

    # Count only documents visible under the applied restrictions.
    total = db.scalar(
        select(func.count()).select_from(query.subquery())
    ) or 0

    sort_column = sort_columns[sort_by]
    ordering = (
        sort_column.asc()
        if sort_order == "asc"
        else sort_column.desc()
    )

    # document_id provides deterministic ordering for ties.
    query = (
        query.order_by(ordering, Document.document_id.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )

    documents = list(db.scalars(query).all())

    return documents, total


"""Delete document metadata, source, and Qdrant points."""

from sqlalchemy import delete, update
from sqlalchemy.orm import Session
from qdrant_client import models

from backend.database.models import Document, DocumentSource
from backend.qdrant_schema import COLLECTION_NAME, create_client
from backend.rag_service import delete_document_points


class DocumentNotDeletableError(Exception):
    """Document is not eligible for deletion."""


def delete_document(
    db: Session,
    *,
    document_id: str,
) -> None:
    """Delete a document from PostgreSQL and Qdrant.

    A failed deletion remains retryable through status='deleting'.
    """

    # Step 1: Claim the document for deletion.
    try:
        statement = (
            update(Document)
            .where(
                Document.document_id == document_id,
                Document.status.in_(
                    ("indexed", "failed", "deleting")
                ),
                Document.permission_update_target.is_(None),
            )
            .values(status="deleting")
            .returning(Document.document_id)
        )

        claimed_id = db.scalar(statement)

        if claimed_id is None:
            db.rollback()
            raise DocumentNotDeletableError(
                "Document is not available for deletion"
            )

        db.commit()

    except DocumentNotDeletableError:
        raise
    except Exception:
        db.rollback()
        raise

    # Step 2: Delete Qdrant points and verify removal.
    client = None

    try:
        client = create_client()

        if client.collection_exists(COLLECTION_NAME):
            delete_document_points(
                client,
                document_id=document_id,
            )

            remaining, _ = client.scroll(
                collection_name=COLLECTION_NAME,
                scroll_filter=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="document_id",
                            match=models.MatchValue(
                                value=document_id
                            ),
                        )
                    ]
                ),
                limit=1,
                with_payload=False,
                with_vectors=False,
            )

            if remaining:
                raise RuntimeError(
                    "Qdrant document deletion verification failed"
                )

    finally:
        if client is not None:
            client.close()

    # Step 3: Delete PostgreSQL source and metadata.
    # Both deletions are committed in one transaction.
    try:
        db.execute(
            delete(DocumentSource).where(
                DocumentSource.document_id == document_id
            )
        )

        db.execute(
            delete(Document).where(
                Document.document_id == document_id
            )
        )

        db.commit()

    except Exception:
        db.rollback()
        raise

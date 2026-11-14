
"""Document reindexing using the existing ingestion pipeline."""

import logging

from sqlalchemy import update

from backend.database.connection import SessionLocal
from backend.database.models import Document, DocumentSource
from backend.qdrant_schema import COLLECTION_NAME, create_client
from backend.rag_service import ingest, delete_document_points
from backend.services.document_service import update_document_status

logger = logging.getLogger(__name__)


def claim_document_for_reindex(db, *, document_id: str) -> bool:
    """Mark an eligible document as processing before reindexing."""

    try:
        statement = (
            update(Document)
            .where(
                Document.document_id == document_id,
                Document.status.in_(("indexed", "failed")),
                Document.permission_update_target.is_(None),
            )
            .values(status="processing")
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


def run_document_reindex(document_id: str) -> None:
    """Rebuild Qdrant chunks from the stored PostgreSQL source."""

    # Background tasks must use their own database session.
    db = SessionLocal()
    client = None

    try:
        document = db.get(Document, document_id)
        source = db.get(DocumentSource, document_id)

        if document is None or source is None:
            raise RuntimeError("Document or original source not found")

        if document.status != "processing":
            raise RuntimeError("Document is not in processing state")

        if document.permission_update_target is not None:
            raise RuntimeError("Document permission update is in progress")

        client = create_client()

        # Remove old chunks, including chunks that may no longer
        # exist after the document is parsed again.
        if client.collection_exists(COLLECTION_NAME):
            delete_document_points(
                client,
                document_id=document_id,
            )

        # Reuse the current catalog metadata and ingestion pipeline.
        chunk_count = ingest(
            client,
            document_id=document.document_id,
            filename=document.filename,
            content_type=document.content_type,
            content=source.source_content,
            department_id=document.department_id,
            permission_level=document.permission_level,
        )

        if chunk_count == 0:
            raise RuntimeError("Reindex produced no chunks")

        update_document_status(
            db,
            document_id=document_id,
            status="indexed",
        )

        logger.info(
            "Document reindexed successfully: %s (%d chunks)",
            document_id,
            chunk_count,
        )

    except Exception:
        logger.exception("Document reindex failed: %s", document_id)
        db.rollback()

        # Keep partially rebuilt indexes out of Qdrant.
        if client is not None:
            try:
                if client.collection_exists(COLLECTION_NAME):
                    delete_document_points(
                        client,
                        document_id=document_id,
                    )
            except Exception:
                logger.exception(
                    "Qdrant cleanup failed: %s",
                    document_id,
                )

        # Failed documents remain excluded from normal search.
        try:
            update_document_status(
                db,
                document_id=document_id,
                status="failed",
            )
        except Exception:
            logger.exception(
                "Failed to persist reindex failure: %s",
                document_id,
            )

    finally:
        db.close()
        if client is not None:
            client.close()

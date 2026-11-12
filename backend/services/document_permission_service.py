
"""Coordinate document permission updates across PostgreSQL and Qdrant."""

import logging

from qdrant_client import QdrantClient
from sqlalchemy.orm import Session

from backend.database.models import Document
from backend.rag_service import (
    update_document_permission,
    verify_document_permission,
)
from backend.services.document_service import (
    claim_document_for_permission_update,
    finish_document_permission_update,
)

logger = logging.getLogger(__name__)


class DocumentNotClaimableError(RuntimeError):
    """The document does not exist or is not available for updating."""


def change_document_permission(
    db: Session,
    client: QdrantClient,
    *,
    document_id: str,
    new_permission_level: int,
) -> Document:
    """Synchronize document permissions across PostgreSQL and Qdrant."""

    if not document_id:
        raise ValueError("document_id cannot be empty")

    if new_permission_level not in (1, 2, 3):
        raise ValueError("permission_level must be between 1 and 3")

    # Prevent new searches and competing permission updates.
    if not claim_document_for_permission_update(
        db,
        document_id=document_id,
        new_permission_level=new_permission_level,
    ):
        raise DocumentNotClaimableError(
            f"Document {document_id} cannot be updated"
        )

    original_level = None
    original_count = None

    try:
        document = db.get(Document, document_id)
        if document is None:
            raise RuntimeError("Claimed document was not found")

        db.refresh(document)

        if document.status != "processing":
            raise RuntimeError("Document is not in processing state")

        original_level = document.permission_level

        # Establish the original Qdrant state before modifying it.
        original_count = verify_document_permission(
            client,
            document_id=document_id,
            permission_level=original_level,
        )

        # Update all matching Qdrant chunks.
        update_document_permission(
            client,
            document_id=document_id,
            permission_level=new_permission_level,
        )

        updated_count = verify_document_permission(
            client,
            document_id=document_id,
            permission_level=new_permission_level,
        )

        if updated_count != original_count:
            raise RuntimeError("Document chunk count changed during update")

        # Restore search visibility only after Qdrant verification.
        updated_document = finish_document_permission_update(
            db,
            document_id=document_id,
            expected_permission_level=original_level,
            new_permission_level=new_permission_level,
            target_permission_level=new_permission_level,
        )

        if updated_document is None:
            raise RuntimeError("PostgreSQL permission finalization failed")

        return updated_document

    except Exception:
        db.rollback()

        if original_level is not None:
            try:
                current = db.get(Document, document_id)
                if current is not None:
                    db.refresh(current)

                # Never revert Qdrant if PostgreSQL may have
                # already committed the new permission.
                if (
                    current is not None
                    and current.status == "processing"
                    and current.permission_level == original_level
                    and current.permission_update_target == new_permission_level
                ):

                    if original_count is None:
                        # The initial verification failed before any Qdrant update.
                        # Recheck the original state before restoring search visibility.
                        verify_document_permission(
                            client,
                            document_id=document_id,
                            permission_level=original_level,
                        )
                    else:
                        # Qdrant may have been modified. Restore its original permission.
                        update_document_permission(
                            client,
                            document_id=document_id,
                            permission_level=original_level,
                        )

                        restored_count = verify_document_permission(
                            client,
                            document_id=document_id,
                            permission_level=original_level,
                        )

                        if restored_count != original_count:
                            raise RuntimeError(
                                "Chunk count mismatch during recovery"
                            )


                    restored = finish_document_permission_update(
                        db,
                        document_id=document_id,
                        expected_permission_level=original_level,
                        new_permission_level=original_level,
                        target_permission_level=new_permission_level,
                    )

                    if restored is None:
                        raise RuntimeError(
                            "PostgreSQL recovery finalization failed"
                        )
                else:
                    logger.error(
                        "Permission recovery requires state reconciliation: %s",
                        document_id,
                    )

            except Exception:
                logger.exception(
                    "Automatic permission recovery failed: %s",
                    document_id,
                )

        raise

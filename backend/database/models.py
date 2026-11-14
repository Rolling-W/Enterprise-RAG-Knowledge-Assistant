
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Float,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Conversation(Base):
    __tablename__ = "conversations"

    conversation_id: Mapped[str] = mapped_column(
        String(128),
        primary_key=True,
    )

    owner_id: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        index=True,
    )

    title: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class Message(Base):
    __tablename__ = "messages"

    __table_args__ = (
        UniqueConstraint(
            "conversation_id",
            "sequence",
            name="uq_messages_conversation_sequence",
        ),
    )

    message_id: Mapped[str] = mapped_column(
        String(128),
        primary_key=True,
    )

    conversation_id: Mapped[str] = mapped_column(
        ForeignKey("conversations.conversation_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    sequence: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    role: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
    )

    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


class MessageCitation(Base):
    __tablename__ = "message_citations"

    __table_args__ = (
        UniqueConstraint(
            "message_id",
            "position",
            name="uq_message_citations_position",
        ),
    )

    citation_id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    message_id: Mapped[str] = mapped_column(
        ForeignKey("messages.message_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    position: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    document_id: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
    )

    chunk_id: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
    )

    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    permission_level: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    score: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )

    page: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    line_start: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    line_end: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )


class Document(Base):
    __tablename__ = "documents"

    __table_args__ = (
        CheckConstraint(
            "permission_level BETWEEN 1 AND 3",
            name="ck_documents_permission_level",
        ),
        CheckConstraint(
            "permission_update_target IS NULL OR "
            "permission_update_target BETWEEN 1 AND 3",
            name="ck_documents_permission_update_target",
        ),
        CheckConstraint(
            "size_bytes >= 0",
            name="ck_documents_size_bytes",
        ),
        CheckConstraint(
            "status IN ('processing', 'indexed', 'failed', 'deleting')",
            name="ck_documents_status",
        ),
    )

    document_id: Mapped[str] = mapped_column(
        String(128),
        primary_key=True,
    )

    filename: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    content_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    size_bytes: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    department_id: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        index=True,
    )

    permission_level: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default="1",
    )

    permission_update_target: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    creator_id: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        index=True,
    )

    creator_display_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        server_default="processing",
        index=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class DocumentSource(Base):
    __tablename__ = "document_sources"

    document_id: Mapped[str] = mapped_column(
        ForeignKey("documents.document_id", ondelete="CASCADE"),
        primary_key=True,
    )

    source_content: Mapped[bytes] = mapped_column(
        LargeBinary,
        nullable=False,
    )

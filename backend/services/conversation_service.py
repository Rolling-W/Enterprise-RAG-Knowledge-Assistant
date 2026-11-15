
from uuid import uuid4

from sqlalchemy.orm import Session

from backend.database.models import Conversation, Message, MessageCitation

from sqlalchemy import func, select

from datetime import datetime, timezone


def create_conversation(
    db: Session,
    *,
    owner_id: str,
    title: str | None = None,
) -> Conversation:
    conversation = Conversation(
        conversation_id=f"conv_{uuid4().hex}",
        owner_id=owner_id,
        title=title,
    )

    db.add(conversation)
    db.commit()
    db.refresh(conversation)

    return conversation


def get_conversation(
    db: Session,
    *,
    conversation_id: str,
    owner_id: str,
) -> Conversation | None:
    statement = select(Conversation).where(
        Conversation.conversation_id == conversation_id,
        Conversation.owner_id == owner_id,
    )

    return db.scalar(statement)


def list_conversations(
    db: Session,
    *,
    owner_id: str,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[Conversation], int]:
    if page < 1 or not 1 <= page_size <= 100:
        raise ValueError("Invalid pagination parameters")

    # Count only conversations owned by this user.
    total = db.scalar(
        select(func.count())
        .select_from(Conversation)
        .where(Conversation.owner_id == owner_id)
    ) or 0

    # Retrieve the requested page, newest first.
    statement = (
        select(Conversation)
        .where(Conversation.owner_id == owner_id)
        .order_by(
            Conversation.updated_at.desc(),
            Conversation.conversation_id.desc(),
        )
        .offset((page - 1) * page_size)
        .limit(page_size)
    )

    conversations = list(db.scalars(statement).all())

    return conversations, total


def delete_conversation(
    db: Session,
    *,
    conversation_id: str,
    owner_id: str,
) -> bool:
    conversation = get_conversation(
        db,
        conversation_id=conversation_id,
        owner_id=owner_id,
    )

    if conversation is None:
        return False

    db.delete(conversation)
    db.commit()

    return True


def add_user_message(
    db: Session,
    *,
    conversation_id: str,
    owner_id: str,
    content: str,
) -> Message | None:
    if not content.strip():
        raise ValueError("Message content cannot be empty")

    # Lock the conversation to prevent concurrent sequence conflicts.
    conversation = db.scalar(
        select(Conversation)
        .where(
            Conversation.conversation_id == conversation_id,
            Conversation.owner_id == owner_id,
        )
        .with_for_update()
    )

    if conversation is None:
        return None

    # Determine the next message sequence.
    last_sequence = db.scalar(
        select(func.max(Message.sequence))
        .where(Message.conversation_id == conversation_id)
    )

    message = Message(
        message_id=f"msg_{uuid4().hex}",
        conversation_id=conversation_id,
        sequence=(last_sequence or 0) + 1,
        role="user",
        content=content,
    )

    db.add(message)

    # Update the conversation's last activity timestamp.
    conversation.updated_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(message)

    return message


def list_conversation_messages(
    db: Session,
    *,
    conversation_id: str,
    owner_id: str,
) -> list[Message] | None:
    # Verify that the conversation belongs to this user.
    conversation = get_conversation(
        db,
        conversation_id=conversation_id,
        owner_id=owner_id,
    )

    if conversation is None:
        return None

    # Retrieve messages in chronological sequence.
    statement = (
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(
            Message.sequence.asc(),
            Message.created_at.asc(),
        )
    )

    return list(db.scalars(statement).all())


def add_assistant_message(
    db: Session,
    *,
    conversation_id: str,
    owner_id: str,
    content: str,
    citations: list[dict],
) -> Message | None:
    if not content.strip():
        raise ValueError("Assistant message cannot be empty")

    # Lock the conversation and verify ownership.
    conversation = db.scalar(
        select(Conversation)
        .where(
            Conversation.conversation_id == conversation_id,
            Conversation.owner_id == owner_id,
        )
        .with_for_update()
    )

    if conversation is None:
        return None

    try:
        # Determine the next sequence number.
        last_sequence = db.scalar(
            select(func.max(Message.sequence))
            .where(Message.conversation_id == conversation_id)
        )

        message = Message(
            message_id=f"msg_{uuid4().hex}",
            conversation_id=conversation_id,
            sequence=(last_sequence or 0) + 1,
            role="assistant",
            content=content,
        )

        db.add(message)

        # Store citations in their original order.
        for position, citation in enumerate(citations, start=1):
            db.add(
                MessageCitation(
                    message_id=message.message_id,
                    position=position,
                    document_id=citation["document_id"],
                    chunk_id=citation["chunk_id"],
                    title=citation["title"],
                    permission_level=citation["permission_level"],
                    score=citation["score"],
                    page=citation.get("page"),
                    line_start=citation.get("line_start"),
                    line_end=citation.get("line_end"),
                )
            )

        conversation.updated_at = datetime.now(timezone.utc)

        # Save the message and citations atomically.
        db.commit()
        db.refresh(message)

        return message

    except Exception:
        db.rollback()
        raise


def list_conversation_citations(
    db: Session,
    *,
    conversation_id: str,
    owner_id: str,
) -> list[MessageCitation] | None:
    # Verify conversation ownership.
    conversation = get_conversation(
        db,
        conversation_id=conversation_id,
        owner_id=owner_id,
    )

    if conversation is None:
        return None

    # Retrieve citations ordered by message and position.
    statement = (
        select(MessageCitation)
        .join(
            Message,
            Message.message_id == MessageCitation.message_id,
        )
        .where(Message.conversation_id == conversation_id)
        .order_by(
            Message.sequence.asc(),
            MessageCitation.position.asc(),
        )
    )

    return list(db.scalars(statement).all())

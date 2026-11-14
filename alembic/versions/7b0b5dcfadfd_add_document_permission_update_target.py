"""add document permission update target

Revision ID: 7b0b5dcfadfd
Revises: b6795e60a6cd
Create Date: 2026-11-12 11:47:51.853462

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7b0b5dcfadfd'
down_revision: Union[str, Sequence[str], None] = 'b6795e60a6cd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None



def upgrade() -> None:
    op.add_column(
        "documents",
        sa.Column(
            "permission_update_target",
            sa.Integer(),
            nullable=True,
        ),
    )

    op.create_check_constraint(
        "ck_documents_permission_update_target",
        "documents",
        "permission_update_target IS NULL OR "
        "permission_update_target BETWEEN 1 AND 3",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_documents_permission_update_target",
        "documents",
        type_="check",
    )

    op.drop_column(
        "documents",
        "permission_update_target",
    )

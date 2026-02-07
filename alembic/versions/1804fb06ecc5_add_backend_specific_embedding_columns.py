"""Add backend specific embedding columns

Revision ID: 1804fb06ecc5
Revises: ba79132da33d
Create Date: 2026-02-05 18:02:21.088688

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector


# revision identifiers, used by Alembic.
revision: str = '1804fb06ecc5'
down_revision: Union[str, None] = 'ba79132da33d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Add backend-specific embedding columns without deleting existing data.
    """
    op.add_column(
        "document_chunks",
        sa.Column("embedding_768", Vector(768), nullable=True)
    )
    op.add_column(
        "document_chunks",
        sa.Column("embedding_1536", Vector(1536), nullable=True)
    )
    op.create_index(
        "ix_document_chunks_embedding_768_ivfflat",
        "document_chunks",
        ["embedding_768"],
        unique=False,
        postgresql_with={"lists": "7"},
        postgresql_using="ivfflat"
    )
    op.create_index(
        "ix_document_chunks_embedding_1536_ivfflat",
        "document_chunks",
        ["embedding_1536"],
        unique=False,
        postgresql_with={"lists": "7"},
        postgresql_using="ivfflat"
    )


def downgrade() -> None:
    """
    Drop backend-specific embedding columns.
    """
    op.drop_index(
        "ix_document_chunks_embedding_1536_ivfflat",
        table_name="document_chunks",
        postgresql_with={"lists": "7"},
        postgresql_using="ivfflat"
    )
    op.drop_index(
        "ix_document_chunks_embedding_768_ivfflat",
        table_name="document_chunks",
        postgresql_with={"lists": "7"},
        postgresql_using="ivfflat"
    )
    op.drop_column("document_chunks", "embedding_1536")
    op.drop_column("document_chunks", "embedding_768")

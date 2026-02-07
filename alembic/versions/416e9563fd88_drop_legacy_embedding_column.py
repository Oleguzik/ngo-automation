"""Drop legacy embedding column

Revision ID: 416e9563fd88
Revises: 1804fb06ecc5
Create Date: 2026-02-05 18:28:58.973522

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '416e9563fd88'
down_revision: Union[str, None] = '1804fb06ecc5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Drop legacy embedding column after backfill verification.
    """
    connection = op.get_bind()
    result = connection.execute(
        sa.text(
            """
            SELECT COUNT(*)
            FROM document_chunks
            WHERE embedding_768 IS NULL
              AND embedding_1536 IS NULL
            """
        )
    )
    missing_count = result.scalar() or 0
    if missing_count > 0:
        raise RuntimeError(
            f"Backfill incomplete: {missing_count} chunks have no embeddings. "
            "Run scripts/backfill_document_chunk_embeddings.py before dropping legacy column."
        )

    op.drop_column("document_chunks", "embedding")


def downgrade() -> None:
    """
    Recreate legacy embedding column for rollback.
    """
    op.execute("ALTER TABLE document_chunks ADD COLUMN embedding vector(768);")

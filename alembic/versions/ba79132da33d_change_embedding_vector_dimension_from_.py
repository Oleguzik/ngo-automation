"""Change embedding vector dimension from 1536 to 768 for Ollama compatibility

Revision ID: ba79132da33d
Revises: 1f95e2bbd073
Create Date: 2026-02-05 16:31:19.474299

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'ba79132da33d'
down_revision: Union[str, None] = '1f95e2bbd073'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Deprecated destructive migration.
    
    This migration previously deleted document_chunks data to change dimensions.
    It is now a no-op to prevent data loss. Use the backend-specific embedding
    columns migration for safe upgrades.
    """
    return None


def downgrade() -> None:
    """
    Deprecated destructive migration.
    
    This migration remains a no-op to prevent data loss.
    """
    return None

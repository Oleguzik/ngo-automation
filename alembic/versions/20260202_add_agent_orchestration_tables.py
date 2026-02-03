"""Add Phase 5C agent orchestration tables: agent_tasks and agent_steps

This migration creates tables for multi-step agent orchestration,
enabling complex financial analysis tasks with planning and execution tracking.

References:
- Spec: docs/PHASE5C_IMPLEMENTATION_SPEC.md
- Models: app/models.py (AgentTask, AgentStep)

Features:
- AgentTask: Multi-step task planning and status tracking
- AgentStep: Individual step execution logs with LLM interaction details
- Cost tracking: tokens and USD costs per task/step
- Langfuse integration: trace_id and span_id linking
- Performance metrics: duration tracking for optimization

Revision ID: 20260202_agent_orchestration
Revises: 20260119_docchunk_pgvector
Create Date: 2026-02-02 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision: str = '20260202_agent_orchestration'
down_revision: Union[str, None] = '20260119_docchunk_pgvector'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create agent_tasks and agent_steps tables."""
    
    # Create agent_tasks table
    op.create_table(
        'agent_tasks',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('organization_id', sa.Integer(), nullable=False),
        sa.Column('objective', sa.Text(), nullable=False),
        sa.Column('context', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('plan', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('max_steps', sa.Integer(), server_default='10', nullable=False),
        sa.Column('status', sa.String(length=50), server_default='pending', nullable=False),
        sa.Column('current_step', sa.Integer(), server_default='0', nullable=False),
        sa.Column('result', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('total_tokens_used', sa.Integer(), server_default='0', nullable=False),
        sa.Column('total_cost_usd', sa.DECIMAL(precision=10, scale=6), server_default='0.0', nullable=False),
        sa.Column('langfuse_trace_id', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for agent_tasks
    op.create_index('idx_agent_tasks_id', 'agent_tasks', ['id'], unique=False)
    op.create_index('idx_agent_tasks_org_id', 'agent_tasks', ['organization_id'], unique=False)
    op.create_index('idx_agent_tasks_status', 'agent_tasks', ['status'], unique=False)
    op.create_index('idx_agent_tasks_created_at', 'agent_tasks', ['created_at'], unique=False)
    
    # Create agent_steps table
    op.create_table(
        'agent_steps',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('task_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('step_number', sa.Integer(), nullable=False),
        sa.Column('step_name', sa.String(length=255), nullable=False),
        sa.Column('action', sa.String(length=100), nullable=False),
        sa.Column('input_data', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('status', sa.String(length=50), server_default='pending', nullable=False),
        sa.Column('output_data', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('llm_prompt', sa.Text(), nullable=True),
        sa.Column('llm_response', sa.Text(), nullable=True),
        sa.Column('tokens_used', sa.Integer(), server_default='0', nullable=False),
        sa.Column('cost_usd', sa.DECIMAL(precision=10, scale=6), server_default='0.0', nullable=False),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('duration_seconds', sa.DECIMAL(precision=10, scale=3), nullable=True),
        sa.Column('langfuse_span_id', sa.String(length=255), nullable=True),
        sa.ForeignKeyConstraint(['task_id'], ['agent_tasks.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for agent_steps
    op.create_index('idx_agent_steps_id', 'agent_steps', ['id'], unique=False)
    op.create_index('idx_agent_steps_task_id', 'agent_steps', ['task_id'], unique=False)
    op.create_index('idx_agent_steps_task_step', 'agent_steps', ['task_id', 'step_number'], unique=True)
    
    # Create trigger for updated_at auto-update on agent_tasks
    op.execute("""
        CREATE OR REPLACE FUNCTION update_agent_tasks_updated_at()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = CURRENT_TIMESTAMP;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)
    
    op.execute("""
        CREATE TRIGGER trigger_update_agent_tasks_updated_at
        BEFORE UPDATE ON agent_tasks
        FOR EACH ROW
        EXECUTE FUNCTION update_agent_tasks_updated_at();
    """)


def downgrade() -> None:
    """Drop agent_tasks and agent_steps tables."""
    
    # Drop trigger and function
    op.execute('DROP TRIGGER IF EXISTS trigger_update_agent_tasks_updated_at ON agent_tasks')
    op.execute('DROP FUNCTION IF EXISTS update_agent_tasks_updated_at()')
    
    # Drop indexes for agent_steps
    op.drop_index('idx_agent_steps_task_step', table_name='agent_steps')
    op.drop_index('idx_agent_steps_task_id', table_name='agent_steps')
    op.drop_index('idx_agent_steps_id', table_name='agent_steps')
    
    # Drop agent_steps table
    op.drop_table('agent_steps')
    
    # Drop indexes for agent_tasks
    op.drop_index('idx_agent_tasks_created_at', table_name='agent_tasks')
    op.drop_index('idx_agent_tasks_status', table_name='agent_tasks')
    op.drop_index('idx_agent_tasks_org_id', table_name='agent_tasks')
    op.drop_index('idx_agent_tasks_id', table_name='agent_tasks')
    
    # Drop agent_tasks table
    op.drop_table('agent_tasks')

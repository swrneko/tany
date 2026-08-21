"""providers and jobs

Revision ID: e6b3cd5a655f
Revises: 0001
Create Date: 2026-08-21 19:15:18.053432+00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '0002'
down_revision: str | None = '0001'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table('providers',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('kind', sa.String(length=8), nullable=False),
    sa.Column('name', sa.String(length=128), nullable=False),
    sa.Column('base_url', sa.Text(), nullable=False),
    sa.Column('api_key_encrypted', sa.LargeBinary(), nullable=True),
    sa.Column('default_model', sa.String(length=128), nullable=True),
    sa.Column('context_tokens', sa.Integer(), nullable=True),
    sa.Column('extra_json', sa.Text(), nullable=True),
    sa.Column('is_default', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('providers', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_providers_kind'), ['kind'], unique=False)

    op.create_table('jobs',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('owner_id', sa.Uuid(), nullable=False),
    sa.Column('source_type', sa.String(length=16), nullable=False),
    sa.Column('source_ref', sa.Text(), nullable=False),
    sa.Column('title', sa.Text(), nullable=False),
    sa.Column('status', sa.String(length=16), nullable=False),
    sa.Column('progress', sa.Float(), nullable=False),
    sa.Column('language', sa.String(length=16), nullable=True),
    sa.Column('prompt', sa.Text(), nullable=True),
    sa.Column('stt_provider_id', sa.Uuid(), nullable=True),
    sa.Column('stt_model', sa.String(length=128), nullable=True),
    sa.Column('sha256', sa.String(length=64), nullable=True),
    sa.Column('duration_sec', sa.Float(), nullable=True),
    sa.Column('error_code', sa.String(length=64), nullable=True),
    sa.Column('error_params', sa.Text(), nullable=True),
    sa.Column('error_message', sa.Text(), nullable=True),
    sa.Column('worker_id', sa.String(length=64), nullable=True),
    sa.Column('heartbeat_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['owner_id'], ['users.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['stt_provider_id'], ['providers.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('jobs', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_jobs_owner_id'), ['owner_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_jobs_sha256'), ['sha256'], unique=False)
        batch_op.create_index(batch_op.f('ix_jobs_status'), ['status'], unique=False)



def downgrade() -> None:
    with op.batch_alter_table('jobs', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_jobs_status'))
        batch_op.drop_index(batch_op.f('ix_jobs_sha256'))
        batch_op.drop_index(batch_op.f('ix_jobs_owner_id'))

    op.drop_table('jobs')
    with op.batch_alter_table('providers', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_providers_kind'))

    op.drop_table('providers')

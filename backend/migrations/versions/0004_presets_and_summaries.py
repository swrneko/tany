"""presets and summaries

Revision ID: 3a0d421887ed
Revises: 0003
Create Date: 2026-08-21 20:00:36.581140+00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

import app.models  # noqa: F401  -- custom column types are rendered fully qualified

revision: str = '0004'
down_revision: str | None = '0003'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table('presets',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('owner_id', sa.Uuid(), nullable=True),
    sa.Column('name', sa.String(length=128), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('system_prompt', sa.Text(), nullable=False),
    sa.Column('user_template', sa.Text(), nullable=False),
    sa.Column('model_override', sa.String(length=128), nullable=True),
    sa.Column('provider_id', sa.Uuid(), nullable=True),
    sa.Column('temperature', sa.Float(), nullable=True),
    sa.Column('output_format', sa.String(length=16), nullable=False),
    sa.Column('is_builtin', sa.Boolean(), nullable=False),
    sa.Column('builtin_key', sa.String(length=64), nullable=True),
    sa.Column('created_at', app.models.UtcDateTime(), nullable=False),
    sa.ForeignKeyConstraint(['owner_id'], ['users.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['provider_id'], ['providers.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('builtin_key')
    )
    with op.batch_alter_table('presets', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_presets_owner_id'), ['owner_id'], unique=False)

    op.create_table('summaries',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('job_id', sa.Uuid(), nullable=False),
    sa.Column('preset_id', sa.Uuid(), nullable=True),
    sa.Column('preset_name', sa.String(length=128), nullable=False),
    sa.Column('status', sa.String(length=16), nullable=False),
    sa.Column('progress', sa.Float(), nullable=False),
    sa.Column('content', sa.Text(), nullable=False),
    sa.Column('partials_json', sa.Text(), nullable=True),
    sa.Column('model_used', sa.String(length=128), nullable=True),
    sa.Column('error_code', sa.String(length=64), nullable=True),
    sa.Column('error_params', sa.Text(), nullable=True),
    sa.Column('error_message', sa.Text(), nullable=True),
    sa.Column('worker_id', sa.String(length=64), nullable=True),
    sa.Column('heartbeat_at', app.models.UtcDateTime(), nullable=True),
    sa.Column('created_at', app.models.UtcDateTime(), nullable=False),
    sa.Column('finished_at', app.models.UtcDateTime(), nullable=True),
    sa.ForeignKeyConstraint(['job_id'], ['jobs.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['preset_id'], ['presets.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('summaries', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_summaries_job_id'), ['job_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_summaries_status'), ['status'], unique=False)



def downgrade() -> None:
    with op.batch_alter_table('summaries', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_summaries_status'))
        batch_op.drop_index(batch_op.f('ix_summaries_job_id'))

    op.drop_table('summaries')
    with op.batch_alter_table('presets', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_presets_owner_id'))

    op.drop_table('presets')

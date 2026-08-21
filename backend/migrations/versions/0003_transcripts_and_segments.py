"""transcripts and segments

Revision ID: 8fce31c72950
Revises: 0002
Create Date: 2026-08-21 19:24:14.419268+00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '0003'
down_revision: str | None = '0002'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table('transcripts',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('job_id', sa.Uuid(), nullable=False),
    sa.Column('raw_json', sa.Text(), nullable=False),
    sa.Column('language', sa.String(length=32), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['job_id'], ['jobs.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('job_id')
    )
    op.create_table('segments',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('transcript_id', sa.Uuid(), nullable=False),
    sa.Column('idx', sa.Integer(), nullable=False),
    sa.Column('start', sa.Float(), nullable=False),
    sa.Column('end', sa.Float(), nullable=False),
    sa.Column('text', sa.Text(), nullable=False),
    sa.Column('edited_text', sa.Text(), nullable=True),
    sa.Column('speaker', sa.String(length=64), nullable=True),
    sa.ForeignKeyConstraint(['transcript_id'], ['transcripts.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('segments', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_segments_transcript_id'), ['transcript_id'], unique=False)



def downgrade() -> None:
    with op.batch_alter_table('segments', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_segments_transcript_id'))

    op.drop_table('segments')
    op.drop_table('transcripts')

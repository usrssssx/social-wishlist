"""Add email verification and password reset schema

Revision ID: 20260305_0002
Revises: 20260305_0001
Create Date: 2026-03-05 10:25:00.000000

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '20260305_0002'
down_revision = '20260305_0001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('users', sa.Column('email_verified', sa.Boolean(), server_default=sa.text('false'), nullable=False))

    email_action_purpose = postgresql.ENUM('verify_email', 'reset_password', name='emailactionpurpose')
    email_action_purpose.create(op.get_bind(), checkfirst=True)

    op.create_table(
        'email_action_tokens',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            'purpose',
            postgresql.ENUM('verify_email', 'reset_password', name='emailactionpurpose', create_type=False),
            nullable=False,
        ),
        sa.Column('token_hash', sa.String(length=128), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('used_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_email_action_tokens_expires_at'), 'email_action_tokens', ['expires_at'], unique=False)
    op.create_index(op.f('ix_email_action_tokens_token_hash'), 'email_action_tokens', ['token_hash'], unique=True)
    op.create_index(op.f('ix_email_action_tokens_user_id'), 'email_action_tokens', ['user_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_email_action_tokens_user_id'), table_name='email_action_tokens')
    op.drop_index(op.f('ix_email_action_tokens_token_hash'), table_name='email_action_tokens')
    op.drop_index(op.f('ix_email_action_tokens_expires_at'), table_name='email_action_tokens')
    op.drop_table('email_action_tokens')

    postgresql.ENUM('verify_email', 'reset_password', name='emailactionpurpose').drop(op.get_bind(), checkfirst=True)
    op.drop_column('users', 'email_verified')

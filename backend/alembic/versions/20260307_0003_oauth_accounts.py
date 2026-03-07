"""Add OAuth accounts

Revision ID: 20260307_0003
Revises: 20260305_0002
Create Date: 2026-03-07 11:15:00.000000

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '20260307_0003'
down_revision = '20260305_0002'
branch_labels = None
depends_on = None


def upgrade() -> None:
    oauth_provider = postgresql.ENUM('google', 'github', name='oauthprovider')
    oauth_provider.create(op.get_bind(), checkfirst=True)

    op.create_table(
        'oauth_accounts',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            'provider',
            postgresql.ENUM('google', 'github', name='oauthprovider', create_type=False),
            nullable=False,
        ),
        sa.Column('provider_user_id', sa.String(length=255), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('provider', 'provider_user_id', name='uq_oauth_provider_user'),
    )
    op.create_index(op.f('ix_oauth_accounts_user_id'), 'oauth_accounts', ['user_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_oauth_accounts_user_id'), table_name='oauth_accounts')
    op.drop_table('oauth_accounts')
    postgresql.ENUM('google', 'github', name='oauthprovider').drop(op.get_bind(), checkfirst=True)

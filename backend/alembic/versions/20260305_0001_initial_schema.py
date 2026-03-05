"""Initial schema

Revision ID: 20260305_0001
Revises: 
Create Date: 2026-03-05 10:00:00.000000

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '20260305_0001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    item_status = postgresql.ENUM('active', 'archived', name='itemstatus')
    item_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        'users',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('password_hash', sa.String(length=255), nullable=False),
        sa.Column('name', sa.String(length=120), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)

    op.create_table(
        'wishlists',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('owner_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('title', sa.String(length=140), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('event_date', sa.Date(), nullable=True),
        sa.Column('share_token', sa.String(length=32), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['owner_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_wishlists_owner_id'), 'wishlists', ['owner_id'], unique=False)
    op.create_index(op.f('ix_wishlists_share_token'), 'wishlists', ['share_token'], unique=True)

    op.create_table(
        'wishlist_items',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('wishlist_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('title', sa.String(length=240), nullable=False),
        sa.Column('product_url', sa.Text(), nullable=True),
        sa.Column('image_url', sa.Text(), nullable=True),
        sa.Column('price', sa.Numeric(10, 2), nullable=True),
        sa.Column('allow_contributions', sa.Boolean(), nullable=False),
        sa.Column('goal_amount', sa.Numeric(10, 2), nullable=True),
        sa.Column(
            'status',
            postgresql.ENUM('active', 'archived', name='itemstatus', create_type=False),
            nullable=False,
        ),
        sa.Column('archived_reason', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['wishlist_id'], ['wishlists.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_wishlist_items_wishlist_id'), 'wishlist_items', ['wishlist_id'], unique=False)

    op.create_table(
        'viewer_sessions',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('wishlist_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('display_name', sa.String(length=120), nullable=False),
        sa.Column('session_token', sa.String(length=64), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('last_seen_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['wishlist_id'], ['wishlists.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_viewer_sessions_session_token'), 'viewer_sessions', ['session_token'], unique=True)
    op.create_index(op.f('ix_viewer_sessions_wishlist_id'), 'viewer_sessions', ['wishlist_id'], unique=False)

    op.create_table(
        'reservations',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('item_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('session_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['item_id'], ['wishlist_items.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['session_id'], ['viewer_sessions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('item_id', 'session_id', name='uq_item_session_reservation'),
    )
    op.create_index(op.f('ix_reservations_item_id'), 'reservations', ['item_id'], unique=False)
    op.create_index(op.f('ix_reservations_session_id'), 'reservations', ['session_id'], unique=False)
    op.create_index(
        'uq_active_item_reservation',
        'reservations',
        ['item_id'],
        unique=True,
        postgresql_where=sa.text('revoked_at IS NULL'),
    )

    op.create_table(
        'contributions',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('item_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('session_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('amount', sa.Numeric(10, 2), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['item_id'], ['wishlist_items.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['session_id'], ['viewer_sessions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_contributions_item_id'), 'contributions', ['item_id'], unique=False)
    op.create_index(op.f('ix_contributions_session_id'), 'contributions', ['session_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_contributions_session_id'), table_name='contributions')
    op.drop_index(op.f('ix_contributions_item_id'), table_name='contributions')
    op.drop_table('contributions')

    op.drop_index('uq_active_item_reservation', table_name='reservations')
    op.drop_index(op.f('ix_reservations_session_id'), table_name='reservations')
    op.drop_index(op.f('ix_reservations_item_id'), table_name='reservations')
    op.drop_table('reservations')

    op.drop_index(op.f('ix_viewer_sessions_wishlist_id'), table_name='viewer_sessions')
    op.drop_index(op.f('ix_viewer_sessions_session_token'), table_name='viewer_sessions')
    op.drop_table('viewer_sessions')

    op.drop_index(op.f('ix_wishlist_items_wishlist_id'), table_name='wishlist_items')
    op.drop_table('wishlist_items')

    op.drop_index(op.f('ix_wishlists_share_token'), table_name='wishlists')
    op.drop_index(op.f('ix_wishlists_owner_id'), table_name='wishlists')
    op.drop_table('wishlists')

    op.drop_index(op.f('ix_users_email'), table_name='users')
    op.drop_table('users')

    postgresql.ENUM('active', 'archived', name='itemstatus').drop(op.get_bind(), checkfirst=True)

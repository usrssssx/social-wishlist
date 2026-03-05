from __future__ import annotations

import enum
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


class ItemStatus(str, enum.Enum):
    active = 'active'
    archived = 'archived'


class User(Base):
    __tablename__ = 'users'

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    name: Mapped[str] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    wishlists: Mapped[list[Wishlist]] = relationship(back_populates='owner', cascade='all, delete-orphan')


class Wishlist(Base):
    __tablename__ = 'wishlists'

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), index=True)
    title: Mapped[str] = mapped_column(String(140))
    description: Mapped[str] = mapped_column(Text(), default='')
    event_date: Mapped[Date | None] = mapped_column(Date, nullable=True)
    share_token: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    owner: Mapped[User] = relationship(back_populates='wishlists')
    items: Mapped[list[WishlistItem]] = relationship(back_populates='wishlist', cascade='all, delete-orphan')
    viewer_sessions: Mapped[list[ViewerSession]] = relationship(back_populates='wishlist', cascade='all, delete-orphan')


class WishlistItem(Base):
    __tablename__ = 'wishlist_items'

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    wishlist_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('wishlists.id', ondelete='CASCADE'), index=True)
    title: Mapped[str] = mapped_column(String(240))
    product_url: Mapped[str | None] = mapped_column(Text(), nullable=True)
    image_url: Mapped[str | None] = mapped_column(Text(), nullable=True)
    price: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    allow_contributions: Mapped[bool] = mapped_column(Boolean, default=False)
    goal_amount: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    status: Mapped[ItemStatus] = mapped_column(Enum(ItemStatus), default=ItemStatus.active)
    archived_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    wishlist: Mapped[Wishlist] = relationship(back_populates='items')
    reservations: Mapped[list[Reservation]] = relationship(back_populates='item', cascade='all, delete-orphan')
    contributions: Mapped[list[Contribution]] = relationship(back_populates='item', cascade='all, delete-orphan')


class ViewerSession(Base):
    __tablename__ = 'viewer_sessions'

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    wishlist_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('wishlists.id', ondelete='CASCADE'), index=True)
    display_name: Mapped[str] = mapped_column(String(120))
    session_token: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    wishlist: Mapped[Wishlist] = relationship(back_populates='viewer_sessions')
    reservations: Mapped[list[Reservation]] = relationship(back_populates='session', cascade='all, delete-orphan')
    contributions: Mapped[list[Contribution]] = relationship(back_populates='session', cascade='all, delete-orphan')


class Reservation(Base):
    __tablename__ = 'reservations'
    __table_args__ = (
        UniqueConstraint('item_id', 'session_id', name='uq_item_session_reservation'),
        Index(
            'uq_active_item_reservation',
            'item_id',
            unique=True,
            postgresql_where=text('revoked_at IS NULL'),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    item_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('wishlist_items.id', ondelete='CASCADE'), index=True)
    session_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('viewer_sessions.id', ondelete='CASCADE'), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    item: Mapped[WishlistItem] = relationship(back_populates='reservations')
    session: Mapped[ViewerSession] = relationship(back_populates='reservations')


class Contribution(Base):
    __tablename__ = 'contributions'

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    item_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('wishlist_items.id', ondelete='CASCADE'), index=True)
    session_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('viewer_sessions.id', ondelete='CASCADE'), index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    item: Mapped[WishlistItem] = relationship(back_populates='contributions')
    session: Mapped[ViewerSession] = relationship(back_populates='contributions')

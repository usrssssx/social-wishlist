from __future__ import annotations

import secrets
from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import and_, distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import get_settings
from ..models import Contribution, Reservation, ViewerSession, Wishlist, WishlistItem
from ..schemas import OwnerItemView, PublicItemView, WishlistOwnerDetail, WishlistPublicDetail

settings = get_settings()
ZERO = Decimal('0.00')


def _to_decimal(value: Decimal | None) -> Decimal:
    if value is None:
        return ZERO
    return Decimal(value).quantize(Decimal('0.01'))


def is_deadline_passed(event_date: date | None) -> bool:
    if not event_date:
        return False
    return date.today() > event_date


def collection_status(
    *,
    allow_contributions: bool,
    goal_amount: Decimal,
    contributed: Decimal,
    deadline_passed: bool,
) -> str:
    if not allow_contributions:
        return 'not_applicable'
    if goal_amount <= ZERO:
        return 'open'
    if contributed >= goal_amount:
        return 'funded'
    if deadline_passed and contributed > ZERO:
        return 'underfunded'
    if deadline_passed and contributed == ZERO:
        return 'deadline_passed'
    return 'open'


async def generate_share_token(db: AsyncSession) -> str:
    while True:
        token = secrets.token_urlsafe(9).replace('-', '').replace('_', '')[:14]
        exists = await db.execute(select(Wishlist.id).where(Wishlist.share_token == token))
        if exists.scalar_one_or_none() is None:
            return token


async def generate_viewer_token(db: AsyncSession) -> str:
    while True:
        token = secrets.token_urlsafe(18)
        exists = await db.execute(select(ViewerSession.id).where(ViewerSession.session_token == token))
        if exists.scalar_one_or_none() is None:
            return token


async def item_aggregates(db: AsyncSession, item_id: UUID) -> tuple[Decimal, int, Reservation | None]:
    contrib_result = await db.execute(
        select(
            func.coalesce(func.sum(Contribution.amount), 0),
            func.count(distinct(Contribution.session_id)),
        ).where(Contribution.item_id == item_id)
    )
    contributed_amount, contributors_count = contrib_result.one()
    reservation_result = await db.execute(
        select(Reservation)
        .where(and_(Reservation.item_id == item_id, Reservation.revoked_at.is_(None)))
        .limit(1)
    )
    active_reservation = reservation_result.scalar_one_or_none()
    return _to_decimal(contributed_amount), int(contributors_count or 0), active_reservation


async def to_owner_item_view(db: AsyncSession, item: WishlistItem, wishlist: Wishlist) -> OwnerItemView:
    contributed, contributors_count, active_reservation = await item_aggregates(db, item.id)
    goal = _to_decimal(item.goal_amount) if item.goal_amount is not None else _to_decimal(item.price)
    deadline_passed = is_deadline_passed(wishlist.event_date)
    status = collection_status(
        allow_contributions=item.allow_contributions,
        goal_amount=goal,
        contributed=contributed,
        deadline_passed=deadline_passed,
    )
    contributions_locked = item.allow_contributions and deadline_passed and contributed < goal
    remaining_amount = None
    if item.allow_contributions and goal > ZERO:
        remaining_amount = (goal - contributed if contributed < goal else ZERO).quantize(Decimal('0.01'))

    reserved = active_reservation is not None or (item.allow_contributions and goal > ZERO and contributed >= goal)

    return OwnerItemView(
        id=item.id,
        title=item.title,
        product_url=item.product_url,
        image_url=item.image_url,
        price=_to_decimal(item.price) if item.price is not None else None,
        allow_contributions=item.allow_contributions,
        goal_amount=_to_decimal(item.goal_amount) if item.goal_amount is not None else None,
        status=item.status.value,
        archived_reason=item.archived_reason,
        reserved=reserved,
        contributed_amount=contributed,
        contributors_count=contributors_count,
        contributions_locked=contributions_locked,
        collection_status=status,
        remaining_amount=remaining_amount,
        created_at=item.created_at,
    )


async def to_public_item_view(
    db: AsyncSession,
    wishlist: Wishlist,
    item: WishlistItem,
    current_session: ViewerSession | None,
) -> PublicItemView:
    contributed, contributors_count, active_reservation = await item_aggregates(db, item.id)
    goal_amount = _to_decimal(item.goal_amount) if item.goal_amount is not None else _to_decimal(item.price)
    deadline_passed = is_deadline_passed(wishlist.event_date)
    status = collection_status(
        allow_contributions=item.allow_contributions,
        goal_amount=goal_amount,
        contributed=contributed,
        deadline_passed=deadline_passed,
    )
    contributions_locked = item.allow_contributions and deadline_passed and contributed < goal_amount
    remaining_amount = None
    if item.allow_contributions and goal_amount > ZERO:
        remaining_amount = (goal_amount - contributed if contributed < goal_amount else ZERO).quantize(Decimal('0.01'))

    reserved_by_me = bool(
        current_session
        and active_reservation
        and active_reservation.session_id == current_session.id
    )
    reserved_by_someone = active_reservation is not None
    reserved_by_funding = bool(item.allow_contributions and goal_amount > ZERO and contributed >= goal_amount)
    reserved = reserved_by_someone or reserved_by_funding

    progress_percent = 0
    if item.allow_contributions and goal_amount > ZERO:
        progress_percent = int(min(100, (contributed / goal_amount) * 100))

    can_reserve = item.status.value == 'active' and not deadline_passed and not reserved and contributed == ZERO
    can_contribute = (
        item.status.value == 'active'
        and item.allow_contributions
        and not contributions_locked
        and not reserved_by_someone
        and (goal_amount == ZERO or contributed < goal_amount)
    )

    return PublicItemView(
        id=item.id,
        title=item.title,
        product_url=item.product_url,
        image_url=item.image_url,
        price=_to_decimal(item.price) if item.price is not None else None,
        allow_contributions=item.allow_contributions,
        goal_amount=_to_decimal(item.goal_amount) if item.goal_amount is not None else None,
        status=item.status.value,
        archived_reason=item.archived_reason,
        reserved=reserved,
        reserved_by_me=reserved_by_me,
        can_reserve=can_reserve,
        can_contribute=can_contribute,
        contributed_amount=contributed,
        contributors_count=contributors_count,
        progress_percent=progress_percent,
        contributions_locked=contributions_locked,
        collection_status=status,
        remaining_amount=remaining_amount,
    )


async def get_owner_wishlist_detail(db: AsyncSession, wishlist: Wishlist) -> WishlistOwnerDetail:
    items_result = await db.execute(
        select(WishlistItem)
        .where(WishlistItem.wishlist_id == wishlist.id)
        .order_by(WishlistItem.created_at.desc())
    )
    items = items_result.scalars().all()
    owner_items = [await to_owner_item_view(db, item, wishlist) for item in items]

    return WishlistOwnerDetail(
        id=wishlist.id,
        title=wishlist.title,
        description=wishlist.description,
        event_date=wishlist.event_date,
        deadline_passed=is_deadline_passed(wishlist.event_date),
        share_token=wishlist.share_token,
        items=owner_items,
    )


async def get_public_wishlist_detail(
    db: AsyncSession,
    wishlist: Wishlist,
    current_session: ViewerSession | None,
) -> WishlistPublicDetail:
    items_result = await db.execute(
        select(WishlistItem)
        .where(WishlistItem.wishlist_id == wishlist.id)
        .order_by(WishlistItem.created_at.desc())
    )
    items = items_result.scalars().all()
    public_items = [await to_public_item_view(db, wishlist, item, current_session) for item in items]

    return WishlistPublicDetail(
        id=wishlist.id,
        title=wishlist.title,
        description=wishlist.description,
        event_date=wishlist.event_date,
        deadline_passed=is_deadline_passed(wishlist.event_date),
        share_token=wishlist.share_token,
        items=public_items,
    )


async def get_wishlist_by_token(db: AsyncSession, share_token: str) -> Wishlist:
    result = await db.execute(select(Wishlist).where(Wishlist.share_token == share_token))
    wishlist = result.scalar_one_or_none()
    if not wishlist:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Wishlist not found')
    return wishlist


async def get_viewer_session(db: AsyncSession, share_token: str, session_token: str | None) -> ViewerSession | None:
    if not session_token:
        return None
    wishlist = await get_wishlist_by_token(db, share_token)
    result = await db.execute(
        select(ViewerSession).where(
            and_(
                ViewerSession.wishlist_id == wishlist.id,
                ViewerSession.session_token == session_token,
            )
        )
    )
    session = result.scalar_one_or_none()
    if session:
        session.last_seen_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(session)
    return session


async def require_viewer_session(db: AsyncSession, wishlist_id: UUID, session_token: str | None) -> ViewerSession:
    if not session_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Viewer session required')
    result = await db.execute(
        select(ViewerSession).where(
            and_(
                ViewerSession.wishlist_id == wishlist_id,
                ViewerSession.session_token == session_token,
            )
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Invalid viewer session')
    return session


def validate_contribution_amount(amount: Decimal) -> None:
    min_amount = Decimal(str(settings.min_contribution_amount)).quantize(Decimal('0.01'))
    if amount < min_amount:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f'Minimal contribution amount is {min_amount}',
        )

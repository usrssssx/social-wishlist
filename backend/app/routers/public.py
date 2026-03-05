from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Body, Depends, Header, HTTPException, Request, status
from sqlalchemy import and_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_db
from ..models import Contribution, Reservation, ViewerSession, WishlistItem
from ..rate_limit import limiter
from ..schemas import (
    ContributionCreateRequest,
    ContributionResponse,
    ReserveResponse,
    ViewerSessionCreateRequest,
    ViewerSessionResponse,
    WishlistPublicDetail,
)
from ..services.captcha_service import verify_captcha_or_skip
from ..services.realtime import hub
from ..services.wishlist_service import (
    ZERO,
    generate_viewer_token,
    get_public_wishlist_detail,
    get_wishlist_by_token,
    require_viewer_session,
    is_deadline_passed,
    validate_contribution_amount,
)

router = APIRouter(prefix='/api/public', tags=['public'])


@router.get('/w/{share_token}', response_model=WishlistPublicDetail)
async def public_wishlist(
    share_token: str,
    db: AsyncSession = Depends(get_db),
    x_viewer_token: str | None = Header(default=None),
) -> WishlistPublicDetail:
    wishlist = await get_wishlist_by_token(db, share_token)

    current_session = None
    if x_viewer_token:
        result = await db.execute(
            select(ViewerSession).where(
                and_(
                    ViewerSession.wishlist_id == wishlist.id,
                    ViewerSession.session_token == x_viewer_token,
                )
            )
        )
        current_session = result.scalar_one_or_none()

    return await get_public_wishlist_detail(db, wishlist, current_session)


@router.post('/w/{share_token}/sessions', response_model=ViewerSessionResponse)
@limiter.limit('20/hour')
async def create_viewer_session(
    request: Request,
    share_token: str,
    payload: ViewerSessionCreateRequest = Body(...),
    db: AsyncSession = Depends(get_db),
) -> ViewerSessionResponse:
    await verify_captcha_or_skip(payload.captcha_token, request.client.host if request.client else None)
    wishlist = await get_wishlist_by_token(db, share_token)
    session_token = await generate_viewer_token(db)

    session = ViewerSession(
        wishlist_id=wishlist.id,
        display_name=payload.display_name.strip(),
        session_token=session_token,
    )
    db.add(session)
    await db.commit()

    await hub.publish_update(share_token, 'viewer_joined')
    return ViewerSessionResponse(display_name=session.display_name, session_token=session.session_token)


@router.post('/w/{share_token}/items/{item_id}/reserve', response_model=ReserveResponse)
@limiter.limit('60/hour')
async def reserve_item(
    request: Request,
    share_token: str,
    item_id: UUID,
    db: AsyncSession = Depends(get_db),
    x_viewer_token: str | None = Header(default=None),
) -> ReserveResponse:
    _ = request
    wishlist = await get_wishlist_by_token(db, share_token)
    session = await require_viewer_session(db, wishlist.id, x_viewer_token)
    if is_deadline_passed(wishlist.event_date):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail='Wishlist deadline passed. New reservations are closed.',
        )

    try:
        item_result = await db.execute(
            select(WishlistItem)
            .where(and_(WishlistItem.id == item_id, WishlistItem.wishlist_id == wishlist.id))
            .with_for_update()
        )
        item = item_result.scalar_one_or_none()
        if not item:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Item not found')

        if item.status.value != 'active':
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail='Item is archived')

        active_reservation_result = await db.execute(
            select(Reservation)
            .where(and_(Reservation.item_id == item.id, Reservation.revoked_at.is_(None)))
            .with_for_update()
        )
        active_reservation = active_reservation_result.scalar_one_or_none()
        if active_reservation:
            if active_reservation.session_id == session.id:
                await db.rollback()
                return ReserveResponse(ok=True)
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail='Item already reserved')

        contributions_result = await db.execute(
            select(Contribution).where(Contribution.item_id == item.id).with_for_update()
        )
        contributions = contributions_result.scalars().all()
        contributed = sum(
            (Decimal(c.amount).quantize(Decimal('0.01')) for c in contributions),
            start=ZERO,
        )
        if contributed > ZERO:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail='Cannot reserve item with active contributions',
            )

        reservation = Reservation(item_id=item.id, session_id=session.id)
        db.add(reservation)
        await db.commit()
    except HTTPException:
        await db.rollback()
        raise
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail='Item already reserved') from exc

    await hub.publish_update(share_token, 'item_reserved', str(item.id))
    return ReserveResponse(ok=True)


@router.delete('/w/{share_token}/items/{item_id}/reserve', response_model=ReserveResponse)
@limiter.limit('60/hour')
async def unreserve_item(
    request: Request,
    share_token: str,
    item_id: UUID,
    db: AsyncSession = Depends(get_db),
    x_viewer_token: str | None = Header(default=None),
) -> ReserveResponse:
    _ = request
    wishlist = await get_wishlist_by_token(db, share_token)
    session = await require_viewer_session(db, wishlist.id, x_viewer_token)
    try:
        reservation_result = await db.execute(
            select(Reservation)
            .join(WishlistItem, Reservation.item_id == WishlistItem.id)
            .where(
                and_(
                    Reservation.item_id == item_id,
                    Reservation.session_id == session.id,
                    Reservation.revoked_at.is_(None),
                    WishlistItem.wishlist_id == wishlist.id,
                )
            )
            .with_for_update()
        )
        reservation = reservation_result.scalar_one_or_none()
        if not reservation:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Reservation not found')

        reservation.revoked_at = datetime.now(timezone.utc)
        await db.commit()
    except HTTPException:
        await db.rollback()
        raise

    await hub.publish_update(share_token, 'item_unreserved', str(item_id))
    return ReserveResponse(ok=True)


@router.post('/w/{share_token}/items/{item_id}/contributions', response_model=ContributionResponse)
@limiter.limit('60/hour')
async def contribute(
    request: Request,
    share_token: str,
    item_id: UUID,
    payload: ContributionCreateRequest = Body(...),
    db: AsyncSession = Depends(get_db),
    x_viewer_token: str | None = Header(default=None),
) -> ContributionResponse:
    _ = request
    wishlist = await get_wishlist_by_token(db, share_token)
    session = await require_viewer_session(db, wishlist.id, x_viewer_token)
    if is_deadline_passed(wishlist.event_date):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail='Wishlist deadline passed. Contributions are closed.',
        )

    validate_contribution_amount(payload.amount)
    funded_now = False

    try:
        item_result = await db.execute(
            select(WishlistItem)
            .where(and_(WishlistItem.id == item_id, WishlistItem.wishlist_id == wishlist.id))
            .with_for_update()
        )
        item = item_result.scalar_one_or_none()
        if not item:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Item not found')

        if item.status.value != 'active':
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail='Item is archived')
        if not item.allow_contributions:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Contributions are disabled')

        active_reservation_result = await db.execute(
            select(Reservation)
            .where(and_(Reservation.item_id == item.id, Reservation.revoked_at.is_(None)))
            .with_for_update()
        )
        if active_reservation_result.scalar_one_or_none() is not None:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail='Item already reserved')

        contributions_result = await db.execute(
            select(Contribution).where(Contribution.item_id == item.id).with_for_update()
        )
        contributions = contributions_result.scalars().all()
        current_total = sum(
            (Decimal(c.amount).quantize(Decimal('0.01')) for c in contributions),
            start=ZERO,
        )

        goal_amount = item.goal_amount if item.goal_amount is not None else item.price
        if goal_amount is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Goal amount is not set')

        goal = Decimal(goal_amount).quantize(Decimal('0.01'))
        if current_total >= goal:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail='Goal already reached')

        remaining = (goal - current_total).quantize(Decimal('0.01'))
        if payload.amount > remaining:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f'Contribution exceeds remaining amount ({remaining})',
            )

        contribution = Contribution(item_id=item.id, session_id=session.id, amount=payload.amount)
        db.add(contribution)
        funded_now = payload.amount == remaining
        await db.commit()
    except HTTPException:
        await db.rollback()
        raise

    await hub.publish_update(share_token, 'item_contribution', str(item.id))
    if funded_now:
        await hub.publish_update(share_token, 'item_funded', str(item.id))

    return ContributionResponse(ok=True)

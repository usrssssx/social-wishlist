from __future__ import annotations

from decimal import Decimal
from urllib.parse import urlparse
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_db
from ..deps import get_current_user
from ..models import ItemStatus, User, Wishlist, WishlistItem
from ..schemas import (
    AutofillResponse,
    ItemCreateRequest,
    ItemUpdateRequest,
    WishlistCreateRequest,
    WishlistOwnerDetail,
    WishlistSummary,
)
from ..services.metadata_service import scrape_product_metadata
from ..services.realtime import hub
from ..services.wishlist_service import (
    ZERO,
    generate_share_token,
    get_owner_wishlist_detail,
    item_aggregates,
)

router = APIRouter(prefix='/api/wishlists', tags=['wishlists'])


def _clean_url(url: str | None) -> str | None:
    if not url:
        return None
    parsed = urlparse(str(url))
    if parsed.scheme not in {'http', 'https'}:
        return None
    return str(url)


@router.post('', response_model=WishlistOwnerDetail)
async def create_wishlist(
    payload: WishlistCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> WishlistOwnerDetail:
    share_token = await generate_share_token(db)
    wishlist = Wishlist(
        owner_id=current_user.id,
        title=payload.title.strip(),
        description=payload.description.strip(),
        event_date=payload.event_date,
        share_token=share_token,
    )
    db.add(wishlist)
    await db.commit()
    await db.refresh(wishlist)

    return await get_owner_wishlist_detail(db, wishlist)


@router.get('', response_model=list[WishlistSummary])
async def list_wishlists(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[WishlistSummary]:
    result = await db.execute(
        select(Wishlist)
        .where(Wishlist.owner_id == current_user.id)
        .order_by(Wishlist.created_at.desc())
    )
    wishlists = result.scalars().all()

    response: list[WishlistSummary] = []
    for wishlist in wishlists:
        detail = await get_owner_wishlist_detail(db, wishlist)
        reserved_count = sum(1 for item in detail.items if item.reserved)
        funded_amount = sum((item.contributed_amount for item in detail.items), start=ZERO)
        response.append(
            WishlistSummary(
                id=wishlist.id,
                title=wishlist.title,
                description=wishlist.description,
                event_date=wishlist.event_date,
                share_token=wishlist.share_token,
                item_count=len(detail.items),
                reserved_count=reserved_count,
                funded_amount=Decimal(funded_amount).quantize(Decimal('0.01')),
            )
        )

    return response


@router.get('/{wishlist_id}', response_model=WishlistOwnerDetail)
async def get_wishlist(
    wishlist_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> WishlistOwnerDetail:
    result = await db.execute(
        select(Wishlist).where(and_(Wishlist.id == wishlist_id, Wishlist.owner_id == current_user.id))
    )
    wishlist = result.scalar_one_or_none()
    if not wishlist:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Wishlist not found')

    return await get_owner_wishlist_detail(db, wishlist)


@router.post('/{wishlist_id}/items', response_model=WishlistOwnerDetail)
async def create_item(
    wishlist_id: UUID,
    payload: ItemCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> WishlistOwnerDetail:
    wishlist_result = await db.execute(
        select(Wishlist).where(and_(Wishlist.id == wishlist_id, Wishlist.owner_id == current_user.id))
    )
    wishlist = wishlist_result.scalar_one_or_none()
    if not wishlist:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Wishlist not found')

    if payload.allow_contributions and payload.goal_amount is None and payload.price is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='Set price or goal amount to enable contributions',
        )

    goal_amount = payload.goal_amount
    if payload.allow_contributions and goal_amount is None:
        goal_amount = payload.price

    item = WishlistItem(
        wishlist_id=wishlist.id,
        title=payload.title.strip(),
        product_url=_clean_url(str(payload.product_url)) if payload.product_url else None,
        image_url=_clean_url(str(payload.image_url)) if payload.image_url else None,
        price=payload.price,
        allow_contributions=payload.allow_contributions,
        goal_amount=goal_amount,
    )
    db.add(item)
    await db.commit()

    await hub.publish_update(wishlist.share_token, 'item_created', str(item.id))
    return await get_owner_wishlist_detail(db, wishlist)


@router.patch('/items/{item_id}', response_model=WishlistOwnerDetail)
async def update_item(
    item_id: UUID,
    payload: ItemUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> WishlistOwnerDetail:
    result = await db.execute(
        select(WishlistItem, Wishlist)
        .join(Wishlist, WishlistItem.wishlist_id == Wishlist.id)
        .where(and_(WishlistItem.id == item_id, Wishlist.owner_id == current_user.id))
    )
    row = result.first()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Item not found')

    item, wishlist = row

    updates = payload.model_dump(exclude_unset=True)
    if 'title' in updates and updates['title']:
        item.title = updates['title'].strip()
    if 'product_url' in updates:
        item.product_url = _clean_url(str(updates['product_url'])) if updates['product_url'] else None
    if 'image_url' in updates:
        item.image_url = _clean_url(str(updates['image_url'])) if updates['image_url'] else None
    if 'price' in updates:
        item.price = updates['price']
    if 'allow_contributions' in updates:
        item.allow_contributions = updates['allow_contributions']
    if 'goal_amount' in updates:
        item.goal_amount = updates['goal_amount']

    if item.allow_contributions and item.goal_amount is None and item.price is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='Set price or goal amount to enable contributions',
        )
    if item.allow_contributions and item.goal_amount is None:
        item.goal_amount = item.price
    if not item.allow_contributions:
        item.goal_amount = None

    await db.commit()
    await hub.publish_update(wishlist.share_token, 'item_updated', str(item.id))
    return await get_owner_wishlist_detail(db, wishlist)


@router.delete('/items/{item_id}', response_model=WishlistOwnerDetail)
async def delete_item(
    item_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> WishlistOwnerDetail:
    result = await db.execute(
        select(WishlistItem, Wishlist)
        .join(Wishlist, WishlistItem.wishlist_id == Wishlist.id)
        .where(and_(WishlistItem.id == item_id, Wishlist.owner_id == current_user.id))
    )
    row = result.first()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Item not found')

    item, wishlist = row
    contributed, _, active_reservation = await item_aggregates(db, item.id)

    if contributed > ZERO or active_reservation is not None:
        item.status = ItemStatus.archived
        item.archived_reason = 'Товар скрыт владельцем после бронирования/сбора. Уточните замену лично.'
    else:
        await db.delete(item)

    await db.commit()
    await hub.publish_update(wishlist.share_token, 'item_removed', str(item.id))
    return await get_owner_wishlist_detail(db, wishlist)


@router.get('/items/autofill', response_model=AutofillResponse)
async def autofill_item(
    url: str = Query(...),
    current_user: User = Depends(get_current_user),
) -> AutofillResponse:
    _ = current_user
    parsed = urlparse(url)
    if parsed.scheme not in {'http', 'https'} or not parsed.netloc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Invalid URL')

    try:
        metadata = await scrape_product_metadata(url)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail='Cannot parse product page') from exc

    return AutofillResponse(**metadata)

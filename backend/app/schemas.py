from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import AnyHttpUrl, BaseModel, EmailStr, Field


class TokenPayload(BaseModel):
    sub: str
    exp: int


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    name: str = Field(min_length=2, max_length=120)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RegisterResponse(BaseModel):
    ok: bool = True
    detail: str


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = 'bearer'
    user: 'UserResponse'


class UserResponse(BaseModel):
    id: UUID
    email: EmailStr
    name: str
    created_at: datetime

    model_config = {'from_attributes': True}


class EmailActionRequest(BaseModel):
    email: EmailStr


class EmailActionConfirmRequest(BaseModel):
    token: str = Field(min_length=16, max_length=255)


class PasswordResetConfirmRequest(BaseModel):
    token: str = Field(min_length=16, max_length=255)
    new_password: str = Field(min_length=8, max_length=128)


class GenericMessageResponse(BaseModel):
    ok: bool = True
    detail: str


class WishlistCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=140)
    description: str = Field(default='', max_length=3000)
    event_date: date | None = None


class WishlistSummary(BaseModel):
    id: UUID
    title: str
    description: str
    event_date: date | None
    share_token: str
    item_count: int
    reserved_count: int
    funded_amount: Decimal


class ItemCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=240)
    product_url: AnyHttpUrl | None = None
    image_url: AnyHttpUrl | None = None
    price: Decimal | None = Field(default=None, ge=0)
    allow_contributions: bool = False
    goal_amount: Decimal | None = Field(default=None, ge=0)


class ItemUpdateRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=240)
    product_url: AnyHttpUrl | None = None
    image_url: AnyHttpUrl | None = None
    price: Decimal | None = Field(default=None, ge=0)
    allow_contributions: bool | None = None
    goal_amount: Decimal | None = Field(default=None, ge=0)


class OwnerItemView(BaseModel):
    id: UUID
    title: str
    product_url: str | None
    image_url: str | None
    price: Decimal | None
    allow_contributions: bool
    goal_amount: Decimal | None
    status: str
    archived_reason: str | None
    reserved: bool
    contributed_amount: Decimal
    contributors_count: int
    contributions_locked: bool
    collection_status: str
    remaining_amount: Decimal | None
    created_at: datetime


class WishlistOwnerDetail(BaseModel):
    id: UUID
    title: str
    description: str
    event_date: date | None
    deadline_passed: bool
    share_token: str
    items: list[OwnerItemView]


class ViewerSessionCreateRequest(BaseModel):
    display_name: str = Field(min_length=2, max_length=120)


class ViewerSessionResponse(BaseModel):
    display_name: str
    session_token: str


class PublicItemView(BaseModel):
    id: UUID
    title: str
    product_url: str | None
    image_url: str | None
    price: Decimal | None
    allow_contributions: bool
    goal_amount: Decimal | None
    status: str
    archived_reason: str | None
    reserved: bool
    reserved_by_me: bool
    can_reserve: bool
    can_contribute: bool
    contributed_amount: Decimal
    contributors_count: int
    progress_percent: int
    contributions_locked: bool
    collection_status: str
    remaining_amount: Decimal | None


class WishlistPublicDetail(BaseModel):
    id: UUID
    title: str
    description: str
    event_date: date | None
    deadline_passed: bool
    share_token: str
    items: list[PublicItemView]


class ReserveResponse(BaseModel):
    ok: bool


class ContributionCreateRequest(BaseModel):
    amount: Decimal = Field(gt=0)


class ContributionResponse(BaseModel):
    ok: bool


class AutofillResponse(BaseModel):
    title: str | None
    image_url: str | None
    price: Decimal | None
    url: str


class RealtimeEvent(BaseModel):
    type: str
    item_id: UUID | None = None
    timestamp: datetime

export type User = {
  id: string;
  email: string;
  name: string;
  created_at: string;
};

export type AuthResponse = {
  access_token: string;
  token_type: 'bearer';
  user: User;
};

export type RegisterResponse = {
  ok: boolean;
  detail: string;
};

export type GenericMessageResponse = {
  ok: boolean;
  detail: string;
};

export type WishlistSummary = {
  id: string;
  title: string;
  description: string;
  event_date: string | null;
  share_token: string;
  item_count: number;
  reserved_count: number;
  funded_amount: string;
};

export type OwnerItem = {
  id: string;
  title: string;
  product_url: string | null;
  image_url: string | null;
  price: string | null;
  allow_contributions: boolean;
  goal_amount: string | null;
  status: 'active' | 'archived';
  archived_reason: string | null;
  reserved: boolean;
  contributed_amount: string;
  contributors_count: number;
  contributions_locked: boolean;
  collection_status: 'not_applicable' | 'open' | 'funded' | 'underfunded' | 'deadline_passed';
  remaining_amount: string | null;
  created_at: string;
};

export type WishlistOwnerDetail = {
  id: string;
  title: string;
  description: string;
  event_date: string | null;
  deadline_passed: boolean;
  share_token: string;
  items: OwnerItem[];
};

export type PublicItem = {
  id: string;
  title: string;
  product_url: string | null;
  image_url: string | null;
  price: string | null;
  allow_contributions: boolean;
  goal_amount: string | null;
  status: 'active' | 'archived';
  archived_reason: string | null;
  reserved: boolean;
  reserved_by_me: boolean;
  can_reserve: boolean;
  can_contribute: boolean;
  contributed_amount: string;
  contributors_count: number;
  progress_percent: number;
  contributions_locked: boolean;
  collection_status: 'not_applicable' | 'open' | 'funded' | 'underfunded' | 'deadline_passed';
  remaining_amount: string | null;
};

export type WishlistPublicDetail = {
  id: string;
  title: string;
  description: string;
  event_date: string | null;
  deadline_passed: boolean;
  share_token: string;
  items: PublicItem[];
};

export type AutofillResponse = {
  title: string | null;
  image_url: string | null;
  price: string | null;
  url: string;
};

import type {
  AuthResponse,
  AutofillResponse,
  GenericMessageResponse,
  RegisterResponse,
  WishlistOwnerDetail,
  WishlistPublicDetail,
  WishlistSummary
} from './types';

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';

type HttpMethod = 'GET' | 'POST' | 'PATCH' | 'DELETE';

const LEGACY_ERROR_MAP: Record<string, string> = {
  'Request failed with status 500': 'Сервер временно недоступен. Попробуйте чуть позже.',
  'Request failed with status 429': 'Слишком много попыток. Подождите немного и попробуйте снова.',
  'Captcha token required': 'Подтвердите, что вы не робот.',
  'Invalid captcha token': 'Проверка CAPTCHA не пройдена. Попробуйте еще раз.',
  'Captcha verification failed': 'Не удалось проверить CAPTCHA. Попробуйте еще раз.',
  'Invalid credentials': 'Неверный email или пароль.',
  'Email already in use': 'Этот email уже занят.',
  'Email is not verified. Please confirm email before login.': 'Подтвердите email перед входом.',
  'Invalid or expired token': 'Ссылка недействительна или устарела.',
};

function formatApiError(errorPayload: unknown, statusCode: number): string {
  const fallbackByStatus: Record<number, string> = {
    400: 'Проверьте введенные данные.',
    401: 'Нужно войти в систему.',
    403: 'Доступ запрещен.',
    404: 'Ничего не найдено.',
    409: 'Сейчас это действие недоступно.',
    422: 'Проверьте, как заполнены поля формы.',
    429: 'Слишком много попыток. Подождите немного и попробуйте снова.',
    500: 'Сервер временно недоступен. Попробуйте чуть позже.',
    502: 'Сервис временно недоступен. Попробуйте чуть позже.',
    503: 'Сервис временно недоступен. Попробуйте чуть позже.'
  };
  const fallback = fallbackByStatus[statusCode] ?? 'Произошла ошибка. Попробуйте снова.';

  if (!errorPayload || typeof errorPayload !== 'object') {
    return fallback;
  }

  const detail = (errorPayload as { detail?: unknown }).detail;
  if (typeof detail === 'string') {
    return LEGACY_ERROR_MAP[detail] ?? detail;
  }

  if (Array.isArray(detail)) {
    const messages = detail
      .map((item) => {
        if (!item || typeof item !== 'object') return null;
        const msg = (item as { msg?: unknown }).msg;
        const loc = (item as { loc?: unknown }).loc;
        if (typeof msg !== 'string') return null;
        if (!Array.isArray(loc)) return msg;
        const locPath = loc.map((x) => String(x)).join('.');
        return `${msg} (${locPath})`;
      })
      .filter((x): x is string => Boolean(x));

    if (messages.length > 0) {
      return messages.join('; ');
    }
  }

  if (detail !== undefined) {
    try {
      return JSON.stringify(detail);
    } catch {
      return fallback;
    }
  }

  return fallback;
}

async function request<T>(
  path: string,
  options: {
    method?: HttpMethod;
    body?: unknown;
    token?: string | null;
    viewerToken?: string | null;
  } = {}
): Promise<T> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json'
  };

  if (options.token) {
    headers.Authorization = `Bearer ${options.token}`;
  }

  if (options.viewerToken) {
    headers['X-Viewer-Token'] = options.viewerToken;
  }

  const response = await fetch(`${API_URL}${path}`, {
    method: options.method ?? 'GET',
    headers,
    body: options.body ? JSON.stringify(options.body) : undefined,
    cache: 'no-store'
  });

  if (!response.ok) {
    const errorPayload = await response.json().catch(() => null);
    const message = formatApiError(errorPayload, response.status);
    throw new Error(message);
  }

  return response.json() as Promise<T>;
}

export const api = {
  register(email: string, password: string, name: string, captchaToken?: string | null) {
    return request<RegisterResponse>('/api/auth/register', {
      method: 'POST',
      body: { email, password, name, captcha_token: captchaToken ?? null }
    });
  },

  login(email: string, password: string, captchaToken?: string | null) {
    return request<AuthResponse>('/api/auth/login', {
      method: 'POST',
      body: { email, password, captcha_token: captchaToken ?? null }
    });
  },

  resendVerification(email: string, captchaToken?: string | null) {
    return request<GenericMessageResponse>('/api/auth/resend-verification', {
      method: 'POST',
      body: { email, captcha_token: captchaToken ?? null }
    });
  },

  verifyEmail(token: string) {
    return request<GenericMessageResponse>('/api/auth/verify-email/confirm', {
      method: 'POST',
      body: { token }
    });
  },

  requestPasswordReset(email: string, captchaToken?: string | null) {
    return request<GenericMessageResponse>('/api/auth/password-reset/request', {
      method: 'POST',
      body: { email, captcha_token: captchaToken ?? null }
    });
  },

  confirmPasswordReset(token: string, newPassword: string) {
    return request<GenericMessageResponse>('/api/auth/password-reset/confirm', {
      method: 'POST',
      body: { token, new_password: newPassword }
    });
  },

  me(token: string) {
    return request('/api/auth/me', { token });
  },

  listWishlists(token: string) {
    return request<WishlistSummary[]>('/api/wishlists', { token });
  },

  createWishlist(token: string, payload: { title: string; description: string; event_date: string | null }) {
    return request<WishlistOwnerDetail>('/api/wishlists', {
      method: 'POST',
      token,
      body: payload
    });
  },

  getWishlist(token: string, wishlistId: string) {
    return request<WishlistOwnerDetail>(`/api/wishlists/${wishlistId}`, { token });
  },

  createItem(
    token: string,
    wishlistId: string,
    payload: {
      title: string;
      product_url: string | null;
      image_url: string | null;
      price: number | null;
      allow_contributions: boolean;
      goal_amount: number | null;
    }
  ) {
    return request<WishlistOwnerDetail>(`/api/wishlists/${wishlistId}/items`, {
      method: 'POST',
      token,
      body: payload
    });
  },

  updateItem(
    token: string,
    itemId: string,
    payload: {
      title?: string;
      product_url?: string | null;
      image_url?: string | null;
      price?: number | null;
      allow_contributions?: boolean;
      goal_amount?: number | null;
    }
  ) {
    return request<WishlistOwnerDetail>(`/api/wishlists/items/${itemId}`, {
      method: 'PATCH',
      token,
      body: payload
    });
  },

  deleteItem(token: string, itemId: string) {
    return request<WishlistOwnerDetail>(`/api/wishlists/items/${itemId}`, {
      method: 'DELETE',
      token
    });
  },

  autofill(token: string, url: string) {
    return request<AutofillResponse>(`/api/wishlists/items/autofill?url=${encodeURIComponent(url)}`, { token });
  },

  getPublicWishlist(shareToken: string, viewerToken: string | null) {
    return request<WishlistPublicDetail>(`/api/public/w/${shareToken}`, {
      viewerToken
    });
  },

  createViewerSession(shareToken: string, displayName: string, captchaToken?: string | null) {
    return request<{ display_name: string; session_token: string }>(`/api/public/w/${shareToken}/sessions`, {
      method: 'POST',
      body: { display_name: displayName, captcha_token: captchaToken ?? null }
    });
  },

  reserveItem(shareToken: string, itemId: string, viewerToken: string) {
    return request<{ ok: boolean }>(`/api/public/w/${shareToken}/items/${itemId}/reserve`, {
      method: 'POST',
      viewerToken
    });
  },

  unreserveItem(shareToken: string, itemId: string, viewerToken: string) {
    return request<{ ok: boolean }>(`/api/public/w/${shareToken}/items/${itemId}/reserve`, {
      method: 'DELETE',
      viewerToken
    });
  },

  contribute(shareToken: string, itemId: string, amount: number, viewerToken: string) {
    return request<{ ok: boolean }>(`/api/public/w/${shareToken}/items/${itemId}/contributions`, {
      method: 'POST',
      viewerToken,
      body: { amount }
    });
  }
};

export function getWsUrl(shareToken: string): string {
  const base = API_URL.replace('http://', 'ws://').replace('https://', 'wss://');
  return `${base}/ws/w/${shareToken}`;
}

export function formatMoney(value: string | number | null | undefined): string {
  if (value === null || value === undefined || value === '') {
    return '—';
  }
  const amount = Number(value);
  if (Number.isNaN(amount)) {
    return '—';
  }
  return new Intl.NumberFormat('ru-RU', {
    style: 'currency',
    currency: 'RUB',
    maximumFractionDigits: 0
  }).format(amount);
}

export function getAuthToken(): string | null {
  if (typeof window === 'undefined') {
    return null;
  }
  return localStorage.getItem('swl_auth_token');
}

export function setAuthToken(token: string) {
  localStorage.setItem('swl_auth_token', token);
}

export function clearAuthToken() {
  localStorage.removeItem('swl_auth_token');
}

export function getViewerToken(shareToken: string): string | null {
  if (typeof window === 'undefined') {
    return null;
  }
  return localStorage.getItem(`swl_viewer_${shareToken}`);
}

export function setViewerToken(shareToken: string, token: string) {
  localStorage.setItem(`swl_viewer_${shareToken}`, token);
}

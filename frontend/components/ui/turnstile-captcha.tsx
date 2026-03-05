'use client';

import { useEffect, useRef, useState } from 'react';

type TurnstileApi = {
  render: (container: HTMLElement, options: Record<string, unknown>) => string;
  remove: (widgetId: string) => void;
  execute?: (widgetId: string) => void;
};

declare global {
  interface Window {
    turnstile?: TurnstileApi;
    __turnstileLoader?: Promise<void>;
  }
}

const TURNSTILE_SCRIPT_ID = 'cf-turnstile-script';
const TURNSTILE_SCRIPT_SRC = 'https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit';

function loadTurnstileScript(): Promise<void> {
  if (typeof window === 'undefined' || window.turnstile) {
    return Promise.resolve();
  }

  if (window.__turnstileLoader) {
    return window.__turnstileLoader;
  }

  window.__turnstileLoader = new Promise<void>((resolve, reject) => {
    const existing = document.getElementById(TURNSTILE_SCRIPT_ID) as HTMLScriptElement | null;

    if (existing) {
      const started = Date.now();
      const waitExisting = () => {
        if (window.turnstile) {
          resolve();
          return;
        }
        if (Date.now() - started > 10000) {
          reject(new Error('Turnstile script exists but API is not ready'));
          return;
        }
        setTimeout(waitExisting, 50);
      };
      waitExisting();
      return;
    }

    const script = document.createElement('script');
    script.id = TURNSTILE_SCRIPT_ID;
    script.src = TURNSTILE_SCRIPT_SRC;
    script.async = true;
    script.defer = true;
    script.addEventListener('load', () => resolve(), { once: true });
    script.addEventListener('error', () => reject(new Error('Failed to load Turnstile script')), { once: true });
    document.head.appendChild(script);
  });

  return window.__turnstileLoader.catch((err) => {
    window.__turnstileLoader = undefined;
    throw err;
  });
}

async function waitForTurnstile(timeoutMs: number): Promise<TurnstileApi> {
  const started = Date.now();
  while (!window.turnstile) {
    if (Date.now() - started >= timeoutMs) {
      throw new Error('Turnstile did not initialize in time');
    }
    await new Promise((resolve) => setTimeout(resolve, 50));
  }
  return window.turnstile;
}

type TurnstileCaptchaProps = {
  onTokenChange: (token: string | null) => void;
  resetNonce: number;
  onErrorChange?: (error: string | null) => void;
};

type TurnstileRenderOverrides = {
  size?: 'normal' | 'compact' | 'invisible' | 'flexible';
  appearance?: 'always' | 'execute' | 'interaction-only';
  theme?: 'auto' | 'light' | 'dark';
  execution?: 'render' | 'execute';
};

const RETRYABLE_CODES = new Set(['400020', '400030', '400040']);
const RENDER_PROFILES: TurnstileRenderOverrides[] = [
  {},
  { size: 'normal' },
  { size: 'compact' },
  { size: 'flexible' },
  { size: 'invisible', execution: 'execute', appearance: 'execute' },
  { size: 'invisible', execution: 'render', appearance: 'always' },
  { size: 'invisible', execution: 'render', appearance: 'interaction-only' },
  { size: 'invisible', execution: 'execute', appearance: 'always' },
];

function normalizeErrorCode(code: unknown): string {
  if (typeof code === 'number' || typeof code === 'string') {
    return String(code);
  }
  return '';
}

function getReadableTurnstileError(code: unknown): string {
  const normalized = normalizeErrorCode(code);
  if (!normalized) {
    return 'Не удалось загрузить CAPTCHA. Обновите страницу.';
  }
  if (normalized === '400020') {
    return 'Конфликт параметров размера CAPTCHA. Проверьте режим виджета Turnstile в Cloudflare.';
  }
  if (normalized === '400030') {
    return 'Конфликт режима отображения CAPTCHA. Проверьте настройки виджета Turnstile.';
  }
  if (normalized === '400040') {
    return 'Конфликт темы CAPTCHA. Проверьте настройки виджета Turnstile.';
  }
  if (normalized === '600010' || normalized === '110200') {
    return 'CAPTCHA недоступна для этого домена. Проверьте настройки ключей Turnstile.';
  }
  return `Ошибка CAPTCHA (${normalized}). Обновите страницу и попробуйте снова.`;
}

export default function TurnstileCaptcha({ onTokenChange, resetNonce, onErrorChange }: TurnstileCaptchaProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const activeRenderRef = useRef(0);
  const [renderError, setRenderError] = useState('');
  const [initializing, setInitializing] = useState(false);
  const siteKey = process.env.NEXT_PUBLIC_TURNSTILE_SITE_KEY;

  useEffect(() => {
    if (!siteKey) {
      onTokenChange(null);
      onErrorChange?.(null);
      return;
    }

    let cancelled = false;
    let widgetId: string | null = null;
    let turnstileApi: TurnstileApi | null = null;
    let activeOverrides: TurnstileRenderOverrides = RENDER_PROFILES[0];
    let profileIndex = 0;
    let retries = 0;
    const maxRetries = RENDER_PROFILES.length - 1;
    const reportError = (message: string) => {
      if (cancelled) return;
      setRenderError(message);
      onTokenChange(null);
      onErrorChange?.(message);
    };

    const resetContainer = () => {
      if (!containerRef.current) return;
      containerRef.current.innerHTML = '';
    };

    const clearWidget = () => {
      if (widgetId && window.turnstile) {
        window.turnstile.remove(widgetId);
        widgetId = null;
      }
    };

    const buildRenderOptions = (): Record<string, unknown> => ({
      sitekey: siteKey,
      ...activeOverrides,
      callback: (token: string) => {
        if (cancelled) return;
        setRenderError('');
        onErrorChange?.(null);
        onTokenChange(token);
      },
      'expired-callback': () => {
        if (cancelled) return;
        onTokenChange(null);
      },
      'timeout-callback': () => {
        if (cancelled) return;
        onTokenChange(null);
      },
      'error-callback': (code: unknown) => {
        if (cancelled) return;
        const normalizedCode = normalizeErrorCode(code);
        onTokenChange(null);
        if (tryRetryWithFallback(normalizedCode)) {
          return;
        }
        reportError(getReadableTurnstileError(normalizedCode));
      },
      'unsupported-callback': () => reportError('Ваш браузер не поддерживает CAPTCHA. Обновите браузер.'),
    });

    const renderWidget = () => {
      if (cancelled || !containerRef.current || !turnstileApi) return;
      try {
        const renderId = activeRenderRef.current + 1;
        activeRenderRef.current = renderId;
        clearWidget();
        resetContainer();
        const options = buildRenderOptions();
        const scopedOptions: Record<string, unknown> = {
          ...options,
          callback: (token: string) => {
            if (cancelled || activeRenderRef.current !== renderId) return;
            (options.callback as (t: string) => void)(token);
          },
          'expired-callback': () => {
            if (cancelled || activeRenderRef.current !== renderId) return;
            (options['expired-callback'] as () => void)();
          },
          'timeout-callback': () => {
            if (cancelled || activeRenderRef.current !== renderId) return;
            (options['timeout-callback'] as () => void)();
          },
          'error-callback': (code: unknown) => {
            if (cancelled || activeRenderRef.current !== renderId) return;
            (options['error-callback'] as (c: unknown) => void)(code);
          },
          'unsupported-callback': () => {
            if (cancelled || activeRenderRef.current !== renderId) return;
            (options['unsupported-callback'] as () => void)();
          },
        };
        widgetId = turnstileApi.render(containerRef.current, scopedOptions);
        if (widgetId && activeOverrides.execution === 'execute' && turnstileApi.execute) {
          setTimeout(() => {
            if (!cancelled && activeRenderRef.current === renderId && widgetId && turnstileApi?.execute) {
              turnstileApi.execute(widgetId);
            }
          }, 0);
        }
        setInitializing(false);
      } catch {
        setInitializing(false);
        reportError('Не удалось отрисовать CAPTCHA. Проверьте настройки Turnstile для этого домена.');
      }
    };

    const tryRetryWithFallback = (code: string): boolean => {
      if (!RETRYABLE_CODES.has(code) || retries >= maxRetries) {
        return false;
      }

      profileIndex += 1;
      const nextOverrides = RENDER_PROFILES[profileIndex];
      if (!nextOverrides) return false;

      retries += 1;
      activeOverrides = nextOverrides;
      setRenderError('');
      onErrorChange?.(null);
      setTimeout(() => {
        if (!cancelled) {
          renderWidget();
        }
      }, 0);
      return true;
    };

    async function mount() {
      setInitializing(true);
      setRenderError('');
      onTokenChange(null);
      onErrorChange?.(null);
      try {
        await loadTurnstileScript();
        turnstileApi = await waitForTurnstile(10000);
        if (cancelled || !containerRef.current) return;
        renderWidget();
      } catch {
        setInitializing(false);
        reportError('Не удалось загрузить CAPTCHA. Обновите страницу.');
      }
    }

    void mount();

    return () => {
      cancelled = true;
      activeRenderRef.current += 1;
      setInitializing(false);
      onTokenChange(null);
      onErrorChange?.(null);
      clearWidget();
    };
  }, [onErrorChange, onTokenChange, resetNonce, siteKey]);

  if (!siteKey) {
    return null;
  }

  return (
    <div className="stack" style={{ gap: 6 }}>
      <div ref={containerRef} style={{ minHeight: 65 }} />
      {initializing && !renderError && <p className="muted" style={{ margin: 0, fontSize: '.85rem' }}>Загружаем CAPTCHA...</p>}
      {renderError && <p className="error" style={{ margin: 0 }}>{renderError}</p>}
    </div>
  );
}

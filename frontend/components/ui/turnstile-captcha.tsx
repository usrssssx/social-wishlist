'use client';

import { useEffect, useRef, useState } from 'react';

type TurnstileApi = {
  render: (container: HTMLElement, options: Record<string, unknown>) => string;
  remove: (widgetId: string) => void;
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

function getReadableTurnstileError(code: unknown): string {
  const normalized = typeof code === 'number' || typeof code === 'string' ? String(code) : '';
  if (!normalized) {
    return 'Не удалось загрузить CAPTCHA. Обновите страницу.';
  }
  if (normalized === '400020') {
    return 'CAPTCHA настроена с неверным размером. Обновите страницу или свяжитесь с поддержкой.';
  }
  if (normalized === '400030') {
    return 'CAPTCHA настроена с неверным режимом отображения. Обновите страницу или свяжитесь с поддержкой.';
  }
  if (normalized === '400040') {
    return 'CAPTCHA настроена с неверной темой. Обновите страницу или свяжитесь с поддержкой.';
  }
  if (normalized === '600010' || normalized === '110200') {
    return 'CAPTCHA недоступна для этого домена. Проверьте настройки ключей Turnstile.';
  }
  return `Ошибка CAPTCHA (${normalized}). Обновите страницу и попробуйте снова.`;
}

export default function TurnstileCaptcha({ onTokenChange, resetNonce, onErrorChange }: TurnstileCaptchaProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
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
    const reportError = (message: string) => {
      if (cancelled) return;
      setRenderError(message);
      onTokenChange(null);
      onErrorChange?.(message);
    };

    async function mount() {
      setInitializing(true);
      setRenderError('');
      onTokenChange(null);
      onErrorChange?.(null);
      try {
        await loadTurnstileScript();
        const turnstile = await waitForTurnstile(10000);
        if (cancelled || !containerRef.current) return;

        containerRef.current.innerHTML = '';
        widgetId = turnstile.render(containerRef.current, {
          sitekey: siteKey,
          callback: (token: string) => {
            setRenderError('');
            onErrorChange?.(null);
            onTokenChange(token);
          },
          'expired-callback': () => onTokenChange(null),
          'timeout-callback': () => onTokenChange(null),
          'error-callback': (code: unknown) => reportError(getReadableTurnstileError(code)),
          'unsupported-callback': () => reportError('Ваш браузер не поддерживает CAPTCHA. Обновите браузер.'),
        });
        setInitializing(false);
      } catch {
        setInitializing(false);
        reportError('Не удалось загрузить CAPTCHA. Обновите страницу.');
      }
    }

    void mount();

    return () => {
      cancelled = true;
      setInitializing(false);
      onTokenChange(null);
      onErrorChange?.(null);
      if (widgetId && window.turnstile) {
        window.turnstile.remove(widgetId);
      }
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

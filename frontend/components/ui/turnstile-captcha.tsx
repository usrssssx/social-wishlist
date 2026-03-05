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
      resolve();
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

  return window.__turnstileLoader;
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
};

export default function TurnstileCaptcha({ onTokenChange, resetNonce }: TurnstileCaptchaProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const [renderError, setRenderError] = useState('');
  const siteKey = process.env.NEXT_PUBLIC_TURNSTILE_SITE_KEY;

  useEffect(() => {
    if (!siteKey) {
      onTokenChange(null);
      return;
    }

    let cancelled = false;
    let widgetId: string | null = null;

    async function mount() {
      setRenderError('');
      onTokenChange(null);
      try {
        await loadTurnstileScript();
        const turnstile = await waitForTurnstile(10000);
        if (cancelled || !containerRef.current) return;

        containerRef.current.innerHTML = '';
        widgetId = turnstile.render(containerRef.current, {
          sitekey: siteKey,
          callback: (token: string) => onTokenChange(token),
          'expired-callback': () => onTokenChange(null),
          'error-callback': () => onTokenChange(null),
          theme: 'light',
        });
      } catch {
        if (!cancelled) {
          setRenderError('Не удалось загрузить CAPTCHA. Обновите страницу.');
        }
      }
    }

    void mount();

    return () => {
      cancelled = true;
      onTokenChange(null);
      if (widgetId && window.turnstile) {
        window.turnstile.remove(widgetId);
      }
    };
  }, [onTokenChange, resetNonce, siteKey]);

  if (!siteKey) {
    return null;
  }

  return (
    <div className="stack" style={{ gap: 6 }}>
      <div ref={containerRef} />
      {renderError && <p className="error" style={{ margin: 0 }}>{renderError}</p>}
    </div>
  );
}

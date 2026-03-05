'use client';

import Link from 'next/link';
import { FormEvent, useEffect, useMemo, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';

import TurnstileCaptcha from '@/components/ui/turnstile-captcha';
import { api, getReadableError } from '@/lib/api';
import { getAuthToken, setAuthToken } from '@/lib/utils';

type Mode = 'login' | 'register';

export default function AuthPage() {
  const router = useRouter();
  const searchParams = useSearchParams();

  const [mode, setMode] = useState<Mode>('login');
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [resetPassword, setResetPassword] = useState('');
  const [error, setError] = useState('');
  const [info, setInfo] = useState('');
  const [loading, setLoading] = useState(false);
  const [resetRequested, setResetRequested] = useState(false);
  const [captchaToken, setCaptchaToken] = useState<string | null>(null);
  const [captchaNonce, setCaptchaNonce] = useState(0);

  const verifyToken = searchParams.get('verify_token');
  const resetToken = searchParams.get('reset_token');
  const captchaEnabled = Boolean(process.env.NEXT_PUBLIC_TURNSTILE_SITE_KEY);

  useEffect(() => {
    if (getAuthToken()) router.replace('/dashboard');
  }, [router]);

  useEffect(() => {
    let cancelled = false;

    async function handleEmailActions() {
      if (verifyToken) {
        setLoading(true);
        setError('');
        try {
          const result = await api.verifyEmail(verifyToken);
          if (!cancelled) {
            setInfo(result.detail);
            router.replace('/auth');
          }
        } catch (err) {
          if (!cancelled) {
            setError(getReadableError(err, 'Не удалось подтвердить email'));
            router.replace('/auth');
          }
        } finally {
          if (!cancelled) setLoading(false);
        }
      }
    }

    void handleEmailActions();

    return () => {
      cancelled = true;
    };
  }, [verifyToken, router]);

  const title = useMemo(() => {
    if (resetToken) return 'Сброс пароля';
    return mode === 'login' ? 'С возвращением' : 'Создать аккаунт';
  }, [mode, resetToken]);

  const subtitle = useMemo(() => {
    if (resetToken) return 'Введите новый пароль для входа';
    return mode === 'login'
      ? 'Войдите, чтобы управлять своими вишлистами'
      : 'После регистрации подтвердите email из письма';
  }, [mode, resetToken]);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError('');
    setInfo('');
    setLoading(true);

    let captchaForRequest: string | null = null;
    let shouldResetCaptcha = false;

    try {
      if (resetToken) {
        const result = await api.confirmPasswordReset(resetToken, resetPassword);
        setInfo(result.detail);
        setResetPassword('');
        router.replace('/auth');
        return;
      }

      if (captchaEnabled) {
        if (!captchaToken) {
          setError('Подтвердите CAPTCHA');
          return;
        }
        captchaForRequest = captchaToken;
        shouldResetCaptcha = true;
      }

      if (mode === 'login') {
        const res = await api.login(email.trim(), password, captchaForRequest);
        setAuthToken(res.access_token);
        router.push('/dashboard');
        return;
      }

      const registerResult = await api.register(email.trim(), password, name.trim(), captchaForRequest);
      setInfo(registerResult.detail);
      setMode('login');
      setPassword('');
    } catch (err) {
      setError(getReadableError(err, 'Ошибка авторизации'));
    } finally {
      if (shouldResetCaptcha) {
        setCaptchaToken(null);
        setCaptchaNonce((prev) => prev + 1);
      }
      setLoading(false);
    }
  }

  async function onResendVerification() {
    if (!email.trim()) {
      setError('Введите email для повторной отправки подтверждения');
      return;
    }
    setError('');
    setInfo('');
    setLoading(true);
    let shouldResetCaptcha = false;
    try {
      if (captchaEnabled) {
        if (!captchaToken) {
          setError('Подтвердите CAPTCHA');
          return;
        }
        shouldResetCaptcha = true;
      }
      const result = await api.resendVerification(email.trim(), captchaToken);
      setInfo(result.detail);
    } catch (err) {
      setError(getReadableError(err, 'Не удалось отправить письмо'));
    } finally {
      if (shouldResetCaptcha) {
        setCaptchaToken(null);
        setCaptchaNonce((prev) => prev + 1);
      }
      setLoading(false);
    }
  }

  async function onRequestReset() {
    if (!email.trim()) {
      setError('Введите email для сброса пароля');
      return;
    }
    setError('');
    setInfo('');
    setLoading(true);
    let shouldResetCaptcha = false;
    try {
      if (captchaEnabled) {
        if (!captchaToken) {
          setError('Подтвердите CAPTCHA');
          return;
        }
        shouldResetCaptcha = true;
      }
      const result = await api.requestPasswordReset(email.trim(), captchaToken);
      setInfo(result.detail);
      setResetRequested(true);
    } catch (err) {
      setError(getReadableError(err, 'Не удалось отправить письмо для сброса'));
    } finally {
      if (shouldResetCaptcha) {
        setCaptchaToken(null);
        setCaptchaNonce((prev) => prev + 1);
      }
      setLoading(false);
    }
  }

  return (
    <main className="page" style={{ display: 'flex', justifyContent: 'center', paddingTop: 48 }}>
      <div style={{ width: '100%', maxWidth: 460 }} className="animate-fade-up">
        <div style={{ textAlign: 'center', marginBottom: 32 }}>
          <h1 style={{ fontSize: '2.2rem', marginBottom: 8 }}>{title}</h1>
          <p className="muted">{subtitle}</p>
        </div>

        <div className="card" style={{ padding: '32px 36px' }}>
          <form className="stack" onSubmit={onSubmit}>
            {!resetToken && mode === 'register' && (
              <div className="form-group">
                <label className="label" htmlFor="name">Имя</label>
                <input
                  id="name"
                  className="input"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="Как вас зовут?"
                  required
                  minLength={2}
                />
              </div>
            )}

            <div className="form-group">
              <label className="label" htmlFor="email">Email</label>
              <input
                id="email"
                className="input"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@example.com"
                required={!resetToken}
              />
            </div>

            {!resetToken && (
              <div className="form-group">
                <label className="label" htmlFor="password">Пароль</label>
                <input
                  id="password"
                  className="input"
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Минимум 8 символов"
                  required
                  minLength={8}
                />
              </div>
            )}

            {resetToken && (
              <div className="form-group">
                <label className="label" htmlFor="resetPassword">Новый пароль</label>
                <input
                  id="resetPassword"
                  className="input"
                  type="password"
                  value={resetPassword}
                  onChange={(e) => setResetPassword(e.target.value)}
                  placeholder="Минимум 8 символов"
                  required
                  minLength={8}
                />
              </div>
            )}

            {error && <p className="error">{error}</p>}
            {info && <p className="success">{info}</p>}
            {!resetToken && (
              <TurnstileCaptcha onTokenChange={setCaptchaToken} resetNonce={captchaNonce} />
            )}

            <button className="btn btn-primary btn-lg" type="submit" disabled={loading} style={{ width: '100%', marginTop: 4 }}>
              {loading
                ? 'Подождите...'
                : resetToken
                  ? 'Сохранить новый пароль'
                  : mode === 'login'
                    ? 'Войти'
                    : 'Зарегистрироваться'}
            </button>
          </form>

          {!resetToken && mode === 'login' && (
            <div className="row" style={{ marginTop: 12 }}>
              <button className="btn btn-ghost btn-sm" type="button" onClick={onRequestReset} disabled={loading}>
                {resetRequested ? 'Письмо отправлено' : 'Забыли пароль?'}
              </button>
              <button className="btn btn-ghost btn-sm" type="button" onClick={onResendVerification} disabled={loading}>
                Повторно отправить подтверждение
              </button>
            </div>
          )}

          {!resetToken && (
            <>
              <div className="divider" />
              <p style={{ textAlign: 'center', fontSize: '.9rem', color: 'var(--muted)' }}>
                {mode === 'login' ? 'Нет аккаунта?' : 'Уже есть аккаунт?'}{' '}
                <button
                  className="btn btn-ghost btn-sm"
                  type="button"
                  onClick={() => setMode(mode === 'login' ? 'register' : 'login')}
                  style={{ display: 'inline-flex', marginLeft: 4 }}
                >
                  {mode === 'login' ? 'Создать' : 'Войти'}
                </button>
              </p>
            </>
          )}
        </div>
        <div className="row" style={{ justifyContent: 'center', marginTop: 14 }}>
          <Link className="btn btn-ghost btn-sm" href="/terms">Условия</Link>
          <Link className="btn btn-ghost btn-sm" href="/privacy">Конфиденциальность</Link>
        </div>
      </div>
    </main>
  );
}

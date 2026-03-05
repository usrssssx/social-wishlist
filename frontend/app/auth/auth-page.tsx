'use client';

import { FormEvent, useEffect, useMemo, useState } from 'react';
import { useRouter } from 'next/navigation';

import { api } from '@/lib/api';
import { getAuthToken, setAuthToken } from '@/lib/utils';

type Mode = 'login' | 'register';

export default function AuthPage() {
  const router = useRouter();
  const [mode, setMode] = useState<Mode>('login');
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (getAuthToken()) router.replace('/dashboard');
  }, [router]);

  const title = useMemo(() => (mode === 'login' ? 'С возвращением' : 'Создать аккаунт'), [mode]);
  const subtitle = useMemo(
    () =>
      mode === 'login'
        ? 'Войдите, чтобы управлять своими вишлистами'
        : 'Начните делиться желаниями прямо сейчас',
    [mode]
  );

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      const res =
        mode === 'login'
          ? await api.login(email.trim(), password)
          : await api.register(email.trim(), password, name.trim());
      setAuthToken(res.access_token);
      router.push('/dashboard');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Ошибка авторизации');
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="page" style={{ display: 'flex', justifyContent: 'center', paddingTop: 48 }}>
      <div style={{ width: '100%', maxWidth: 460 }} className="animate-fade-up">
        {/* Header */}
        <div style={{ textAlign: 'center', marginBottom: 32 }}>
          <h1 style={{ fontSize: '2.2rem', marginBottom: 8 }}>{title}</h1>
          <p className="muted">{subtitle}</p>
        </div>

        <div className="card" style={{ padding: '32px 36px' }}>
          <form className="stack" onSubmit={onSubmit}>
            {mode === 'register' && (
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
                required
              />
            </div>

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

            {error && <p className="error">{error}</p>}

            <button className="btn btn-primary btn-lg" type="submit" disabled={loading} style={{ width: '100%', marginTop: 4 }}>
              {loading ? 'Подождите...' : mode === 'login' ? 'Войти' : 'Зарегистрироваться'}
            </button>
          </form>

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
        </div>
      </div>
    </main>
  );
}

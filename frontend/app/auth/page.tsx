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
    if (getAuthToken()) {
      router.replace('/dashboard');
    }
  }, [router]);

  const title = useMemo(
    () => (mode === 'login' ? 'Вход в аккаунт' : 'Создание аккаунта'),
    [mode]
  );

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setError('');
    setLoading(true);

    try {
      const response =
        mode === 'login'
          ? await api.login(email.trim(), password)
          : await api.register(email.trim(), password, name.trim());
      setAuthToken(response.access_token);
      router.push('/dashboard');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Ошибка авторизации');
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="page">
      <section className="hero">
        <h1>{title}</h1>
        <p>Минимум нужен email и пароль. OAuth можно добавить следующим шагом.</p>
      </section>

      <section className="card" style={{ marginTop: 16, maxWidth: 520 }}>
        <form className="grid" onSubmit={onSubmit}>
          {mode === 'register' && (
            <div>
              <label className="label" htmlFor="name">
                Имя
              </label>
              <input
                className="input"
                id="name"
                value={name}
                onChange={(event) => setName(event.target.value)}
                required
                minLength={2}
              />
            </div>
          )}

          <div>
            <label className="label" htmlFor="email">
              Email
            </label>
            <input
              className="input"
              id="email"
              type="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              required
            />
          </div>

          <div>
            <label className="label" htmlFor="password">
              Пароль
            </label>
            <input
              className="input"
              id="password"
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              required
              minLength={8}
            />
          </div>

          {error && <p className="error">{error}</p>}

          <div className="row">
            <button className="btn btn-primary" disabled={loading} type="submit">
              {loading ? 'Подождите...' : mode === 'login' ? 'Войти' : 'Зарегистрироваться'}
            </button>
            <button
              className="btn btn-ghost"
              type="button"
              onClick={() => setMode(mode === 'login' ? 'register' : 'login')}
            >
              {mode === 'login' ? 'Нужен аккаунт' : 'Уже есть аккаунт'}
            </button>
          </div>
        </form>
      </section>
    </main>
  );
}

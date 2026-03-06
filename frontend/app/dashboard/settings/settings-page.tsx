'use client';

import Link from 'next/link';
import { FormEvent, useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';

import { api, getReadableError } from '@/lib/api';
import { clearAuthToken, getAuthToken } from '@/lib/utils';

export default function DashboardSettingsPage() {
  const router = useRouter();
  const [token, setToken] = useState<string | null>(null);
  const [deletePassword, setDeletePassword] = useState('');
  const [deletePhrase, setDeletePhrase] = useState('');
  const [deleteLoading, setDeleteLoading] = useState(false);
  const [deleteError, setDeleteError] = useState('');

  useEffect(() => {
    const authToken = getAuthToken();
    if (!authToken) {
      router.replace('/auth');
      return;
    }
    setToken(authToken);
  }, [router]);

  async function onDeleteAccount(e: FormEvent) {
    e.preventDefault();
    if (!token) return;
    setDeleteError('');
    setDeleteLoading(true);
    try {
      await api.deleteAccount(token, deletePassword, deletePhrase.trim());
      clearAuthToken();
      router.push('/');
    } catch (err) {
      setDeleteError(getReadableError(err, 'Не удалось удалить аккаунт'));
    } finally {
      setDeleteLoading(false);
    }
  }

  return (
    <main className="page">
      <div className="page-header animate-fade-up">
        <div>
          <Link href="/dashboard" className="btn btn-ghost btn-sm" style={{ marginBottom: 10, display: 'inline-flex' }}>
            ← Назад к вишлистам
          </Link>
          <h1 className="section-title">Настройки аккаунта</h1>
          <p className="muted" style={{ marginTop: 4 }}>
            Управляйте сессией и критичными действиями аккаунта.
          </p>
        </div>
      </div>

      <section className="card animate-fade-up" style={{ marginBottom: 20, animationDelay: '.05s' }}>
        <h3 style={{ marginBottom: 8 }}>Сессия</h3>
        <p className="muted" style={{ marginBottom: 14 }}>
          Выйдите из текущего аккаунта на этом устройстве.
        </p>
        <button className="btn btn-ghost btn-sm" type="button" onClick={() => { clearAuthToken(); router.push('/auth'); }}>
          Выйти из аккаунта
        </button>
      </section>

      <section className="card animate-fade-up" style={{ borderColor: 'rgba(212,70,58,.22)', animationDelay: '.1s' }}>
        <h3 style={{ marginBottom: 8 }}>Удаление аккаунта</h3>
        <p className="muted" style={{ marginBottom: 14 }}>
          Удаление аккаунта навсегда удалит ваши вишлисты и связанные персональные данные без возможности восстановления.
        </p>
        <form className="stack" onSubmit={onDeleteAccount}>
          <div className="grid grid-2" style={{ gap: 12 }}>
            <div className="form-group">
              <label className="label" htmlFor="deletePassword">Пароль</label>
              <input
                id="deletePassword"
                className="input"
                type="password"
                minLength={8}
                required
                value={deletePassword}
                onChange={(e) => setDeletePassword(e.target.value)}
                placeholder="Введите пароль"
              />
            </div>
            <div className="form-group">
              <label className="label" htmlFor="deletePhrase">Подтверждение</label>
              <input
                id="deletePhrase"
                className="input"
                type="text"
                required
                value={deletePhrase}
                onChange={(e) => setDeletePhrase(e.target.value)}
                placeholder="Введите DELETE (латиницей)"
              />
            </div>
          </div>
          {deleteError && <p className="error">{deleteError}</p>}
          <div className="row">
            <button className="btn btn-danger" type="submit" disabled={deleteLoading}>
              {deleteLoading ? 'Удаляем...' : 'Удалить аккаунт навсегда'}
            </button>
          </div>
        </form>
      </section>
    </main>
  );
}

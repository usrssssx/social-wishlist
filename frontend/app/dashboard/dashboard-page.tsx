'use client';

import Link from 'next/link';
import { FormEvent, useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';

import { api, getReadableError } from '@/lib/api';
import type { WishlistSummary } from '@/lib/types';
import { clearAuthToken, formatMoney, getAuthToken } from '@/lib/utils';

export default function DashboardPage() {
  const router = useRouter();
  const [token, setToken] = useState<string | null>(null);
  const [wishlists, setWishlists] = useState<WishlistSummary[]>([]);
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [eventDate, setEventDate] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [deletePassword, setDeletePassword] = useState('');
  const [deletePhrase, setDeletePhrase] = useState('');
  const [deleteLoading, setDeleteLoading] = useState(false);
  const [deleteError, setDeleteError] = useState('');

  async function loadData(authToken: string) {
    setLoading(true);
    setError('');
    try {
      const data = await api.listWishlists(authToken);
      setWishlists(data);
    } catch (err) {
      setError(getReadableError(err, 'Не удалось загрузить список'));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    const authToken = getAuthToken();
    if (!authToken) { router.replace('/auth'); return; }
    setToken(authToken);
    void loadData(authToken);
  }, [router]);

  async function onCreate(e: FormEvent) {
    e.preventDefault();
    if (!token) return;
    setError('');
    try {
      await api.createWishlist(token, { title: title.trim(), description: description.trim(), event_date: eventDate || null });
      setTitle(''); setDescription(''); setEventDate('');
      setShowForm(false);
      await loadData(token);
    } catch (err) {
      setError(getReadableError(err, 'Не удалось создать wishlist'));
    }
  }

  function copyPublicLink(shareToken: string) {
    const url = `${window.location.origin}/w/${shareToken}`;
    void navigator.clipboard.writeText(url);
  }

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
      {/* Page header */}
      <div className="page-header animate-fade-up">
        <div>
          <h1 className="section-title">Мои вишлисты</h1>
          <p className="muted" style={{ marginTop: 4 }}>Управляйте подарками и делитесь ссылками</p>
        </div>
        <div className="row">
          <button
            className="btn btn-primary"
            type="button"
            onClick={() => setShowForm(!showForm)}
          >
            {showForm ? '✕ Закрыть' : '+ Новый список'}
          </button>
          <button
            className="btn btn-ghost btn-sm"
            type="button"
            onClick={() => { clearAuthToken(); router.push('/auth'); }}
          >
            Выйти
          </button>
        </div>
      </div>

      {/* Create form */}
      {showForm && (
        <section className="card animate-fade-up" style={{ marginBottom: 28 }}>
          <h3 style={{ marginBottom: 20 }}>Создать новый список</h3>
          <form className="stack" onSubmit={onCreate}>
            <div className="grid grid-2" style={{ gap: 14 }}>
              <div className="form-group">
                <label className="label" htmlFor="title">Название *</label>
                <input id="title" className="input" value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  placeholder="День рождения 2026" required />
              </div>
              <div className="form-group">
                <label className="label" htmlFor="eventDate">Дата события</label>
                <input id="eventDate" className="input" type="date" value={eventDate}
                  onChange={(e) => setEventDate(e.target.value)} />
              </div>
            </div>
            <div className="form-group">
              <label className="label" htmlFor="description">Описание</label>
              <textarea id="description" className="textarea" value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Предпочтения, размеры, пожелания..." />
            </div>
            {error && <p className="error">{error}</p>}
            <div className="row">
              <button className="btn btn-primary" type="submit">Создать список</button>
              <button className="btn btn-ghost" type="button" onClick={() => setShowForm(false)}>Отмена</button>
            </div>
          </form>
        </section>
      )}

      {/* Content */}
      {loading ? (
        <div className="empty-state">
          <div className="icon">⏳</div>
          <p className="muted">Загружаем ваши вишлисты...</p>
        </div>
      ) : wishlists.length === 0 ? (
        <div className="card empty-state animate-fade-in">
          <div className="icon">🎁</div>
          <h3>Пока пусто</h3>
          <p>Создайте первый вишлист и поделитесь им с друзьями. Начните с 3–5 подарков разного бюджета.</p>
          <button className="btn btn-primary" style={{ marginTop: 20 }} onClick={() => setShowForm(true)}>
            Создать первый список
          </button>
        </div>
      ) : (
        <section className="grid grid-2 animate-fade-up" style={{ animationDelay: '.05s' }}>
          {wishlists.map((wl) => (
            <article key={wl.id} className="wishlist-card">
              <div className="wishlist-card-head">
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 8 }}>
                  <h3 style={{ fontSize: '1.15rem' }}>{wl.title}</h3>
                  {wl.event_date && (
                    <span className="tag tag-gold" style={{ flexShrink: 0 }}>
                      📅 {new Date(wl.event_date).toLocaleDateString('ru-RU', { day: 'numeric', month: 'short' })}
                    </span>
                  )}
                </div>
                <p className="muted" style={{ fontSize: '.9rem', marginTop: 6, lineHeight: 1.5 }}>
                  {wl.description || 'Без описания'}
                </p>
              </div>
              <div className="wishlist-card-body">
                <div className="stat-row">
                  <div className="stat-item">
                    <span className="value">{wl.item_count}</span>
                    <span className="label">подарков</span>
                  </div>
                  <div className="stat-item">
                    <span className="value">{wl.reserved_count}</span>
                    <span className="label">забронировано</span>
                  </div>
                  <div className="stat-item">
                    <span className="value" style={{ fontSize: '1.1rem' }}>{formatMoney(wl.funded_amount)}</span>
                    <span className="label">собрано</span>
                  </div>
                </div>
              </div>
              <div className="wishlist-card-foot">
                <Link className="btn btn-primary btn-sm" href={`/dashboard/w/${wl.id}`}>
                  Открыть →
                </Link>
                <button
                  className="btn btn-ghost btn-sm"
                  onClick={() => copyPublicLink(wl.share_token)}
                  type="button"
                >
                  📋 Копировать ссылку
                </button>
              </div>
            </article>
          ))}
        </section>
      )}

      <section className="card animate-fade-up" style={{ marginTop: 26, borderColor: 'rgba(212,70,58,.22)' }}>
        <h3 style={{ marginBottom: 8 }}>Опасная зона</h3>
        <p className="muted" style={{ marginBottom: 14 }}>
          Удаление аккаунта удалит ваши вишлисты и связанные персональные данные без возможности восстановления.
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
              <label className="label" htmlFor="deletePhrase">Фраза подтверждения</label>
              <input
                id="deletePhrase"
                className="input"
                type="text"
                required
                value={deletePhrase}
                onChange={(e) => setDeletePhrase(e.target.value)}
                placeholder="Введите DELETE"
              />
            </div>
          </div>
          {deleteError && <p className="error">{deleteError}</p>}
          <div className="row">
            <button className="btn btn-danger" type="submit" disabled={deleteLoading}>
              {deleteLoading ? 'Удаляем...' : 'Удалить аккаунт и данные'}
            </button>
          </div>
        </form>
      </section>
    </main>
  );
}

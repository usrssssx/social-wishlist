'use client';

import Link from 'next/link';
import { FormEvent, useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';

import { api } from '@/lib/api';
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

  async function loadData(authToken: string) {
    setLoading(true);
    setError('');
    try {
      const data = await api.listWishlists(authToken);
      setWishlists(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Не удалось загрузить список');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    const authToken = getAuthToken();
    if (!authToken) {
      router.replace('/auth');
      return;
    }
    setToken(authToken);
    void loadData(authToken);
  }, [router]);

  async function onCreate(event: FormEvent) {
    event.preventDefault();
    if (!token) return;

    setError('');
    try {
      await api.createWishlist(token, {
        title: title.trim(),
        description: description.trim(),
        event_date: eventDate || null
      });
      setTitle('');
      setDescription('');
      setEventDate('');
      await loadData(token);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Не удалось создать wishlist');
    }
  }

  function copyPublicLink(shareToken: string) {
    const url = `${window.location.origin}/w/${shareToken}`;
    void navigator.clipboard.writeText(url);
  }

  return (
    <main className="page">
      <div className="header">
        <section>
          <h1 className="section-title">Мои вишлисты</h1>
          <p className="muted">Управляйте товарами и делитесь публичной ссылкой.</p>
        </section>

        <button
          className="btn btn-ghost"
          onClick={() => {
            clearAuthToken();
            router.push('/auth');
          }}
          type="button"
        >
          Выйти
        </button>
      </div>

      <section className="card" style={{ marginBottom: 16 }}>
        <h3 style={{ marginTop: 0 }}>Создать новый список</h3>
        <form className="grid" onSubmit={onCreate}>
          <div>
            <label className="label" htmlFor="title">
              Название
            </label>
            <input
              id="title"
              className="input"
              value={title}
              onChange={(event) => setTitle(event.target.value)}
              placeholder="День рождения 2026"
              required
            />
          </div>

          <div>
            <label className="label" htmlFor="description">
              Описание
            </label>
            <textarea
              id="description"
              className="textarea"
              value={description}
              onChange={(event) => setDescription(event.target.value)}
              placeholder="Предпочтения, размеры, цвета"
            />
          </div>

          <div>
            <label className="label" htmlFor="eventDate">
              Дата события (опционально)
            </label>
            <input
              id="eventDate"
              className="input"
              type="date"
              value={eventDate}
              onChange={(event) => setEventDate(event.target.value)}
            />
          </div>

          {error && <p className="error">{error}</p>}

          <button className="btn btn-primary" type="submit">
            Создать wishlist
          </button>
        </form>
      </section>

      {loading ? (
        <p className="muted">Загрузка...</p>
      ) : wishlists.length === 0 ? (
        <section className="card">
          <h3 style={{ marginTop: 0 }}>Пока пусто</h3>
          <p className="muted">
            Первый wishlist лучше начать с 3-5 конкретных подарков: так друзьям проще выбрать и зарезервировать.
          </p>
        </section>
      ) : (
        <section className="grid grid-2">
          {wishlists.map((wishlist) => (
            <article key={wishlist.id} className="card">
              <h3>{wishlist.title}</h3>
              <p className="muted">{wishlist.description || 'Без описания'}</p>
              <p className="stat">
                Подарков: {wishlist.item_count} · Забронировано/собрано: {wishlist.reserved_count} · Всего обещано:{' '}
                {formatMoney(wishlist.funded_amount)}
              </p>
              <div className="row">
                <Link className="btn btn-primary" href={`/dashboard/w/${wishlist.id}`}>
                  Открыть
                </Link>
                <button className="btn btn-ghost" onClick={() => copyPublicLink(wishlist.share_token)} type="button">
                  Копировать ссылку
                </button>
              </div>
            </article>
          ))}
        </section>
      )}
    </main>
  );
}

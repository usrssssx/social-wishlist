'use client';

import Image from 'next/image';
import { FormEvent, useEffect, useMemo, useState } from 'react';
import { useParams } from 'next/navigation';

import { api, getWsUrl } from '@/lib/api';
import type { PublicItem, WishlistPublicDetail } from '@/lib/types';
import { formatMoney, getViewerToken, setViewerToken } from '@/lib/utils';

export default function PublicWishlistPage() {
  const params = useParams<{ shareToken: string }>();
  const shareToken = params.shareToken;

  const [wishlist, setWishlist] = useState<WishlistPublicDetail | null>(null);
  const [viewerToken, setViewerTokenState] = useState<string | null>(null);
  const [viewerName, setViewerName] = useState('');
  const [pendingAmounts, setPendingAmounts] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [flash, setFlash] = useState('');

  async function load(token: string | null) {
    setLoading(true);
    setError('');
    try {
      const data = await api.getPublicWishlist(shareToken, token);
      setWishlist(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Не удалось загрузить wishlist');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    const storedViewerToken = getViewerToken(shareToken);
    setViewerTokenState(storedViewerToken);
    void load(storedViewerToken);
  }, [shareToken]);

  useEffect(() => {
    const socket = new WebSocket(getWsUrl(shareToken));
    socket.onmessage = () => {
      void load(getViewerToken(shareToken));
    };
    return () => socket.close();
  }, [shareToken]);

  const stats = useMemo(() => {
    if (!wishlist) {
      return { total: 0, reserved: 0 };
    }
    return {
      total: wishlist.items.length,
      reserved: wishlist.items.filter((item) => item.reserved).length
    };
  }, [wishlist]);

  async function createSession(event: FormEvent) {
    event.preventDefault();
    setError('');
    try {
      const session = await api.createViewerSession(shareToken, viewerName.trim());
      setViewerToken(shareToken, session.session_token);
      setViewerTokenState(session.session_token);
      setViewerName('');
      await load(session.session_token);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Не удалось создать сессию');
    }
  }

  async function reserve(item: PublicItem) {
    if (!viewerToken) {
      setFlash('Чтобы забронировать подарок, введите имя ниже.');
      return;
    }
    setError('');
    try {
      if (item.reserved_by_me) {
        await api.unreserveItem(shareToken, item.id, viewerToken);
      } else {
        await api.reserveItem(shareToken, item.id, viewerToken);
      }
      await load(viewerToken);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Не удалось обновить бронь');
    }
  }

  async function contribute(item: PublicItem) {
    if (!viewerToken) {
      setFlash('Чтобы внести вклад, введите имя ниже.');
      return;
    }

    const amountRaw = pendingAmounts[item.id];
    const amount = Number(amountRaw);
    if (!amount || Number.isNaN(amount)) {
      setError('Введите сумму вклада');
      return;
    }

    setError('');
    try {
      await api.contribute(shareToken, item.id, amount, viewerToken);
      setPendingAmounts((previous) => ({ ...previous, [item.id]: '' }));
      await load(viewerToken);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Не удалось внести вклад');
    }
  }

  if (loading) {
    return (
      <main className="page">
        <p className="muted">Загрузка...</p>
      </main>
    );
  }

  if (!wishlist) {
    return (
      <main className="page">
        <p className="error">{error || 'Список не найден'}</p>
      </main>
    );
  }

  return (
    <main className="page">
      <section className="hero">
        <h1>{wishlist.title}</h1>
        <p>{wishlist.description || 'Публичный вишлист без обязательной регистрации.'}</p>
        <p className="stat">
          Закрыто подарков: {stats.reserved}/{stats.total}
        </p>
      </section>

      {!viewerToken && (
        <section className="card" style={{ marginTop: 16 }}>
          <h3 style={{ marginTop: 0 }}>Участвовать в брони и сборе</h3>
          <p className="muted">Нужна только подпись. Владелец списка не увидит, кто именно забронировал подарок.</p>
          <form className="row" onSubmit={createSession}>
            <input
              className="input"
              value={viewerName}
              onChange={(event) => setViewerName(event.target.value)}
              placeholder="Ваше имя"
              required
            />
            <button className="btn btn-primary" type="submit">
              Войти как гость
            </button>
          </form>
        </section>
      )}

      {(error || flash) && (
        <section className="card" style={{ marginTop: 16 }}>
          {error && <p className="error">{error}</p>}
          {flash && <p className="muted">{flash}</p>}
        </section>
      )}

      {wishlist.items.length === 0 ? (
        <section className="card" style={{ marginTop: 16 }}>
          <h3 style={{ marginTop: 0 }}>Пока пусто</h3>
          <p className="muted">Владелец ещё не добавил подарки.</p>
        </section>
      ) : (
        <section className="grid grid-2" style={{ marginTop: 16 }}>
          {wishlist.items.map((item) => (
            <article key={item.id} className="card">
              {item.image_url && (
                <Image
                  src={item.image_url}
                  alt={item.title}
                  width={600}
                  height={360}
                  className="item-image"
                  unoptimized
                />
              )}
              <h3>{item.title}</h3>
              <p className="stat">Цена: {formatMoney(item.price)}</p>

              <div className="row" style={{ marginBottom: 8 }}>
                {item.status === 'archived' && <span className="tag">Архив</span>}
                {item.reserved && <span className="tag">Зарезервировано / закрыто</span>}
                {item.allow_contributions && <span className="tag">Можно скинуться</span>}
              </div>

              {item.allow_contributions && (
                <>
                  <div className="progress-wrap">
                    <div className="progress" style={{ width: `${item.progress_percent}%` }} />
                  </div>
                  <p className="stat" style={{ marginTop: 6 }}>
                    Собрано: {formatMoney(item.contributed_amount)} из {formatMoney(item.goal_amount || item.price)} ({' '}
                    {item.progress_percent}%) · Участников: {item.contributors_count}
                  </p>
                </>
              )}

              {item.archived_reason && <p className="muted">{item.archived_reason}</p>}

              <div className="row">
                {item.product_url && (
                  <a className="btn btn-ghost" href={item.product_url} target="_blank" rel="noreferrer">
                    Открыть товар
                  </a>
                )}

                {(item.can_reserve || item.reserved_by_me) && (
                  <button className="btn btn-ok" onClick={() => reserve(item)} type="button">
                    {item.reserved_by_me ? 'Снять мою бронь' : 'Забронировать'}
                  </button>
                )}
              </div>

              {item.can_contribute && (
                <div style={{ marginTop: 10 }}>
                  <label className="label" htmlFor={`amount_${item.id}`}>
                    Вклад (мин. 100 ₽)
                  </label>
                  <div className="row">
                    <input
                      id={`amount_${item.id}`}
                      className="input"
                      type="number"
                      min="100"
                      step="10"
                      value={pendingAmounts[item.id] || ''}
                      onChange={(event) =>
                        setPendingAmounts((previous) => ({
                          ...previous,
                          [item.id]: event.target.value
                        }))
                      }
                    />
                    <button className="btn btn-primary" type="button" onClick={() => contribute(item)}>
                      Внести
                    </button>
                  </div>
                </div>
              )}
            </article>
          ))}
        </section>
      )}
    </main>
  );
}

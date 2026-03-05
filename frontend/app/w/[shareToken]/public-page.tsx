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
    setLoading(true); setError('');
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
    const stored = getViewerToken(shareToken);
    setViewerTokenState(stored);
    void load(stored);
  }, [shareToken]);

  useEffect(() => {
    const socket = new WebSocket(getWsUrl(shareToken));
    socket.onmessage = () => { void load(getViewerToken(shareToken)); };
    return () => socket.close();
  }, [shareToken]);

  const stats = useMemo(() => {
    if (!wishlist) return { total: 0, reserved: 0 };
    return { total: wishlist.items.length, reserved: wishlist.items.filter(i => i.reserved).length };
  }, [wishlist]);

  async function createSession(e: FormEvent) {
    e.preventDefault();
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
    if (!viewerToken) { setFlash('Введите имя ниже, чтобы забронировать подарок.'); return; }
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
    if (!viewerToken) { setFlash('Введите имя ниже, чтобы внести вклад.'); return; }
    const amount = Number(pendingAmounts[item.id]);
    if (!amount || Number.isNaN(amount)) { setError('Введите сумму вклада'); return; }
    setError('');
    try {
      await api.contribute(shareToken, item.id, amount, viewerToken);
      setPendingAmounts(prev => ({ ...prev, [item.id]: '' }));
      await load(viewerToken);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Не удалось внести вклад');
    }
  }

  if (loading) {
    return (
      <main className="page">
        <div className="empty-state"><div className="icon">⏳</div><p className="muted">Загрузка...</p></div>
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

  const progressPct = stats.total > 0 ? Math.round((stats.reserved / stats.total) * 100) : 0;

  return (
    <main className="page">
      {/* Hero */}
      <section className="hero animate-fade-up" style={{ marginBottom: 24 }}>
        <p className="hero-eyebrow">Вишлист</p>
        <h1>{wishlist.title}</h1>
        <p>{wishlist.description || 'Публичный вишлист без обязательной регистрации.'}</p>

        {/* Progress summary */}
        <div style={{ display: 'flex', gap: 20, alignItems: 'center', flexWrap: 'wrap', marginTop: 8 }}>
          <div className="stat-row">
            <div className="stat-item">
              <span className="value">{stats.total}</span>
              <span className="label">подарков</span>
            </div>
            <div className="stat-item">
              <span className="value">{stats.reserved}</span>
              <span className="label">закрыто</span>
            </div>
          </div>
          {stats.total > 0 && (
            <div style={{ flex: 1, minWidth: 160 }}>
              <div className="progress-wrap" style={{ height: 10 }}>
                <div className="progress" style={{ width: `${progressPct}%` }} />
              </div>
              <p className="stat" style={{ marginTop: 4 }}>{progressPct}% подарков закрыто</p>
            </div>
          )}
        </div>
      </section>

      {wishlist.deadline_passed && (
        <section className="card" style={{ marginBottom: 16, borderColor: 'rgba(212,70,58,.25)', background: '#fff6f5' }}>
          <h3 style={{ marginBottom: 6 }}>Срок списка завершён</h3>
          <p className="muted" style={{ fontSize: '.92rem' }}>
            После даты события новые брони и вклады закрываются автоматически.
          </p>
        </section>
      )}

      {/* Join session */}
      {!viewerToken && (
        <section className="card animate-fade-up" style={{ marginBottom: 20, animationDelay: '.05s' }}>
          <div style={{ display: 'flex', gap: 20, flexWrap: 'wrap', alignItems: 'center' }}>
            <div style={{ flex: 1, minWidth: 220 }}>
              <h3 style={{ marginBottom: 4 }}>Участвовать анонимно</h3>
              <p className="muted" style={{ fontSize: '.9rem' }}>Только подпись — владелец не узнает, кто именно бронирует.</p>
            </div>
            <form className="row" onSubmit={createSession} style={{ flexShrink: 0 }}>
              <input className="input" value={viewerName}
                onChange={(e) => setViewerName(e.target.value)}
                placeholder="Ваше имя" required style={{ width: 200 }} />
              <button className="btn btn-primary" type="submit">Войти как гость</button>
            </form>
          </div>
        </section>
      )}

      {viewerToken && (
        <div className="animate-fade-in" style={{ marginBottom: 16 }}>
          <span className="tag tag-green">✓ Вы вошли как гость</span>
        </div>
      )}

      {(error || flash) && (
        <div style={{ marginBottom: 16 }}>
          {error && <p className="error">{error}</p>}
          {flash && <p className="success">{flash}</p>}
        </div>
      )}

      {/* Items */}
      {wishlist.items.length === 0 ? (
        <div className="card empty-state animate-fade-in">
          <div className="icon">🎁</div>
          <h3>Подарки ещё не добавлены</h3>
          <p>Владелец ещё не добавил желания. Загляните позже!</p>
        </div>
      ) : (
        <section className="grid grid-2 animate-fade-up" style={{ animationDelay: '.1s' }}>
          {wishlist.items.map((item) => (
            <article key={item.id} className="item-card">
              {item.image_url && (
                <div className="item-card-img">
                  <Image src={item.image_url} alt={item.title} width={600} height={338} unoptimized />
                </div>
              )}
              <div className="item-card-body">
                <h3 style={{ fontSize: '1rem', lineHeight: 1.35 }}>{item.title}</h3>

                {item.price && (
                  <p style={{ fontWeight: 700, fontSize: '1.1rem', color: 'var(--ink)' }}>
                    {formatMoney(item.price)}
                  </p>
                )}

                <div className="row" style={{ gap: 6 }}>
                  {item.status === 'archived' && <span className="tag">📦 Архив</span>}
                  {item.reserved && <span className="tag tag-rose">🔒 Зарезервировано</span>}
                  {item.reserved_by_me && <span className="tag tag-green">✓ Мой выбор</span>}
                  {item.allow_contributions && !item.reserved && <span className="tag tag-indigo">🤝 Можно скинуться</span>}
                  {item.collection_status === 'underfunded' && <span className="tag">⚠ Не добрали</span>}
                </div>

                {item.allow_contributions && (
                  <div>
                    <div className="progress-wrap">
                      <div className="progress" style={{ width: `${item.progress_percent}%` }} />
                    </div>
                    <p className="stat" style={{ marginTop: 6 }}>
                      {formatMoney(item.contributed_amount)} из {formatMoney(item.goal_amount || item.price)}
                      {' · '}{item.progress_percent}%
                      {' · '}{item.contributors_count} участн.
                    </p>
                  </div>
                )}

                {item.archived_reason && <p className="muted" style={{ fontSize: '.85rem' }}>{item.archived_reason}</p>}
                {item.collection_status === 'underfunded' && item.remaining_amount && (
                  <p className="error" style={{ fontSize: '.85rem' }}>
                    Сбор не набрался к сроку. Не хватает: {formatMoney(item.remaining_amount)}.
                  </p>
                )}
                {item.collection_status === 'deadline_passed' && (
                  <p className="muted" style={{ fontSize: '.85rem' }}>
                    Дедлайн прошёл, поэтому сбор закрыт.
                  </p>
                )}
              </div>

              <div className="item-card-foot">
                {item.product_url && (
                  <a className="btn btn-ghost btn-sm" href={item.product_url} target="_blank" rel="noreferrer">
                    Открыть ↗
                  </a>
                )}

                {(item.can_reserve || item.reserved_by_me) && (
                  <button
                    className={`btn btn-sm ${item.reserved_by_me ? 'btn-ghost' : 'btn-ok'}`}
                    onClick={() => reserve(item)} type="button"
                  >
                    {item.reserved_by_me ? 'Снять бронь' : '✓ Забронировать'}
                  </button>
                )}
              </div>

              {item.can_contribute && (
                <div style={{ padding: '12px 20px 16px', borderTop: '1px solid var(--cream-3)', background: 'var(--cream)' }}>
                  <label className="label" htmlFor={`amount_${item.id}`}>Внести вклад (мин. 100 ₽)</label>
                  <div className="input-with-btn" style={{ marginTop: 6 }}>
                    <input
                      id={`amount_${item.id}`}
                      className="input"
                      type="number" min="100" step="10"
                      value={pendingAmounts[item.id] || ''}
                      onChange={(e) => setPendingAmounts(prev => ({ ...prev, [item.id]: e.target.value }))}
                      placeholder="Сумма"
                    />
                    <button className="btn btn-primary" type="button" onClick={() => contribute(item)}
                      style={{ flexShrink: 0 }}>
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

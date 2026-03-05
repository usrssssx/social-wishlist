'use client';

import Image from 'next/image';
import { FormEvent, useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { useParams, useRouter } from 'next/navigation';

import { api, getReadableError, getWsUrl } from '@/lib/api';
import type { WishlistOwnerDetail } from '@/lib/types';
import { formatMoney, getAuthToken } from '@/lib/utils';

export default function ManageWishlistPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const [token, setToken] = useState<string | null>(null);
  const [wishlist, setWishlist] = useState<WishlistOwnerDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const [title, setTitle] = useState('');
  const [productUrl, setProductUrl] = useState('');
  const [imageUrl, setImageUrl] = useState('');
  const [price, setPrice] = useState('');
  const [allowContributions, setAllowContributions] = useState(false);
  const [goalAmount, setGoalAmount] = useState('');
  const [saving, setSaving] = useState(false);
  const [info, setInfo] = useState('');
  const [copied, setCopied] = useState(false);
  const [editingItemId, setEditingItemId] = useState<string | null>(null);
  const [editTitle, setEditTitle] = useState('');
  const [editProductUrl, setEditProductUrl] = useState('');
  const [editImageUrl, setEditImageUrl] = useState('');
  const [editPrice, setEditPrice] = useState('');
  const [editAllowContributions, setEditAllowContributions] = useState(false);
  const [editGoalAmount, setEditGoalAmount] = useState('');
  const [editSaving, setEditSaving] = useState(false);

  async function load(authToken: string) {
    setLoading(true); setError('');
    try {
      const data = await api.getWishlist(authToken, params.id);
      setWishlist(data);
    } catch (err) {
      setError(getReadableError(err, 'Ошибка загрузки списка'));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    const authToken = getAuthToken();
    if (!authToken) { router.replace('/auth'); return; }
    setToken(authToken);
    void load(authToken);
  }, [params.id, router]);

  useEffect(() => {
    if (!wishlist || !token) return;
    const socket = new WebSocket(getWsUrl(wishlist.share_token));
    socket.onmessage = () => { void load(token); };
    return () => socket.close();
  }, [wishlist?.share_token, token]);

  const publicLink = useMemo(() => {
    if (!wishlist || typeof window === 'undefined') return '';
    return `${window.location.origin}/w/${wishlist.share_token}`;
  }, [wishlist]);

  async function onAutofill() {
    if (!token || !productUrl) return;
    setInfo(''); setError('');
    try {
      const data = await api.autofill(token, productUrl);
      if (data.title) setTitle(data.title);
      if (data.image_url) setImageUrl(data.image_url);
      if (data.price) setPrice(String(data.price));
      if (data.url) setProductUrl(data.url);
      setInfo('Данные подтянуты. Проверьте перед сохранением.');
    } catch (err) {
      setError(getReadableError(err, 'Не удалось подтянуть данные'));
    }
  }

  async function onCreateItem(e: FormEvent) {
    e.preventDefault();
    if (!token || !wishlist) return;
    setSaving(true); setError(''); setInfo('');
    try {
      const updated = await api.createItem(token, wishlist.id, {
        title: title.trim(), product_url: productUrl || null, image_url: imageUrl || null,
        price: price ? Number(price) : null, allow_contributions: allowContributions,
        goal_amount: allowContributions ? (goalAmount ? Number(goalAmount) : null) : null,
      });
      setWishlist(updated);
      setTitle(''); setProductUrl(''); setImageUrl('');
      setPrice(''); setGoalAmount(''); setAllowContributions(false);
    } catch (err) {
      setError(getReadableError(err, 'Не удалось добавить товар'));
    } finally {
      setSaving(false);
    }
  }

  async function onDeleteItem(itemId: string) {
    if (!token || !wishlist) return;
    setError('');
    try {
      const updated = await api.deleteItem(token, itemId);
      setWishlist(updated);
    } catch (err) {
      setError(getReadableError(err, 'Не удалось удалить товар'));
    }
  }

  function startEditItem(item: WishlistOwnerDetail['items'][number]) {
    setEditingItemId(item.id);
    setEditTitle(item.title);
    setEditProductUrl(item.product_url ?? '');
    setEditImageUrl(item.image_url ?? '');
    setEditPrice(item.price ?? '');
    setEditAllowContributions(item.allow_contributions);
    setEditGoalAmount(item.goal_amount ?? '');
    setError('');
    setInfo('');
  }

  function cancelEditItem() {
    setEditingItemId(null);
    setEditTitle('');
    setEditProductUrl('');
    setEditImageUrl('');
    setEditPrice('');
    setEditAllowContributions(false);
    setEditGoalAmount('');
  }

  async function onSaveEditItem(e: FormEvent, itemId: string) {
    e.preventDefault();
    if (!token || !wishlist) return;
    setEditSaving(true);
    setError('');
    setInfo('');
    try {
      const updated = await api.updateItem(token, itemId, {
        title: editTitle.trim(),
        product_url: editProductUrl || null,
        image_url: editImageUrl || null,
        price: editPrice ? Number(editPrice) : null,
        allow_contributions: editAllowContributions,
        goal_amount: editAllowContributions ? (editGoalAmount ? Number(editGoalAmount) : null) : null,
      });
      setWishlist(updated);
      cancelEditItem();
      setInfo('Товар обновлён.');
    } catch (err) {
      setError(getReadableError(err, 'Не удалось обновить товар'));
    } finally {
      setEditSaving(false);
    }
  }

  function copyLink() {
    if (!publicLink) return;
    void navigator.clipboard.writeText(publicLink);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
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
        <p className="error">{error || 'Wishlist не найден'}</p>
      </main>
    );
  }

  const reservedCount = wishlist.items.filter(i => i.reserved).length;

  return (
    <main className="page">
      {/* Header */}
      <div className="page-header animate-fade-up">
        <div>
          <Link href="/dashboard" className="btn btn-ghost btn-sm" style={{ marginBottom: 10, display: 'inline-flex' }}>
            ← Назад
          </Link>
          <h1 className="section-title">{wishlist.title}</h1>
          {wishlist.description && <p className="muted" style={{ marginTop: 4 }}>{wishlist.description}</p>}
        </div>
        <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center', flexShrink: 0 }}>
          <span className="tag">{wishlist.items.length} подарков</span>
          <span className="tag tag-green">{reservedCount} забронировано</span>
        </div>
      </div>

      {wishlist.deadline_passed && (
        <section className="card" style={{ marginBottom: 16, borderColor: 'rgba(212,70,58,.25)', background: '#fff6f5' }}>
          <h3 style={{ marginBottom: 6 }}>Дедлайн события прошёл</h3>
          <p className="muted" style={{ fontSize: '.92rem' }}>
            Новые брони и вклады закрыты. По незакрытым сборам можно договориться с участниками лично или перенести дату события.
          </p>
        </section>
      )}

      {/* Public link */}
      <section className="card animate-fade-up" style={{ marginBottom: 20, animationDelay: '.05s' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
          <div style={{ flex: 1, minWidth: 0 }}>
            <h3 style={{ marginBottom: 8, fontSize: '1rem' }}>Публичная ссылка</h3>
            <div className="link-box">
              <span style={{ fontSize: '.85rem' }}>🔗</span>
              <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {publicLink || `.../${wishlist.share_token}`}
              </span>
            </div>
          </div>
          <button className={`btn ${copied ? 'btn-ok' : 'btn-primary'}`} type="button" onClick={copyLink} style={{ flexShrink: 0 }}>
            {copied ? '✓ Скопировано' : 'Копировать'}
          </button>
        </div>
      </section>

      <section className="card" style={{ marginBottom: 20 }}>
        <h3 style={{ marginBottom: 8 }}>Как система ведёт себя в спорных кейсах</h3>
        <ul style={{ margin: 0, paddingLeft: 18, display: 'grid', gap: 6, color: 'var(--muted)' }}>
          <li>Вы не видите имена и суммы отдельных участников, только агрегаты.</li>
          <li>Если товар удалён после брони или вкладов, он уходит в архив с пояснением.</li>
          <li>После дедлайна новые брони и вклады блокируются автоматически.</li>
          <li>Недобранные к дедлайну сборы помечаются как «Не добрали» с остатком суммы.</li>
        </ul>
      </section>

      {/* Add item form */}
      <section className="card animate-fade-up" style={{ marginBottom: 28, animationDelay: '.08s' }}>
        <h3 style={{ marginBottom: 20 }}>Добавить подарок</h3>
        <form className="stack" onSubmit={onCreateItem}>
          <div className="form-group">
            <label className="label" htmlFor="productUrl">URL товара</label>
            <div className="input-with-btn">
              <input id="productUrl" className="input" value={productUrl}
                onChange={(e) => setProductUrl(e.target.value)} placeholder="https://..." />
              <button className="btn btn-ghost" type="button" onClick={onAutofill} style={{ flexShrink: 0 }}>
                ✨ Автозаполнить
              </button>
            </div>
          </div>

          <div className="grid grid-2" style={{ gap: 14 }}>
            <div className="form-group">
              <label className="label" htmlFor="title">Название *</label>
              <input id="title" className="input" value={title}
                onChange={(e) => setTitle(e.target.value)} required placeholder="Название подарка" />
            </div>
            <div className="form-group">
              <label className="label" htmlFor="price">Цена (₽)</label>
              <input id="price" className="input" type="number" min="0" step="1"
                value={price} onChange={(e) => setPrice(e.target.value)} placeholder="0" />
            </div>
          </div>

          <div className="form-group">
            <label className="label" htmlFor="image">URL изображения</label>
            <input id="image" className="input" value={imageUrl}
              onChange={(e) => setImageUrl(e.target.value)} placeholder="https://..." />
          </div>

          <label className="checkbox-row">
            <input type="checkbox" checked={allowContributions}
              onChange={(e) => setAllowContributions(e.target.checked)} />
            <span>Разрешить совместный сбор на этот подарок</span>
          </label>

          {allowContributions && (
            <div className="form-group">
              <label className="label" htmlFor="goalAmount">Цель сбора (₽)</label>
              <input id="goalAmount" className="input" type="number" min="0" step="1"
                value={goalAmount} onChange={(e) => setGoalAmount(e.target.value)}
                placeholder="Оставьте пустым — возьмём цену товара" />
            </div>
          )}

          {error && <p className="error">{error}</p>}
          {info && <p className="success">{info}</p>}

          <div>
            <button className="btn btn-primary" type="submit" disabled={saving}>
              {saving ? 'Сохраняем...' : '+ Добавить в список'}
            </button>
          </div>
        </form>
      </section>

      {/* Items */}
      {wishlist.items.length === 0 ? (
        <div className="card empty-state animate-fade-in">
          <div className="icon">🎁</div>
          <h3>Список пуст</h3>
          <p>Добавьте минимум 3 подарка: один до 3 000 ₽, один средний и один дорогой для совместного сбора.</p>
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

                <div className="row" style={{ gap: 6 }}>
                  {item.reserved && <span className="tag tag-rose">🔒 Забронировано</span>}
                  {item.allow_contributions && <span className="tag tag-indigo">🤝 Сбор</span>}
                  {item.collection_status === 'underfunded' && <span className="tag">⚠ Не добрали</span>}
                  {item.collection_status === 'deadline_passed' && <span className="tag">⌛ Дедлайн прошёл</span>}
                  {item.status === 'archived' && <span className="tag">📦 Архив</span>}
                </div>

                <div className="stat-row">
                  {item.price && (
                    <div className="stat-item">
                      <span style={{ fontWeight: 600, color: 'var(--ink)', fontSize: '1rem' }}>{formatMoney(item.price)}</span>
                      <span className="label">цена</span>
                    </div>
                  )}
                  {item.allow_contributions && (
                    <>
                      <div className="stat-item">
                        <span style={{ fontWeight: 600, color: 'var(--green)', fontSize: '1rem' }}>{formatMoney(item.contributed_amount)}</span>
                        <span className="label">собрано</span>
                      </div>
                      <div className="stat-item">
                        <span style={{ fontWeight: 600, color: 'var(--ink)', fontSize: '1rem' }}>{item.contributors_count}</span>
                        <span className="label">участников</span>
                      </div>
                    </>
                  )}
                </div>

                {item.archived_reason && <p className="muted" style={{ fontSize: '.85rem' }}>{item.archived_reason}</p>}
                {item.collection_status === 'underfunded' && item.remaining_amount && (
                  <p className="error" style={{ fontSize: '.85rem' }}>
                    Сбор не набрался к дате события. Не хватает: {formatMoney(item.remaining_amount)}.
                  </p>
                )}
                {item.collection_status === 'deadline_passed' && (
                  <p className="muted" style={{ fontSize: '.85rem' }}>
                    Дедлайн прошёл, этот сбор закрыт без вкладов.
                  </p>
                )}
              </div>
              <div className="item-card-foot">
                {item.product_url && (
                  <a className="btn btn-ghost btn-sm" href={item.product_url} target="_blank" rel="noreferrer">
                    Открыть ↗
                  </a>
                )}
                <button className="btn btn-ghost btn-sm" type="button" onClick={() => startEditItem(item)}>
                  Редактировать
                </button>
                <button className="btn btn-danger btn-sm" type="button" onClick={() => onDeleteItem(item.id)}>
                  Удалить
                </button>
              </div>

              {editingItemId === item.id && (
                <form
                  onSubmit={(e) => onSaveEditItem(e, item.id)}
                  style={{
                    padding: '12px 20px 16px',
                    borderTop: '1px solid var(--cream-3)',
                    background: '#fffdf8',
                    display: 'grid',
                    gap: 10,
                  }}
                >
                  <div className="form-group">
                    <label className="label" htmlFor={`edit_title_${item.id}`}>Название</label>
                    <input
                      id={`edit_title_${item.id}`}
                      className="input"
                      value={editTitle}
                      onChange={(e) => setEditTitle(e.target.value)}
                      required
                    />
                  </div>
                  <div className="form-group">
                    <label className="label" htmlFor={`edit_url_${item.id}`}>URL товара</label>
                    <input
                      id={`edit_url_${item.id}`}
                      className="input"
                      value={editProductUrl}
                      onChange={(e) => setEditProductUrl(e.target.value)}
                      placeholder="https://..."
                    />
                  </div>
                  <div className="form-group">
                    <label className="label" htmlFor={`edit_image_${item.id}`}>URL изображения</label>
                    <input
                      id={`edit_image_${item.id}`}
                      className="input"
                      value={editImageUrl}
                      onChange={(e) => setEditImageUrl(e.target.value)}
                      placeholder="https://..."
                    />
                  </div>
                  <div className="grid grid-2" style={{ gap: 8 }}>
                    <div className="form-group">
                      <label className="label" htmlFor={`edit_price_${item.id}`}>Цена</label>
                      <input
                        id={`edit_price_${item.id}`}
                        className="input"
                        type="number"
                        min="0"
                        step="1"
                        value={editPrice}
                        onChange={(e) => setEditPrice(e.target.value)}
                      />
                    </div>
                    <div className="form-group">
                      <label className="label" htmlFor={`edit_goal_${item.id}`}>Цель сбора</label>
                      <input
                        id={`edit_goal_${item.id}`}
                        className="input"
                        type="number"
                        min="0"
                        step="1"
                        value={editGoalAmount}
                        onChange={(e) => setEditGoalAmount(e.target.value)}
                        disabled={!editAllowContributions}
                      />
                    </div>
                  </div>
                  <label className="checkbox-row">
                    <input
                      type="checkbox"
                      checked={editAllowContributions}
                      onChange={(e) => setEditAllowContributions(e.target.checked)}
                    />
                    <span>Разрешить совместный сбор</span>
                  </label>
                  <div className="row">
                    <button className="btn btn-primary btn-sm" type="submit" disabled={editSaving}>
                      {editSaving ? 'Сохраняем...' : 'Сохранить'}
                    </button>
                    <button className="btn btn-ghost btn-sm" type="button" onClick={cancelEditItem}>
                      Отмена
                    </button>
                  </div>
                </form>
              )}
            </article>
          ))}
        </section>
      )}
    </main>
  );
}

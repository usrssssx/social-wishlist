'use client';

import Image from 'next/image';
import { FormEvent, useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { useParams, useRouter } from 'next/navigation';

import { api, getWsUrl } from '@/lib/api';
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

  async function load(authToken: string) {
    setLoading(true);
    setError('');
    try {
      const data = await api.getWishlist(authToken, params.id);
      setWishlist(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Ошибка загрузки списка');
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
    void load(authToken);
  }, [params.id, router]);

  useEffect(() => {
    if (!wishlist || !token) return;

    const socket = new WebSocket(getWsUrl(wishlist.share_token));
    socket.onmessage = () => {
      void load(token);
    };

    return () => {
      socket.close();
    };
  }, [wishlist?.share_token, token]);

  const publicLink = useMemo(() => {
    if (!wishlist || typeof window === 'undefined') return '';
    return `${window.location.origin}/w/${wishlist.share_token}`;
  }, [wishlist]);

  async function onAutofill() {
    if (!token || !productUrl) return;
    setInfo('');
    setError('');
    try {
      const data = await api.autofill(token, productUrl);
      if (data.title) setTitle(data.title);
      if (data.image_url) setImageUrl(data.image_url);
      if (data.price) setPrice(String(data.price));
      if (data.url) setProductUrl(data.url);
      setInfo('Данные подтянуты автоматически. Проверьте перед сохранением.');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Не удалось подтянуть данные');
    }
  }

  async function onCreateItem(event: FormEvent) {
    event.preventDefault();
    if (!token || !wishlist) return;
    setSaving(true);
    setError('');
    setInfo('');

    try {
      const updated = await api.createItem(token, wishlist.id, {
        title: title.trim(),
        product_url: productUrl || null,
        image_url: imageUrl || null,
        price: price ? Number(price) : null,
        allow_contributions: allowContributions,
        goal_amount: allowContributions ? (goalAmount ? Number(goalAmount) : null) : null
      });
      setWishlist(updated);
      setTitle('');
      setProductUrl('');
      setImageUrl('');
      setPrice('');
      setGoalAmount('');
      setAllowContributions(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Не удалось добавить товар');
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
      setError(err instanceof Error ? err.message : 'Не удалось удалить товар');
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
        <p className="error">{error || 'Wishlist не найден'}</p>
      </main>
    );
  }

  return (
    <main className="page">
      <div className="header">
        <section>
          <h1 className="section-title">{wishlist.title}</h1>
          <p className="muted">{wishlist.description || 'Без описания'}</p>
        </section>
        <Link href="/dashboard" className="btn btn-ghost">
          Назад
        </Link>
      </div>

      <section className="card" style={{ marginBottom: 16 }}>
        <h3 style={{ marginTop: 0 }}>Публичная ссылка</h3>
        <p className="muted" style={{ marginTop: 6 }}>
          {publicLink || `.../w/${wishlist.share_token}`}
        </p>
        <button
          className="btn btn-primary"
          type="button"
          onClick={() => {
            if (!publicLink) return;
            void navigator.clipboard.writeText(publicLink);
          }}
        >
          Копировать ссылку
        </button>
      </section>

      <section className="card" style={{ marginBottom: 16 }}>
        <h3 style={{ marginTop: 0 }}>Добавить подарок</h3>
        <form className="grid" onSubmit={onCreateItem}>
          <div>
            <label className="label" htmlFor="productUrl">
              URL товара
            </label>
            <div className="row">
              <input
                id="productUrl"
                className="input"
                value={productUrl}
                onChange={(event) => setProductUrl(event.target.value)}
                placeholder="https://..."
              />
              <button className="btn btn-ghost" onClick={onAutofill} type="button">
                Автозаполнить
              </button>
            </div>
          </div>

          <div className="grid grid-2">
            <div>
              <label className="label" htmlFor="title">
                Название
              </label>
              <input
                id="title"
                className="input"
                value={title}
                onChange={(event) => setTitle(event.target.value)}
                required
              />
            </div>

            <div>
              <label className="label" htmlFor="price">
                Цена
              </label>
              <input
                id="price"
                className="input"
                type="number"
                min="0"
                step="1"
                value={price}
                onChange={(event) => setPrice(event.target.value)}
              />
            </div>
          </div>

          <div>
            <label className="label" htmlFor="image">
              URL картинки
            </label>
            <input
              id="image"
              className="input"
              value={imageUrl}
              onChange={(event) => setImageUrl(event.target.value)}
              placeholder="https://..."
            />
          </div>

          <label className="row" style={{ alignItems: 'center' }}>
            <input
              type="checkbox"
              checked={allowContributions}
              onChange={(event) => setAllowContributions(event.target.checked)}
            />
            <span>Разрешить общий сбор на этот подарок</span>
          </label>

          {allowContributions && (
            <div>
              <label className="label" htmlFor="goalAmount">
                Цель сбора
              </label>
              <input
                id="goalAmount"
                className="input"
                type="number"
                min="0"
                step="1"
                value={goalAmount}
                onChange={(event) => setGoalAmount(event.target.value)}
                placeholder="Если пусто, возьмём цену товара"
              />
            </div>
          )}

          {error && <p className="error">{error}</p>}
          {info && <p className="success">{info}</p>}

          <button className="btn btn-primary" type="submit" disabled={saving}>
            {saving ? 'Сохраняем...' : 'Добавить в список'}
          </button>
        </form>
      </section>

      {wishlist.items.length === 0 ? (
        <section className="card">
          <h3 style={{ marginTop: 0 }}>Пока пусто</h3>
          <p className="muted">
            Добавьте хотя бы 3 позиции: одна до 3000 ₽, одна в среднем бюджете и одна дорогая для коллективного
            сбора.
          </p>
        </section>
      ) : (
        <section className="grid grid-2">
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
              <p className="stat">
                Цена: {formatMoney(item.price)} · Собрано: {formatMoney(item.contributed_amount)} · Участников:{' '}
                {item.contributors_count}
              </p>
              <div className="row" style={{ marginBottom: 8 }}>
                <span className="tag">{item.reserved ? 'Забронировано/закрыто' : 'Свободно'}</span>
                {item.allow_contributions && <span className="tag">Совместный сбор</span>}
                {item.status === 'archived' && <span className="tag">Архив</span>}
              </div>
              {item.archived_reason && <p className="muted">{item.archived_reason}</p>}
              <div className="row">
                {item.product_url && (
                  <a className="btn btn-ghost" href={item.product_url} target="_blank" rel="noreferrer">
                    Открыть товар
                  </a>
                )}
                <button className="btn btn-danger" type="button" onClick={() => onDeleteItem(item.id)}>
                  Удалить
                </button>
              </div>
            </article>
          ))}
        </section>
      )}
    </main>
  );
}

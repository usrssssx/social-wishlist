import Link from 'next/link';

export default function HomePage() {
  return (
    <main className="page">
      <section className="hero">
        <h1>Social Wish List</h1>
        <p>
          Создавай вишлисты, делись ссылкой и избегай дублей подарков. Друзья резервируют позиции или
          скидываются на дорогие вещи, а ты видишь только прогресс без раскрытия имён.
        </p>
        <div className="row">
          <Link className="btn btn-primary" href="/auth">
            Войти / зарегистрироваться
          </Link>
        </div>
      </section>

      <section style={{ marginTop: 20 }} className="grid grid-2">
        <article className="card">
          <h3>Реалтайм без перезагрузки</h3>
          <p className="muted">Бронь и вклад моментально появляются у всех участников через WebSocket.</p>
        </article>
        <article className="card">
          <h3>Сюрприз не ломается</h3>
          <p className="muted">Владелец видит только факт брони и сумму сбора, но не кто именно участвовал.</p>
        </article>
      </section>
    </main>
  );
}

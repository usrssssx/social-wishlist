import Link from 'next/link';

export default function HomePage() {
  return (
    <main className="page">
      {/* Hero */}
      <section className="hero animate-fade-up" style={{ marginBottom: 32 }}>
        <p className="hero-eyebrow">Социальный вишлист</p>
        <h1>
          Подарки, которые
          <br />
          <em>действительно</em> хочется
        </h1>
        <p>
          Создавай вишлисты, делись ссылкой и забудь про дубли. Друзья
          резервируют подарки или скидываются на дорогие — а ты видишь
          только прогресс, без раскрытия имён.
        </p>
        <div className="row">
          <Link className="btn btn-primary btn-lg" href="/auth">
            Начать бесплатно
          </Link>
          <Link className="btn btn-ghost btn-lg" href="/auth">
            Войти
          </Link>
        </div>
      </section>

      {/* Features */}
      <section className="grid grid-3 animate-fade-up" style={{ animationDelay: '.1s' }}>
        <article className="feature-card">
          <div className="feature-icon">⚡</div>
          <h3>Реалтайм без перезагрузки</h3>
          <p className="muted" style={{ fontSize: '.92rem', lineHeight: 1.65, marginTop: 4 }}>
            Бронь и вклад моментально появляются у всех участников через WebSocket.
          </p>
        </article>

        <article className="feature-card">
          <div className="feature-icon">🎁</div>
          <h3>Сюрприз не ломается</h3>
          <p className="muted" style={{ fontSize: '.92rem', lineHeight: 1.65, marginTop: 4 }}>
            Владелец видит только факт брони и сумму сбора, но не кто именно участвовал.
          </p>
        </article>

        <article className="feature-card">
          <div className="feature-icon">🤝</div>
          <h3>Совместные подарки</h3>
          <p className="muted" style={{ fontSize: '.92rem', lineHeight: 1.65, marginTop: 4 }}>
            Друзья могут скинуться на дорогой подарок — прогресс-бар покажет сколько собрали.
          </p>
        </article>
      </section>

      {/* How it works */}
      <section className="animate-fade-up" style={{ marginTop: 48, animationDelay: '.2s' }}>
        <div className="section-header">
          <h2 className="section-title">Как это работает</h2>
        </div>
        <div className="grid grid-2" style={{ gap: 16 }}>
          {[
            { n: '01', title: 'Создай вишлист', text: 'Добавь подарки с ценами и картинками — вручную или автозаполнением по ссылке.' },
            { n: '02', title: 'Поделись ссылкой', text: 'Отправь публичную ссылку друзьям — регистрация не нужна, только имя.' },
            { n: '03', title: 'Друзья бронируют', text: 'Каждый видит что ещё свободно и может забронировать или скинуться.' },
            { n: '04', title: 'Ты в предвкушении', text: 'Видишь только что и сколько собрали — никаких спойлеров.' },
          ].map(({ n, title, text }) => (
            <article key={n} className="card" style={{ display: 'flex', gap: 16, alignItems: 'flex-start' }}>
              <span style={{
                fontFamily: 'var(--font-mono)',
                fontSize: '.75rem',
                fontWeight: 500,
                color: 'var(--rose)',
                background: '#fdf1f0',
                border: '1px solid rgba(212,70,58,.15)',
                borderRadius: 6,
                padding: '4px 8px',
                flexShrink: 0,
                marginTop: 2,
              }}>{n}</span>
              <div>
                <h3 style={{ fontSize: '1rem', marginBottom: 4 }}>{title}</h3>
                <p className="muted" style={{ fontSize: '.9rem', lineHeight: 1.6 }}>{text}</p>
              </div>
            </article>
          ))}
        </div>
      </section>

      <section className="card animate-fade-up" style={{ marginTop: 28, animationDelay: '.25s' }}>
        <h3 style={{ marginBottom: 8 }}>Прозрачные правила</h3>
        <ul style={{ margin: 0, paddingLeft: 18, display: 'grid', gap: 6, color: 'var(--muted)' }}>
          <li>Владелец не видит, кто конкретно бронировал или вносил деньги.</li>
          <li>Удаление товара с бронями/вкладами не стирает историю: товар уходит в архив.</li>
          <li>После даты события новые брони и вклады блокируются автоматически.</li>
          <li>Недобранные сборы помечаются отдельно, с видимым остатком суммы.</li>
        </ul>
      </section>

    </main>
  );
}

import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Условия использования',
};

export default function TermsPage() {
  return (
    <main className="page">
      <section className="card animate-fade-up" style={{ maxWidth: 900, margin: '0 auto' }}>
        <h1 style={{ marginBottom: 10 }}>Условия использования</h1>
        <p className="muted" style={{ marginBottom: 20 }}>
          Актуально на 5 марта 2026 года.
        </p>

        <div className="stack" style={{ gap: 18 }}>
          <section>
            <h3>1. Назначение сервиса</h3>
            <p className="muted">
              Сервис помогает создавать и публиковать вишлисты, резервировать подарки и отслеживать прогресс совместных
              сборов.
            </p>
          </section>

          <section>
            <h3>2. Ответственность пользователя</h3>
            <p className="muted">
              Пользователь отвечает за корректность ссылок, описаний и уместность публикуемого контента. Запрещено
              использовать сервис для незаконных действий и спама.
            </p>
          </section>

          <section>
            <h3>3. Публичные ссылки</h3>
            <p className="muted">
              Любой, у кого есть публичная ссылка, может просматривать вишлист и взаимодействовать с ним как гость.
              Владелец сам управляет распространением ссылки.
            </p>
          </section>

          <section>
            <h3>4. Доступность</h3>
            <p className="muted">
              Мы стремимся к непрерывной работе сервиса, но допускаются технические окна обслуживания и временные сбои.
            </p>
          </section>

          <section>
            <h3>5. Удаление аккаунта</h3>
            <p className="muted">
              Пользователь может удалить аккаунт самостоятельно в кабинете. После удаления восстановление данных не
              гарантируется.
            </p>
          </section>

          <section>
            <h3>6. Изменения условий</h3>
            <p className="muted">
              Мы можем обновлять условия. Актуальная версия всегда доступна на этой странице.
            </p>
          </section>
        </div>
      </section>
    </main>
  );
}

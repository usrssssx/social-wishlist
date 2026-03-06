import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Политика конфиденциальности',
};

export default function PrivacyPage() {
  return (
    <main className="page">
      <section className="card animate-fade-up" style={{ maxWidth: 900, margin: '0 auto' }}>
        <h1 style={{ marginBottom: 10 }}>Политика конфиденциальности</h1>
        <p className="muted" style={{ marginBottom: 20 }}>
          Актуально на 5 марта 2026 года.
        </p>

        <div className="stack" style={{ gap: 18 }}>
          <section>
            <h3>1. Какие данные мы храним</h3>
            <p className="muted">
              Email, имя аккаунта, хэш пароля, созданные вами вишлисты и товары в них, а также технические логи
              безопасности и доставки писем.
            </p>
          </section>

          <section>
            <h3>2. Для чего мы используем данные</h3>
            <p className="muted">
              Для работы аккаунта, авторизации, отправки писем подтверждения/сброса пароля, защиты от злоупотреблений и
              поддержки realtime-обновлений.
            </p>
          </section>

          <section>
            <h3>3. Кто видит ваши данные</h3>
            <p className="muted">
              Публичная ссылка открывает только вишлист. Email владельца и личные данные участников не показываются
              гостям. Владелец не видит, кто именно бронировал или вносил вклад.
            </p>
          </section>

          <section>
            <h3>4. Хранение и безопасность</h3>
            <p className="muted">
              Пароли хранятся только в виде криптографического хэша. Доступ к продакшен-данным ограничен техническими
              правами и журналируется.
            </p>
          </section>

          <section>
            <h3>5. Удаление аккаунта и данных</h3>
            <p className="muted">
              Вы можете удалить аккаунт в разделе «Настройки аккаунта» в кабинете. При удалении удаляются аккаунт и
              связанные персональные данные, включая ваши вишлисты.
            </p>
          </section>

          <section>
            <h3>6. Контакт</h3>
            <p className="muted">
              По вопросам персональных данных используйте канал поддержки проекта.
            </p>
          </section>
        </div>
      </section>
    </main>
  );
}

# Incident Runbook

## Каналы оповещения

- Slack webhook: `ONCALL_SLACK_WEBHOOK_URL`
- Telegram bot: `ONCALL_TELEGRAM_BOT_TOKEN` + `ONCALL_TELEGRAM_CHAT_ID`
- Generic webhook (опционально): `ONCALL_WEBHOOK_URL`

Автопроверка каждые 5 минут: `.github/workflows/oncall-healthcheck.yml`.

## P0: сервис недоступен

1. Проверить `https://<backend>/health` и `https://<backend>/health/readiness`.
2. Открыть логи `swl-backend` на Render и найти последние `5xx`.
3. Если проблема в конфиге (`readiness=false`) — откатить/исправить env и сделать redeploy.
4. Если проблема в миграции/БД — остановить новые деплои и перейти к плану восстановления.

## P1: деградация realtime

1. Проверить `realtime_ok` в `/health/readiness`.
2. Убедиться, что `REDIS_URL` задан и Redis доступен.
3. Проверить, что websocket-путь `/ws/w/<share_token>` работает в двух вкладках.
4. Если Redis недоступен — временно работать в single-instance режиме и ограничить масштабирование.

## P1: email/verify/reset проблемы

1. Проверить `email_ok` в `/health/readiness`.
2. Проверить `RESEND_API_KEY`/SMTP env.
3. Проверить webhook endpoint `POST /api/webhooks/resend` и `RESEND_WEBHOOK_SECRET`.

## Восстановление БД

1. Взять последний backup (`scheduled-db-backup.yml` artifacts или внешнее хранилище).
2. Поднять временную БД и выполнить test-restore.
3. При успешном тесте выполнить restore в прод БД в окно обслуживания.
4. Прогнать smoke: `scripts/smoke_prod.sh` и `scripts/sentry_alert_smoke.sh`.

## Пост-инцидент

1. Зафиксировать таймлайн и RCA.
2. Добавить тест/алерт на выявленную причину.
3. Обновить runbook и чеклисты.

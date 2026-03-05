# Backup и Restore PostgreSQL

## Требования

- Установлены `pg_dump` и `pg_restore`.
- Есть `DATABASE_URL` для нужной БД.

## Backup

```bash
DATABASE_URL=postgresql://... \
BACKUP_DIR=./backups \
./scripts/db_backup.sh
```

Результат: файл `social_wishlist_<UTC_TIMESTAMP>.dump` в `BACKUP_DIR`.

## Restore

Внимание: restore перезаписывает текущие таблицы.

```bash
DATABASE_URL=postgresql://... \
DUMP_FILE=./backups/social_wishlist_20260305T120000Z.dump \
FORCE_RESTORE=true \
./scripts/db_restore.sh
```

## Рекомендация для продакшена

1. Делать backup перед каждым деплоем схемы или массовыми миграциями.
2. Хранить минимум 7 последних дампов во внешнем хранилище (S3/GCS/аналог).
3. Раз в месяц прогонять тестовый restore на отдельной БД.

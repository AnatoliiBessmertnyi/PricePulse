# How We Work

Документ описывает стандарты разработки проекта PricePulse.

---

# Основные принципы

## 1. Читаемость важнее краткости

Плохой код:

```python
p = await repo.get(id)
```

Хороший код:

```python
subscription = await subscription_repository.get_by_id(subscription_id)
```

Код читается значительно чаще, чем пишется.

---

## 2. Явное лучше неявного

Следуем принципам PEP20.

Предпочитаем:

```python
if subscription is None:
    raise SubscriptionNotFoundError()
```

вместо сложных вложенных конструкций.

---

## 3. Один модуль — одна ответственность

Каждый модуль отвечает только за одну задачу.

Примеры:

* repositories → работа с БД
* services → бизнес-логика
* api → HTTP интерфейс
* workers → фоновые задачи
* parsers → получение данных с маркетплейсов

---

## 4. Не смешиваем слои

Запрещено:

API → БД напрямую

```python
@router.post("/")
async def create_subscription():
    session.add(...)
```

Правильно:

```text
Router
  ↓
Service
  ↓
Repository
  ↓
Database
```

---

## 5. Типизация обязательна

Каждая публичная функция должна иметь типы.

Пример:

```python
async def get_subscription(
    subscription_id: int,
) -> Subscription:
    ...
```

Используем строгий mypy режим.

---

## 6. Асинхронность по умолчанию

Все операции ввода-вывода должны быть асинхронными:

* PostgreSQL
* Redis
* HTTP запросы
* Telegram API

Запрещено использовать синхронные клиенты.

---

## 7. Dependency Injection

Сервисы не создают зависимости самостоятельно.

Плохо:

```python
service = SubscriptionService()
```

Хорошо:

```python
service = SubscriptionService(repository)
```

## 8. Dependency Management

Используем:

- pyproject.toml
- uv

Не используем:

- requirements.txt
- pip freeze

Все зависимости описываются только в pyproject.toml.

---

# Архитектура

```text
API
 ↓
Services
 ↓
Repositories
 ↓
PostgreSQL
```

Отдельно:

```text
Celery Worker
 ↓
Services
 ↓
Repositories
 ↓
PostgreSQL
```

---

# Работа с Базой Данных

## Репозитории

Каждая сущность имеет собственный репозиторий.

Примеры:

* UserRepository
* SubscriptionRepository
* PriceHistoryRepository

---

## Миграции

Любое изменение схемы БД сопровождается миграцией Alembic.

Порядок:

1. Изменить модель.
2. Создать миграцию.
3. Проверить миграцию.
4. Закоммитить вместе с кодом.

---

# Работа с API

## Версионирование

Все эндпоинты размещаются внутри:

```text
/api/v1/
```

Пример:

```text
POST /api/v1/subscriptions
```

---

## Ответы API

Успешный ответ:

```json
{
  "status": "success",
  "data": {}
}
```

Ошибка:

```json
{
  "status": "error",
  "message": "Subscription not found"
}
```

---

# Работа с Celery

В очередь передаются только идентификаторы.

Плохо:

```python
parse_price_task.delay(url)
```

Хорошо:

```python
parse_price_task.delay(subscription_id)
```

Воркер самостоятельно получает данные из БД.

---

# Работа с Парсерами

Каждый маркетплейс имеет отдельный парсер.

Пример:

```python
class OzonParser(BaseParser):
    ...
```

Все парсеры реализуют единый интерфейс.

---

# Логирование

Используем structlog.

Запрещено:

```python
print("price changed")
```

Используем:

```python
logger.info(
    "price_changed",
    subscription_id=sub_id,
    old_price=old_price,
    new_price=new_price,
)
```

---

# Тестирование

Минимальные требования:

* сервисы тестируются
* репозитории тестируются
* парсеры тестируются

Новый функционал без тестов не считается завершенным.

---

# Git Workflow

Основная ветка:

```text
main
```

Разработка:

```text
dev
```

Каждая задача:

```text
feature/<task-name>
```

Примеры:

```text
feature/add-subscriptions-api
feature/ozon-parser
feature/celery-worker
```

---

# Code Review Checklist

Перед merge необходимо проверить:

* Код проходит линтеры
* Код проходит тесты
* Есть типизация
* Нет дублирования
* Нет print()
* Нет закомментированного кода
* Есть обработка ошибок
* Есть логирование

---

# Commit Convention
Используем Gitmoji + Conventional Commits.

Формат:
<gitmoji> <type>: <description>

Примеры:
🎉 feat: initialize project
✨ feat: add subscription api
🐛 fix: handle parser timeout
♻️ refactor: split parser service
📝 docs: update architecture
✅ test: add parser tests
🔧 chore: configure docker compose
🚀 feat: add celery worker
🔒 security: validate incoming urls
🔥 chore: remove deprecated code

---

Основные Gitmoji
🎉 — начало проекта
✨ — новый функционал
🐛 — исправление ошибки
♻️ — рефакторинг
📝 — документация
✅ — тесты
🔧 — конфигурация
🚀 — деплой или инфраструктура
🔥 — удаление кода
🔒 — безопасность

---

# Главное правило

Любое решение должно делать код:

1. Проще читать
2. Проще тестировать
3. Проще расширять

Если решение ухудшает хотя бы один из пунктов — требуется пересмотр.


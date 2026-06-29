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

### Исключение: Celery Worker

Celery задачи выполняются в синхронном контексте, но внутри используют `asyncio.run()` для вызова асинхронных сервисов.

Для Redis используются два клиента:
* **FastAPI** — `redis.asyncio.Redis` (асинхронный)
* **Celery Worker** — `redis.Redis` (синхронный)

Это необходимо для избежания конфликтов event loop.

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

## 9. Virtual Environment

Используем только:

- uv
- .venv

Команды:

```bash
uv sync
uv add <package>
uv remove <package>
uv run <command>
```

Не используем:

- venv/
- virtualenv
- pip install
- requirements.txt

Файл uv.lock обязательно коммитится в репозиторий.

## 10. Не передаем бизнес-данные между сервисами
В очередь и между сервисами передаются только идентификаторы.

Плохо:
parse_price_task.delay(url, price)

Хорошо:
parse_price_task.delay(subscription_id)

## 11. Каждый сервис считается потенциально недоступным
При разработке предполагается, что любой внешний компонент может быть временно недоступен.

Следует предусматривать:

- retry;
- timeout;
- обработку ошибок;
- идемпотентность операций.

## 12. Сервисы должны быть заменяемыми
Бизнес-логика не должна зависеть от конкретной реализации инфраструктуры.

Например:

- ParserFactory не знает о FastAPI;
- Service не знает о Celery;
- Repository не знает о PostgreSQL.

Зависимости инвертируются через интерфейсы и Dependency Injection.

## 13. Не использовать БД как очередь сообщений
**PostgreSQL хранит данные.**

**RabbitMQ доставляет сообщения.**

Нельзя использовать таблицы БД как механизм обмена сообщениями между сервисами.

И наоборот:

RabbitMQ не хранит бизнес-данные.

## 14. Изолированные async engine в Celery задачах

Каждая Celery задача, работающая с БД, должна создавать собственный async SQLAlchemy engine вместо использования глобального.

Плохо:

```python
async def _check_all_subscriptions() -> None:
    async for session in get_db():  # Использует глобальный engine
        service = get_subscription_service(session)
        ...
```

Хорошо:

```python
async def _check_all_subscriptions() -> None:
    engine = create_async_engine(settings.postgres_url, ...)
    async_session_factory = async_sessionmaker(bind=engine, ...)
    
    try:
        async with async_session_factory() as session:
            result = await session.execute(
                select(Subscription).where(Subscription.is_active)
            )
            subscriptions = result.scalars().all()
            
            for subscription in subscriptions:
                parse_price.delay(subscription.id)
    finally:
        await engine.dispose()
```

Причина: глобальный engine привязан к event loop, созданному при импорте модуля. Celery использует **asyncio.run()**, который создаёт новый event loop для каждой задачи, что приводит к конфликтам.


## 15. Playwright для парсинга маркетплейсов

Для парсинга маркетплейсов с продвинутой защитой (Ozon) используется Playwright (headless Chromium) вместо HTTP-клиентов.

Запрещено:

```python
import httpx

async with httpx.AsyncClient() as client:
    response = await client.get(url)  # Блокируется Ozon
```

Правильно:

```python
from playwright.async_api import async_playwright

async with async_playwright() as p:
    browser = await p.chromium.launch(headless=True)
    page = await browser.new_page()
    await page.goto(url)
    html = await page.content()
    await browser.close()
```

Причина: Ozon использует JavaScript challenges, TLS fingerprinting и блокирует обычные HTTP-запросы.

Компромиссы:
- Парсинг занимает 6-9 секунд вместо 1-2 секунд
- Требует установки Chromium и системных зависимостей
- Потребляет больше памяти (~200-300 МБ на браузер)

### Конфигурация Docker
Для запуска Playwright в Docker необходимо:

1. Установить системные зависимости:

```dockerfile
RUN apt-get update && apt-get install -y --no-install-recommends wget
RUN uv run playwright install chromium
RUN uv run playwright install-deps chromium
```
2. Использовать флаги --no-sandbox и --disable-setuid-sandbox:

```python
browser = await p.chromium.launch(
    headless=True,
    args=["--no-sandbox", "--disable-setuid-sandbox"],
)
```

Эти флаги обязательны для запуска Chromium в Docker-контейнере от root.


# Архитектура

```text
FastAPI
    ↓
Services
    ↓
Repositories
    ↓
PostgreSQL

Celery Worker
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

Воркер самостоятельно получает необходимые данные из БД.

Celery используется только как механизм доставки задач между сервисами.

## Конфигурация воркера

Воркер запускается с `--pool=prefork` для избежания конфликтов event loop:

```bash
uv run celery -A app.workers.celery_app:celery_app worker --pool=prefork --loglevel=info
```

Каждый процесс имеет свой event loop, что позволяет использовать asyncio.run() без конфликтов.

### Periodic Tasks

Для периодических задач используется Celery Beat.

Пример конфигурации:

```python
# app/workers/beat_schedule.py
beat_schedule = {
    "check-all-subscriptions": {
        "task": TASK_CHECK_ALL_SUBSCRIPTIONS,
        "schedule": 900.0,  # 15 минут
    }
}
```

Задача должна:

- Создавать собственный async engine
- Получать данные из БД
- Ставить задачи в очередь
- Закрывать engine в finally блоке

### Graceful Shutdown

При остановке воркера необходимо корректно закрывать ресурсы:

```python
from celery.signals import worker_shutdown

@worker_shutdown.connect
def on_worker_shutdown(**kwargs):
    import asyncio
    asyncio.run(close_browser())
```

Это гарантирует, что Playwright браузер закрывается корректно.

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
* Нет сильной связанности между компонентами

---

# Commit Convention
Используем Gitmoji + Conventional Commits.

Формат:
<gitmoji> <type>: <description>

Примеры:
🎉 feat: initialize project
✨ feat: add subscription api
✨ feat: integrate Playwright for Ozon parsing
✨ feat: add Celery Beat for periodic price checking
🐛 fix: handle parser timeout
🐛 fix: resolve event loop conflicts in Celery tasks
♻️ refactor: split parser service
📝 docs: update architecture
✅ test: add parser tests
🔧 chore: configure docker compose
🔧 chore: add Playwright system dependencies to Dockerfile
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

Любое изменение проекта должно делать систему:

1. Проще читать.
2. Проще тестировать.
3. Проще расширять.
4. Проще сопровождать.
5. Более устойчивой к отказам.

Если решение ухудшает хотя бы один из пунктов — требуется пересмотр.


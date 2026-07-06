# PricePulse

PricePulse — сервис мониторинга цен на маркетплейсах с уведомлениями в Telegram.

Пользователь добавляет ссылку на товар через Telegram-бота. Система периодически проверяет цену, сохраняет историю изменений и уведомляет пользователя при изменении стоимости товара.

---

# Возможности

Планируемый функционал:

* Мониторинг цен на Ozon
* Мониторинг цен на Wildberries
* Мониторинг цен на Яндекс.Маркет
* Уведомления в Telegram
* История изменения цен
* Графики изменения стоимости
* Несколько подписок на пользователя

---

# Архитектура

```text
                Telegram
                    │
                    ▼
           Telegram Bot
                    │
                    ▼
                FastAPI ──────────► Redis (кэш)
                    │
          ┌─────────┴─────────┐
          │                   │
          ▼                   ▼
     PostgreSQL           RabbitMQ
                              │
                              ▼
                        Celery Beat
                        (каждые 15 мин)
                              │
                              ▼
                       Celery Worker
                              │
                              ▼
                     Playwright Browser
                              │
                              ▼
                         Marketplace
```

---

# Технологический стек

## Backend

* FastAPI
* SQLAlchemy 2.0 Async
* PostgreSQL
* Alembic
* Pydantic Settings

## Очереди и кеш

* RabbitMQ
* Redis (кэш последних цен, TTL 1 час)
* Celery + Celery Beat

## Telegram

* python-telegram-bot

## Парсинг

* Playwright (headless Chromium)
* BeautifulSoup4

## Инфраструктура

* Docker
* Docker Compose

## Тестирование и качество кода

* pytest
* pytest-asyncio
* respx
* Ruff (linter + formatter)
* mypy
* pre-commit

## Логирование

* structlog
* Rich traceback

---

# Структура проекта

```text
app/
├── api/              # FastAPI endpoints
├── bot/              # Telegram Bot
├── cli/              # CLI приложение (интерактивный режим)
├── core/             # Config, database, redis
├── models/           # SQLAlchemy models
├── parsers/          # Marketplace parsers
├── repositories/     # Data access layer
├── services/         # Business logic
└── workers/          # Celery tasks & beat
```

---

# Архитектурные решения

## Worker Infrastructure

### ProcessBrowser (singleton per process)
Каждый Celery worker-процесс имеет свой экземпляр браузера Playwright.
Реализован через singleton-паттерн, переиспользуется между задачами.
Закрытие происходит через `worker_max_tasks_per_child=1`.

### Database Factories
Фабрики `create_worker_engine()` и `create_worker_session_factory()`
вынесены в `app/workers/database.py` для устранения дублирования.

### PriceCache
Инкапсулирует sync/async Redis логику. Автоматически выбирает нужный клиент.
Используется в `PriceService` для работы с кэшем последних цен.

### Redis Connection Singleton
Соединения Redis (`get_redis()`, `get_redis_sync()`) создаются один раз
и переиспользуются через глобальные переменные.

## Логирование

* **structlog** — структурированные логи с контекстом
* **Rich traceback** — красивые traceback с locals (ограничены `locals_max_string=100`)
* **Truncation** — длинные строки обрезаются до 200 символов в логах
* **Single traceback** — ошибка логируется один раз на верхнем уровне задачи

---

# Быстрый старт

## Клонирование

```bash
git clone <repository-url>
cd pricepulse
```

## Настройка окружения

```bash
cp .env.example .env
```

Заполнить необходимые переменные окружения.

---

## Запуск

```bash
docker compose up -d
```

Команда запускает все сервисы:
- PostgreSQL 16
- Redis 7
- RabbitMQ 3
- FastAPI (порт 8000)
- Celery Worker
- Celery Beat
- Init-контейнер для миграций

API доступен по адресу: http://localhost:8000

Swagger UI: http://localhost:8000/docs

---

## CLI приложение

Интерактивный CLI для работы с системой без Telegram:

```bash
uv run python -m app.cli.main
```

Доступные команды:
* `start` — зарегистрироваться в системе
* `add <ссылка>` — добавить подписку на товар
* `list` — показать ваши подписки
* `price <id>` — получить текущую цену
* `delete <id>` — удалить подписку
* `help` — показать справку

---

## Миграции

Миграции применяются автоматически при запуске через init-контейнер.

Для ручного управления:

Создать миграцию:
```bash
uv run alembic revision --autogenerate -m "message"
```

Применить миграции:
```bash
docker compose exec api uv run alembic upgrade head
```

---

# API Endpoints

* `POST /api/v1/subscriptions` — создать подписку
* `GET /api/v1/subscriptions/{user_id}` — получить подписки пользователя
* `GET /api/v1/subscriptions/{subscription_id}/prices` — история цен
* `POST /api/v1/subscriptions/{subscription_id}/parse` — ручной запуск парсинга
* `GET /api/v1/subscriptions/{subscription_id}/latest-price` — последняя цена (из кэша)
* `GET /health` — проверка здоровья сервисов

---

# Разработка

Подробные правила разработки находятся в:

```text
how_we_work.md
```

Текущее состояние проекта и план работ:

```text
sprints.md
```

Архитектурные решения:

```text
architecture.md
```

---

# Roadmap

## Sprint 1 (текущий)

* ✅ Инфраструктура (Docker, PostgreSQL, Redis, RabbitMQ)
* ✅ FastAPI с REST API
* ✅ Celery Worker + Celery Beat
* ✅ Парсер Ozon (Playwright)
* ✅ Периодический мониторинг цен (каждые 15 минут)
* ✅ Кэширование в Redis
* ✅ Структурированное логирование (structlog + Rich traceback)
* ⏳ Telegram Bot
* ⏳ Уведомления о снижении цены

## Sprint 2

* Уведомления о снижении цены
* Поддержка Wildberries
* Rate limiting

## Sprint 3

* История цен с графиками
* Поддержка Яндекс.Маркет
* Масштабирование (пул браузеров, residential proxy)

---

# Статус проекта

Текущая стадия:

🚧 Активная разработка

Проект находится на этапе построения Telegram Bot и системы уведомлений.

Базовая инфраструктура, парсинг цен и логирование работают.
```

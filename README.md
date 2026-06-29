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

## Тестирование

* pytest
* pytest-asyncio
* respx

## Логирование

* structlog

---

# Структура проекта

```text
app/
├── api/              # FastAPI endpoints
├── bot/              # Telegram Bot
├── core/             # Config, database, redis
├── models/           # SQLAlchemy models
├── parsers/          # Marketplace parsers
├── repositories/     # Data access layer
├── services/         # Business logic
└── workers/          # Celery tasks & beat
```

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
* ⏳ Telegram Bot
* ⏳ Логирование и мониторинг

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

Базовая инфраструктура и парсинг цен работают.

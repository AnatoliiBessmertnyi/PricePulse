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
Telegram Bot
      ↓
    FastAPI
      ↓
    Celery
      ↓
   RabbitMQ
      ↓
    Worker
      ↓
PostgreSQL + Redis
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
* Redis
* Celery

## Telegram

* python-telegram-bot

## Парсинг

* httpx
* BeautifulSoup4
* parsel

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
├── api/
├── bot/
├── core/
├── models/
├── parsers/
├── repositories/
├── services/
└── workers/
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
```bash
uv sync
```
```bash
uv run uvicorn app.main:app --reload
```
---

## Миграции

Создать миграцию:
```bash
uv run alembic revision --autogenerate -m "message"
```

Применить миграции:
```bash
uv run alembic upgrade head
```

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

---

# Roadmap

## Sprint 1

* Инфраструктура
* PostgreSQL
* FastAPI
* Celery
* Первый парсер Ozon
* Telegram Bot

## Sprint 2

* Уведомления о снижении цены
* Поддержка Wildberries
* Redis Cache

## Sprint 3

* История цен
* Графики
* Поддержка Яндекс.Маркет

---

# Статус проекта

Текущая стадия:

🚧 Активная разработка

Проект находится на этапе построения базовой инфраструктуры.

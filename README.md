# PricePulse

PricePulse — сервис мониторинга цен на маркетплейсах с уведомлениями в Telegram.

Пользователь добавляет ссылку на товар через Telegram-бота. Система периодически проверяет цену, сохраняет историю изменений и уведомляет пользователя при достижении целевой цены.

---

# Возможности

Текущий функционал:

* ✅ Мониторинг цен на Ozon
* ✅ Уведомления в Telegram при достижении целевой цены
* ✅ История изменения цен
* ✅ Несколько подписок на пользователя
* ✅ Умная логика уведомлений (buffer 5%, cooldown 24 часа)
* ✅ Inline keyboard навигация
* ✅ Единый виджет UX (без спама сообщениями)

Планируемый функционал:

* Мониторинг цен на Wildberries
* Мониторинг цен на Яндекс.Маркет
* Графики изменения стоимости
* Настройка cooldown_hours для каждой подписки
* Rate limiting (защита от блокировок)

---

# Архитектура

```text
                Telegram
                    │
                    ▼
           Telegram Bot ──────► Cloudflare Worker (прокси)
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
                    ┌─────────┴─────────┐
                    │                   │
                    ▼                   ▼
           Playwright Browser    NotificationService
                    │                   │
                    ▼                   ▼
              Marketplace         Telegram API
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
* Cloudflare Worker (прокси для обхода блокировок в РФ)

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
├── bot/              # Telegram Bot (handlers, keyboards, utils)
├── cli/              # CLI приложение (интерактивный режим)
├── core/             # Config, database, redis, constants, logging
├── models/           # SQLAlchemy models
├── parsers/          # Marketplace parsers
├── repositories/     # Data access layer
├── services/         # Business logic (включая NotificationService)
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

## Telegram Bot

### Единый виджет UX
Все действия происходят в одном редактируемом сообщении без спама новыми сообщениями.
Сохранение `request_message_id` в `context.user_data` для последующего редактирования.

### Inline Keyboard Navigation
Интерактивная навигация через inline keyboard с пагинацией и кэшированием в `context.user_data`.

### ConversationHandler
Интерактивные диалоги для добавления подписки и установки target_price.
Поддержка нескольких entry_points для одного диалога.

### Graceful Error Handling
Обработка устаревших callback (Query is too old) и сетевых ошибок от Cloudflare прокси.
Виджет не ломается при временных проблемах.

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

Заполнить необходимые переменные окружения:
- `TELEGRAM_BOT_TOKEN` — токен Telegram бота
- `TELEGRAM_API_URL` — URL Cloudflare Worker прокси (опционально)

---

## Запуск

```bash
docker compose --profile bot up -d
```

Команда запускает все сервисы:
- PostgreSQL 16
- Redis 7
- RabbitMQ 3
- FastAPI (порт 8000)
- Celery Worker
- Celery Beat
- Telegram Bot (profile `bot`)
- Init-контейнер для миграций

API доступен по адресу: http://localhost:8000

Swagger UI: http://localhost:8000/docs

Без Telegram бота:
```bash
docker compose up -d
```

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
docker compose run --rm migrate alembic revision --autogenerate -m "message"
```

Применить миграции:
```bash
docker compose run --rm migrate alembic upgrade head
```

---

# API Endpoints

* `POST /api/v1/users` — регистрация пользователя
* `POST /api/v1/subscriptions` — создать подписку
* `GET /api/v1/subscriptions/{user_id}` — получить подписки пользователя
* `GET /api/v1/subscriptions/{subscription_id}/prices` — история цен
* `POST /api/v1/subscriptions/{subscription_id}/parse` — ручной запуск парсинга
* `GET /api/v1/subscriptions/{subscription_id}/latest-price` — последняя цена (из кэша)
* `PATCH /api/v1/subscriptions/{subscription_id}/target-price` — обновить целевую цену
* `DELETE /api/v1/subscriptions/{subscription_id}` — удалить подписку
* `GET /health` — проверка здоровья сервисов

---

# Telegram Bot

## Команды

* `/start` — стартовое сообщение
* `/list` — список подписок
* `/add` — добавить подписку
* `/help` — справка

## Навигация

Вместо текстовых команд используется inline keyboard навигация:

- **Главное меню:** Мои подписки, Добавить подписку, Удалить подписку, Помощь
- **Список подписок:** пагинация, кнопка "🎯 Установить цену", "🔄 Обновить", "◀️ Назад в меню"
- **Добавление подписки:** ConversationHandler с ожиданием URL
- **Удаление подписки:** двухэтапное (выбор → подтверждение)

## Установка целевой цены

1. В списке подписок нажать "🎯 Установить цену"
2. Выбрать подписку из списка
3. Ввести целевую цену
4. Получить уведомление когда цена опустится ниже цели

После добавления подписки бот сразу предлагает установить целевую цену.

## Умные уведомления

- **Buffer (5%):** Автоматический сброс уведомления когда цена поднимается выше `target_price * 1.05`
- **Cooldown (24 часа):** Минимальный период между повторными уведомлениями
- **Визуальный статус:** ⏳ Мониторинг / 🔔 Цена достигла цели / ✅ Уведомление отправлено

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

## Sprint 1 ✅

* ✅ Инфраструктура (Docker, PostgreSQL, Redis, RabbitMQ)
* ✅ FastAPI с REST API
* ✅ Celery Worker + Celery Beat
* ✅ Парсер Ozon (Playwright)
* ✅ Периодический мониторинг цен (каждые 15 минут)
* ✅ Кэширование в Redis
* ✅ Структурированное логирование (structlog + Rich traceback)
* ✅ CLI клиент для тестирования

## Sprint 2 ✅

* ✅ Telegram Bot с inline keyboard навигацией
* ✅ Система умных уведомлений о достижении целевой цены
* ✅ Единый виджет UX (редактирование сообщений)
* ✅ Graceful error handling для Telegram API ошибок
* ✅ Cloudflare Worker прокси для обхода блокировок
* ✅ Предложение установить target_price после добавления подписки

## Sprint 3 (планируется)

* Redis кэширование на уровне API
* Настройка cooldown_hours для каждой подписки
* Покупка стабильного прокси для Telegram API
* Обработка мёртвых подписок
* Графики изменения цен
* Rate limiting (защита от блокировок)

## Sprint 4 (планируется)

* Поддержка Wildberries
* Поддержка Яндекс.Маркет
* Масштабирование (пул браузеров, residential proxy)
* Prometheus + Grafana
* CI/CD

---

# Статус проекта

Текущая стадия:

🚀 Sprint 2 завершён. Активная разработка.

Telegram бот работает с inline keyboard навигацией, системой умных уведомлений и единым виджетом UX. Базовая инфраструктура, парсинг цен и логирование работают стабильно.

---

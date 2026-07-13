# PricePulse

PricePulse — высокопроизводительный сервис мониторинга цен на маркетплейсах с умными уведомлениями в Telegram.

Пользователь добавляет ссылку на товар через Telegram-бота или CLI. Система периодически проверяет цену, сохраняет историю изменений и уведомляет пользователя при достижении целевой цены.

---

# Возможности

Текущий функционал:

* ✅ Мониторинг цен на Ozon
* ⚡️ **Молниеносный парсинг:** 2-4 секунды на товар (оптимизация через Regex вместо тяжелого DOM-парсинга)
* 🚀 **Redis кэширование API:** Мгновенные ответы бота, снижение нагрузки на БД на 50-70%
* 🕒 **Самовосстанавливающееся расписание:** Проверки работают строго по интервалу без дрейфа таймера (timer drift)
* ✅ Умные уведомления (buffer 5%, cooldown 24 часа)
* ✅ Inline keyboard навигация
* ✅ Единый виджет UX (без спама сообщениями, редактирование на месте)
* ✅ Чистые, структурированные логи без технического шума

Планируемый функционал:

* Мониторинг цен на Wildberries и Яндекс.Маркет
* Графики изменения стоимости
* Настройка `cooldown_hours` для каждой подписки
* Обработка "мёртвых" подписок (автоматическая деактивация удаленных товаров)

---

# Архитектура

```text
                Telegram / CLI
                    │
                    ▼
           Telegram Bot ──────► Cloudflare Worker (прокси)
                    │
                    ▼
                FastAPI ──────────► Redis (API кэш + кэш цен)
                    │
          ┌─────────┴─────────┐
          │                   │
          ▼                   ▼
     PostgreSQL           RabbitMQ
                              │
                              ▼
                        Celery Beat
                        (тик каждую минуту)
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

## Очереди и кэш
* RabbitMQ
* Redis (кэш API и последних цен)
* Celery + Celery Beat

## Telegram
* python-telegram-bot
* Cloudflare Worker (прокси для обхода блокировок в РФ)

## Парсинг
* Playwright (headless Chromium)
* **Regex + `html.unescape`** (оптимизированное извлечение данных, отказ от тяжелого BeautifulSoup)

## Инфраструктура
* Docker
* Docker Compose

## Тестирование и качество кода
* pytest, pytest-asyncio, respx
* Ruff (linter + formatter)
* mypy
* pre-commit

## Логирование
* structlog
* Rich traceback (с ограничением длины строк и переменных)

---

# Структура проекта

```text
app/
├── api/              # FastAPI endpoints и middleware
├── bot/              # Telegram Bot (handlers, keyboards, utils)
├── cli/              # CLI приложение (интерактивный режим)
├── core/             # Config, database, redis, cache, constants, logging
├── models/           # SQLAlchemy models
├── parsers/          # Marketplace parsers (Ozon)
├── repositories/     # Data access layer
├── services/         # Business logic (включая NotificationService)
└── workers/          # Celery tasks, beat schedule & browser manager
```

---

# Ключевые архитектурные решения

## Performance & Reliability
* **API Caching:** `CacheService` кэширует ответы `GET /subscriptions` (TTL 30s) и истории цен (TTL 60s) с автоматической инвалидацией при любых мутациях данных.
* **Parser Optimization:** Прямое извлечение JSON из `<script type="application/ld+json">` и атрибутов `data-state` через регулярные выражения. Fallback на meta-теги при изменениях верстки.
* **Self-Healing Scheduler:** Celery Beat тикает каждую минуту, но реальный интервал контролируется БД. Время `last_check_at` фиксируется в момент *начала* цикла, что полностью устраняет дрейф таймера и позволяет системе автоматически компенсировать временные сбои.
* **Clean Worker Logs:** Кастомный `CeleryTaskNoiseFilter` подавляет избыточные сообщения Celery (`received`, `succeeded`), оставляя только структурные бизнес-события.

## Worker Infrastructure
* **ProcessBrowser (singleton per process):** Каждый Celery worker-процесс имеет свой экземпляр браузера Playwright, переиспользуемый между задачами.
* **Database Factories:** Фабрики `create_worker_engine()` устраняют конфликты event loop в синхронных задачах Celery.

## Telegram Bot UX
* **Единый виджет:** Все действия происходят в одном редактируемом сообщении.
* **Graceful Error Handling:** Игнорирование устаревших callback и сетевых ошибок, чтобы виджет не ломался при временных проблемах прокси.

---

# Быстрый старт

## Клонирование и настройка

```bash
git clone <repository-url>
cd pricepulse
cp .env.example .env
```
Заполни `.env`, указав `TELEGRAM_BOT_TOKEN` и (опционально) `TELEGRAM_API_URL` для Cloudflare прокси.

## Запуск

```bash
# Со всеми сервисами, включая Telegram бота
docker compose --profile bot up -d --build

# Только базовая инфраструктура и API (без бота)
docker compose up -d --build
```

API доступен по адресу: http://localhost:8000  
Swagger UI: http://localhost:8000/docs

## CLI приложение (для тестов без Telegram)

```bash
uv run python -m app.cli.main
```
Доступные команды: `start`, `add <ссылка>`, `list`, `price <id>`, `delete <id>`, `help`.

## Управление миграциями

Миграции применяются автоматически при старте. Для ручного управления:
```bash
docker compose run --rm migrate alembic revision --autogenerate -m "message"
docker compose run --rm migrate alembic upgrade head
```

---

# API Endpoints

* `POST /api/v1/users` — регистрация пользователя
* `POST /api/v1/subscriptions` — создать подписку
* `GET /api/v1/subscriptions/{user_id}` — получить подписки пользователя *(кэшируется)*
* `GET /api/v1/subscriptions/{subscription_id}/prices` — история цен *(кэшируется)*
* `POST /api/v1/subscriptions/{subscription_id}/parse` — ручной запуск парсинга
* `GET /api/v1/subscriptions/{subscription_id}/latest-price` — последняя цена
* `PATCH /api/v1/subscriptions/{subscription_id}/target-price` — обновить целевую цену
* `DELETE /api/v1/subscriptions/{subscription_id}` — удалить подписку
* `GET /health` — проверка здоровья сервисов

---

# Разработка

Подробные правила разработки: `how_we_work.md`  
Текущее состояние и план работ: `sprints.md`  
Детальные архитектурные решения: `architecture.md`

---

# Roadmap

## Sprint 1 ✅ (Фундамент)
* Инфраструктура (Docker, PostgreSQL, Redis, RabbitMQ)
* FastAPI REST API + Celery Worker/Beat
* Парсер Ozon (Playwright)
* Периодический мониторинг цен
* Структурированное логирование + CLI клиент

## Sprint 2 ✅ (Telegram UX)
* Telegram Bot с inline keyboard навигацией
* Система умных уведомлений (buffer, cooldown)
* Единый виджет UX (редактирование сообщений)
* Graceful error handling + Cloudflare прокси

## Sprint 3 ✅ (Производительность и стабильность)
* ⚡️ Оптимизация парсинга Ozon (40с → 2-4с)
* 🚀 Redis кэширование на уровне API с авто-инвалидацией
* 🕒 Устранение дрейфа таймера (Self-healing scheduler)
* 🔇 Очистка логов воркера от технического шума

## Sprint 4 (Планируется)
* Поддержка Wildberries и Яндекс.Маркет
* Обработка "мёртвых" подписок (авто-деактивация)
* Настройка `cooldown_hours` пользователем
* Prometheus + Grafana мониторинг
* CI/CD пайплайн (self-hosted runner)

---

# Статус проекта

🚀 **Sprint 3 завершен.** 

Система оптимизирована, стабильна и готова к нагрузке. Парсинг работает молниеносно, API отвечает мгновенно благодаря кэшу, а планировщик гарантирует точность проверок без дрейфа. Активная разработка новых фич продолжается.

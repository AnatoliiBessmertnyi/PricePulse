# PricePulse

PricePulse — высокопроизводительный сервис мониторинга цен на маркетплейсах с умными уведомлениями в Telegram.

Пользователь добавляет ссылку на товар через Telegram-бота или CLI. Система периодически проверяет цену, сохраняет историю изменений и уведомляет пользователя при достижении целевой цены.

---

# Возможности

Текущий функционал:

* ✅ Мониторинг цен на Ozon
* ⚡️ **Молниеносный парсинг:** 2-4 секунды на товар (оптимизация через Regex вместо тяжелого DOM-парсинга)
* 🚀 **Redis кэширование API:** Мгновенные ответы, снижение нагрузки на БД на 50-70%
* 🕒 **Умное планирование (Smart Scheduling):** Проверки работают строго по интервалу через `eta` без Celery Beat, что полностью устраняет дрейф таймера и лишние SELECT-запросы к БД.
* 🛡️ **Надежность:** Retry-политики при сетевых сбоях и Dead Letter Exchange (DLX) в RabbitMQ для обработки потерянных задач.
* 🧹 **Автоматическая очистка:** Фоновая задача удаляет историю цен старше 90 дней для архивных подписок, предотвращая разрастание БД.
* ✅ **Умные уведомления:** Настраиваемый пользователем cooldown (от 1 до 168 часов), автоматический сброс при росте цены.
* ✅ **Графики изменения цен:** Визуализация истории (Matplotlib), кэширование в Redis, защита от OOM через агрегацию `DATE_TRUNC`.
* ✅ **Обработка "мёртвых" подписок:** Автоматическая архивация после 3 ошибок с возможностью реактивации.
* ✅ Inline keyboard навигация и единый виджет UX (без спама сообщениями).
* ✅ Чистые, структурированные логи без технического шума.

Планируемый функционал:

* Мониторинг цен на Wildberries и Яндекс.Маркет.
* Actionable Notifications (кнопки действий прямо в сообщении об изменении цены).
* Глобальный UX Polish (устранение всех возможных тупиков при сетевых ошибках).
* Покрытие кода Unit и Integration тестами (70%+).

---

# Архитектура

```text
                Telegram / CLI Client
                    │
                    ▼
           Telegram Bot / CLI ──────► Cloudflare Worker (прокси)
                    │                         │
                    ▼                         ▼
                FastAPI ──────────► Redis (API кэш, кэш цен, кэш графиков Base64)
                    │ (Единый Service Layer)
          ┌─────────┴─────────┐
          │                   │
          ▼                   ▼
     PostgreSQL           RabbitMQ (с поддержкой DLX)
                              │
                              ▼
                       Celery Worker 
                  (Smart Scheduling via eta)
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
* Celery (без Beat, умное планирование через `eta`)

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
├── services/         # Business logic (включая NotificationService и кэширование)
└── workers/          # Celery tasks, queue resync & browser manager
```

---

# Ключевые архитектурные решения

## Performance & Reliability
* **API Caching:** `CacheService` кэширует ответы `GET /subscriptions` (TTL 30s) и истории цен (TTL 60s) с автоматической инвалидацией при любых мутациях данных.
* **Parser Optimization:** Прямое извлечение JSON из `<script type="application/ld+json">` и атрибутов `data-state` через регулярные выражения. Fallback на meta-теги при изменениях верстки.
* **Smart Scheduling (eta):** Отказ от периодического опроса БД через Celery Beat ("тупой метроном"). После успешного выполнения задачи парсинга, она самостоятельно планирует свое следующее выполнение через параметр `eta`, что полностью устраняет нагрузку на БД от частых SELECT-запросов и дрейф таймера.
* **Dead Letter Exchange (DLX):** Настройка RabbitMQ для перехвата задач, исчерпавших попытки retry, с возможностью ручного разбора и предотвращения потери данных.
* **Clean Worker Logs:** Кастомный `CeleryTaskNoiseFilter` подавляет избыточные сообщения Celery (`received`, `succeeded`), оставляя только структурные бизнес-события.

## Worker Infrastructure
* **ProcessBrowser (singleton per process):** Каждый Celery worker-процесс имеет свой экземпляр браузера Playwright, переиспользуемый между задачами.
* **Database Factories:** Фабрики `create_worker_engine()` устраняют конфликты event loop в синхронных задачах Celery.
* **Автоматическая очистка истории:** Саморегистрирующаяся фоновая задача удаляет записи `PriceHistory` старше 90 дней для архивных подписок, предотвращая разрастание БД.

## Telegram Bot UX
* **Единый виджет:** Все действия происходят в одном редактируемом сообщении.
* **Graceful Error Handling:** Игнорирование устаревших callback и сетевых ошибок, чтобы виджет не ломался при временных проблемах прокси.

## Charts & Resilience
* **PriceChartService:** Генерация графиков через `matplotlib` в отдельном потоке (`asyncio.to_thread`). Графики кэшируются в Redis как Base64-строки для совместимости с `decode_responses=True`.
* **Delegated Photo Sending:** Из-за ограничений Cloudflare Worker при обработке `multipart/form-data` (обрывы соединения), бот не отправляет фото напрямую. Вместо этого он вызывает `POST /api/v1/subscriptions/{id}/chart/send`, и FastAPI самостоятельно отправляет фото через изолированный `httpx.AsyncClient`, что гарантирует 100% надежность доставки.
* **No Dead Ends UX:** При любых сетевых сбоях бот не оставляет пользователя без кнопок. Отображается понятное сообщение с названием товара и кнопками "🔄 Повторить попытку" / "◀️ Назад к выбору".

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
* `GET /api/v1/subscriptions/{user_id}/archived` — получить архивные подписки пользователя
* `GET /api/v1/subscriptions/{subscription_id}/prices` — история цен *(кэшируется, с агрегацией DATE_TRUNC)*
* `GET /api/v1/subscriptions/{subscription_id}/chart` — получить PNG графика *(кэшируется)*
* `POST /api/v1/subscriptions/{subscription_id}/chart/send` — внутренний эндпоинт для отправки графика в Telegram
* `POST /api/v1/subscriptions/{subscription_id}/parse` — ручной запуск парсинга
* `GET /api/v1/subscriptions/{subscription_id}/latest-price` — последняя цена
* `PATCH /api/v1/subscriptions/{subscription_id}/target-price` — обновить целевую цену
* `PATCH /api/v1/subscriptions/{subscription_id}/cooldown` — обновить интервал уведомлений (1-168 ч)
* `POST /api/v1/subscriptions/{subscription_id}/reactivate` — реактивировать архивную подписку
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
* FastAPI REST API + Celery Worker
* Парсер Ozon (Playwright)
* Периодический мониторинг цен
* Структурированное логирование + CLI клиент

## Sprint 2 ✅ (Telegram UX)
* Telegram Bot с inline keyboard навигацией
* Система умных уведомлений (buffer, базовый cooldown)
* Единый виджет UX (редактирование сообщений)
* Graceful error handling + Cloudflare прокси

## Sprint 3 ✅ (Производительность, стабильность и новые фичи)
* ⚡️ Оптимизация парсинга Ozon (40с → 2-4с)
* 🚀 Redis кэширование на уровне API с авто-инвалидацией
* 🕒 Устранение дрейфа таймера (Self-healing scheduler)
* 🔇 Очистка логов воркера от технического шума
* 🗄 Архивация "мёртвых" подписок после 3 ошибок
* ⏱ Настраиваемый пользователем cooldown (1-168 часов)
* 📊 Графики изменения цен (Matplotlib, кэш Base64, делегирование отправки на API)

## Sprint 3C ✅ (Технический долг и стабилизация стека)
* 🔄 Синхронизация API и Bot (DRY): сохранение полноценного REST API при использовании единого Service Layer
* 📉 Downsampling истории цен через `DATE_TRUNC` (защита от OOM при построении графиков)
* ⏱️ Переход на умное планирование Celery (`eta` вместо Beat-метронома)
* 🛡️ Внедрение Retry-политик для задач парсинга и Dead Letter Exchange (DLX) в RabbitMQ
* 🧹 Удаление мертвого кода и фоновая очистка старой истории цен

## Sprint 4 🚧 (Планируется)
* **UX Polish & Resilience:** Глобальный аудит и устранение всех UX-тупиков при ошибках сети
* **Actionable Notifications:** Кнопки действий (Отложить, Изменить цель, Архив) прямо в сообщении алерта
* **Testing:** Покрытие Unit и Integration тестами критичных сервисов (70%+)
* **Масштабирование:** Поддержка Wildberries, оптимизация SQL (N+1, индексы)
* **Инфраструктура:** Prometheus + Grafana, CI/CD (self-hosted runner)

---

# Статус проекта

✅ **Sprint 3C завершен.** 

Архитектура прошла критическое ревью и стабилизирована. Система оптимизирована: сохранен полноценный REST API (API-First), внедрено умное планирование задач (`eta`), добавлена защита от OOM при построении графиков (`DATE_TRUNC`), настроены retry-политики и DLX. Проект полностью готов к масштабированию и переходу к Sprint 4.

# Architecture

## Назначение документа

Документ описывает архитектурные решения проекта PricePulse.

Цель документа:

* зафиксировать структуру системы;
* объяснить принятые решения;
* снизить количество повторных обсуждений;
* упростить дальнейшее развитие проекта.

---

# Обзор системы

PricePulse — сервис мониторинга цен на маркетплейсах с уведомлениями через Telegram.

Пользователь добавляет ссылку на товар через Telegram бота или CLI клиент.

Система:

1. Сохраняет подписку.
2. Периодически проверяет цену (интервал настраивается через `PRICE_CHECK_INTERVAL`, по умолчанию 15 минут).
3. Сохраняет историю изменений.
4. Кэширует последнюю цену в Redis (TTL 1 час).
5. **Отправляет уведомления при достижении целевой цены (target_price)** с умной логикой:
   - Автоматический сброс при росте цены выше `target_price + 5%`
   - Cooldown период (24 часа по умолчанию) между уведомлениями
   - Визуальный статус в интерфейсе (⏳ Мониторинг / 🔔 Цена достигла цели / ✅ Уведомление отправлено)

---

# Высокоуровневая архитектура

```text
          Telegram / CLI Client
                    │
                    ▼
           Telegram Bot / CLI ──────► Cloudflare Worker (прокси)
                    │                         │
                    ▼                         ▼
                FastAPI ──────────► Redis (кэш)
                    │
          ┌─────────┴─────────┐
          │                   │
          ▼                   ▼
     PostgreSQL           RabbitMQ
                              │
                              ▼
                        Celery Beat
                        (настраиваемый интервал)
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

# Основные компоненты

## FastAPI

Ответственность:

* REST API
* валидация данных
* работа с подписками
* регистрация пользователей
* удаление подписок
* обновление target_price
* структурированное логирование HTTP запросов через middleware

FastAPI не занимается парсингом и не отправляет уведомления напрямую.

### Database Connection

FastAPI использует `@lru_cache` для создания singleton engine и session factory:

```python
from functools import lru_cache

@lru_cache
def get_engine():
    return create_async_engine(
        settings.postgres_url,
        echo=settings.log_level == "DEBUG",
        pool_pre_ping=True,
    )

@lru_cache
def get_session_factory():
    return async_sessionmaker(
        bind=get_engine(),
        class_=AsyncSession,
        expire_on_commit=False,
    )

async def get_db() -> AsyncIterator[AsyncSession]:
    async with get_session_factory()() as session:
        yield session
```

Преимущества **@lru_cache** перед глобальными переменными:
- Потокобезопасность из коробки
- Автоматический singleton без ручного управления состоянием
- Чище код без глобальных переменных **_engine** и **_async_session_factory**
- Ленивая инициализация при первом вызове

Отличие от Celery Worker:

- FastAPI использует **@lru_cache** (один engine на всё приложение)
- Celery Worker создаёт собственный engine для каждой задачи (через **create_worker_engine()**)

Это связано с тем, что Celery использует **asyncio.run()** внутри синхронных задач, создавая новый event loop для каждой задачи, что приводит к конфликтам с глобальным engine.

---

## PostgreSQL

Источник истины (Source of Truth).

Хранит:

* пользователей
* подписки (включая `last_check_at`, `last_success_at`, `target_price`, `alert_sent`, `last_alert_at`, `cooldown_hours`)
* историю цен
* ошибки парсинга

Никакие данные не должны существовать только в Redis.

---

## Redis

Используется исключительно как вспомогательное хранилище.

Назначение:

* кеширование последних цен (TTL 1 час)
* rate limiting (будет добавлено)
* временные данные

Redis может быть очищен без потери данных.

### Структура кэша

```text
price:latest:{subscription_id} → "3009"
```

Ключ содержит ID подписки, значение — последнюю цену в виде строки.

### Клиенты и PriceCache

FastAPI использует `redis.asyncio.Redis` (асинхронный клиент), Celery Worker использует `redis.Redis` (синхронный клиент).

Оба клиента работают с одним Redis-сервером. Разделение обусловлено тем, что Celery задачи выполняются в синхронном контексте и не должны зависеть от event loop FastAPI.

**Singleton соединения:** Функции `get_redis()` и `get_redis_sync()` создают соединение один раз и переиспользуют его через глобальные переменные `_async_redis` и `_sync_redis`. Это устраняет накладные расходы на создание нового соединения при каждом вызове.

**PriceCache:** Класс `PriceCache` инкапсулирует sync/async Redis логику. Автоматически выбирает нужный клиент в зависимости от контекста. Используется в `PriceService` для работы с кэшем последних цен.

```python
class PriceCache:
    def __init__(self, redis_sync=None, redis_async=None):
        self._redis_sync = redis_sync
        self._redis_async = redis_async
    
    async def set(self, key, value, ttl):
        if self._redis_sync:
            self._redis_sync.setex(key, ttl, value)
        elif self._redis_async:
            await self._redis_async.setex(key, ttl, value)
    
    async def get(self, key):
        if self._redis_async:
            return await self._redis_async.get(key)
        if self._redis_sync:
            return self._redis_sync.get(key)
        return None
```

---

## RabbitMQ

Основной брокер сообщений.

Используется для:

* запуска парсинга
* уведомлений
* фоновых задач

---

## Celery Beat

Планировщик периодических задач.

Запускает задачу `check_all_subscriptions` с настраиваемым интервалом (по умолчанию 15 минут, минимум 60 секунд).

Интервал задаётся через переменную окружения `PRICE_CHECK_INTERVAL` в секундах.

Задача:

1. Получает все активные подписки из PostgreSQL
2. Для каждой подписки ставит задачу `parse_price` в очередь
3. **Атомарно обновляет `last_check_at`** — только для успешно созданных задач

### Атомарность операций

Задача `check_all_subscriptions` гарантирует атомарность обновления `last_check_at`:

```python
# Сначала собираем ID успешно созданных задач
successful_ids: list[int] = []
for subscription in subscriptions:
    try:
        parse_price.delay(subscription.id)
        successful_ids.append(subscription.id)
    except Exception as e:
        logger.error("failed_to_create_task", subscription_id=subscription.id, error=str(e))

# Потом обновляем last_check_at только для успешных
for sub_id in successful_ids:
    await repo.mark_last_check_now(sub_id)

await session.commit()
```

Это предотвращает рассинхронизацию: если **parse_price.delay()** упадёт после нескольких итераций, часть подписок не будет обновлена, что соответствует реальному состоянию (задачи не созданы).

### Database Factories

Каждая задача создаёт собственный async SQLAlchemy engine через фабрики `create_worker_engine()` и `create_worker_session_factory()` из `app/workers/database.py`. Это необходимо для избежания конфликтов event loop, так как Celery использует `asyncio.run()` внутри синхронных задач, а глобальный engine привязан к event loop, созданному при импорте модуля.

```python
# app/workers/database.py
def create_worker_engine():
    return create_async_engine(
        settings.postgres_url,
        echo=False,
        pool_pre_ping=True,
    )

def create_worker_session_factory(engine):
    return async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
```

Использование:

```python
async def _check_all_subscriptions() -> None:
    engine = create_worker_engine()
    async_session_factory = create_worker_session_factory(engine)
    
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

---

## Celery Worker

### ProcessBrowser (singleton per process)

Воркер использует **Playwright** (headless Chromium) для парсинга маркетплейсов.

Playwright необходим для обхода продвинутой защиты Ozon:

* JavaScript challenges
* TLS fingerprinting (JA3/JA4)
* Блокировки по User-Agent и fingerprint
* Бесконечные 307 редиректы при использовании обычных HTTP-клиентов

Альтернативы, которые были отброшены:

* `httpx` — блокируется Ozon (403 Forbidden)
* `curl_cffi` с impersonate — блокируется Ozon (403 Forbidden)

**ProcessBrowser singleton:** Каждый Celery worker-процесс имеет свой экземпляр браузера Playwright. Реализован через singleton-паттерн в классе `ProcessBrowser`. Браузер создаётся при первом вызове `get_page()` и переиспользуется между задачами. Закрытие происходит через `worker_max_tasks_per_child=1`.

```python
class ProcessBrowser:
    _instance: "ProcessBrowser | None" = None
    
    def __new__(cls) -> "ProcessBrowser":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    async def get_page(self) -> Page:
        if self._page is not None:
            return self._page
        
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-setuid-sandbox"],
        )
        self._context = await self._browser.new_context(...)
        self._page = await self._context.new_page()
        return self._page
    
    async def close(self) -> None:
        # Закрытие page, context, browser, playwright
        ...

def get_process_browser() -> ProcessBrowser:
    return ProcessBrowser()
```

Конфигурация запуска:

```python
_browser = await _playwright.chromium.launch(
    headless=True,
    args=["--no-sandbox", "--disable-setuid-sandbox"],
)
```

Флаги **--no-sandbox** и **--disable-setuid-sandbox** обязательны для запуска Chromium в Docker-контейнере от root.

### Производительность

- Парсинг одной подписки занимает ~40 секунд (headless Chromium + тяжёлая страница Ozon)
- При интервале 15 минут один воркер успевает обработать ~20 подписок за цикл
- Для масштабирования до 2000 подписок потребуется пул из 5-10 браузеров (отложено)

### Интеграция с NotificationService

После успешного парсинга цены задача `parse_price` проверяет, нужно ли отправить уведомление:

```python
async def _parse_price(subscription_id: int) -> None:
    # ... парсинг цены ...
    
    subscription = await repo.get(subscription_id)
    if subscription and subscription.current_price and subscription.target_price:
        subscription_service = SubscriptionService(repo)
        notification_service = NotificationService(subscription_service)
        
        if notification_service.should_send_alert(subscription, subscription.current_price):
            notification_service.notify_price_drop(subscription)
            await subscription_service.mark_alert_sent(subscription_id)
```

Это обеспечивает:
- Уведомления отправляются только после получения актуальной цены
- Логика уведомлений инкапсулирована в NotificationService
- Worker отвечает за оркестрацию, а не за бизнес-логику

---

## Telegram Bot

Основной интерфейс пользователя.

Бот реализует **единый виджет UX** — все взаимодействия происходят в одном редактируемом сообщении, без спама новыми сообщениями в чате.

### Inline Keyboard Navigation

Вместо текстовых команд используется интерактивная навигация через inline keyboard:

- **Главное меню:** Мои подписки, Добавить подписку, Удалить подписку, Помощь
- **Список подписок:** пагинация, кнопка "🎯 Установить цену", "🔄 Обновить", "◀️ Назад в меню"
- **Добавление подписки:** ConversationHandler с ожиданием URL
- **Удаление подписки:** двухэтапное (выбор → подтверждение)

### Единый виджет UX

Все действия происходят в одном "виджете" (сообщении):

```python
# Сохраняем ID сообщения для последующего редактирования
context.user_data["add_request_message_id"] = update.callback_query.message.message_id

# После обработки — редактируем то же сообщение
await context.bot.edit_message_text(
    chat_id=chat_id,
    message_id=request_message_id,
    text=success_message,
    reply_markup=get_subscription_created_keyboard(subscription_id),
)
```

Это обеспечивает:
- Чистый чат без спама сообщениями
- Пользователь не теряет контекст при навигации
- Плавный UX с редактированием вместо создания новых сообщений

### ConversationHandler

Интерактивные диалоги реализованы через `ConversationHandler`:

```python
set_target_conversation_handler = ConversationHandler(
    entry_points=[
        CallbackQueryHandler(set_target_command, pattern=r"^set_target_select_\d+$"),
        CallbackQueryHandler(set_target_command, pattern=r"^set_target_new_\d+$"),
    ],
    states={
        WAITING_FOR_TARGET_PRICE: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, handle_target_price)
        ],
    },
    fallbacks=[
        CallbackQueryHandler(cancel_set_target, pattern=r"^cancel_target$"),
    ],
    name="set_target_conversation",
    persistent=False,
)
```

Это позволяет:
- Управлять состоянием диалога (ожидание URL, ожидание цены)
- Обрабатывать отмену через fallback
- Поддерживать несколько entry_points для одного диалога

### Кэширование в context.user_data

Для оптимизации производительности используется кэширование в `context.user_data`:

```python
# Кэш подписок для пагинации
context.user_data["cached_subscriptions"] = subscriptions

# Кэш user_id для избежания повторных API запросов
context.user_data["user_id"] = user_id

# ID сообщения для редактирования
context.user_data["add_request_message_id"] = message_id
```

Инвалидация кэша происходит при добавлении/удалении подписки.

### Cloudflare Worker прокси

Для обхода блокировок Telegram API в РФ используется Cloudflare Worker:

```python
if bot_settings.telegram_api_url:
    api_url = bot_settings.telegram_api_url.rstrip("/")
    bot = Bot(
        token=bot_settings.telegram_bot_token,
        base_url=api_url + "/bot{token}",
        base_file_url=api_url + "/file/bot{token}",
        request=request,
    )
```

Worker проксирует запросы к `api.telegram.org` и обходит блокировки.

### Graceful Error Handling

Бот обрабатывает ошибки Telegram API для предотвращения каскадных ошибок:

```python
# Утилиты для определения типа ошибки
def is_stale_callback_error(error: Exception) -> bool:
    error_msg = str(error).lower()
    return any(
        phrase in error_msg
        for phrase in [
            "query is too old",
            "message is not modified",
            "query id is invalid",
            "response timeout expired",
        ]
    )

# При ошибке виджет НЕ ломается
except Exception as e:
    if is_stale_callback_error(e):
        return  # Игнорируем устаревшие callback
    
    # Показываем ошибку через "всплывашку"
    await query.answer("⚠️ Произошла ошибка. Попробуйте ещё раз.", show_alert=True)
```

Это обеспечивает:
- Виджет не ломается при временных проблемах
- Пользователь видит понятные сообщения об ошибках
- Чистые логи без спама HTML от Cloudflare

### Опциональный сервис

Запускается через Docker Compose profile `bot`.

---

## NotificationService

Сервис умных уведомлений о достижении целевой цены.

### Логика уведомлений

```python
class NotificationService:
    def should_send_alert(self, subscription: Subscription, current_price: Decimal) -> bool:
        # 1. Цена должна быть ниже target_price
        if subscription.target_price is None or current_price > subscription.target_price:
            return False
        
        # 2. Проверяем что уведомление ещё не отправлено
        if subscription.alert_sent:
            # Автоматический сброс если цена поднялась выше threshold (+5%)
            threshold = subscription.target_price * Decimal(str(1 + ALERT_RESET_BUFFER))
            if current_price > threshold:
                subscription.alert_sent = False
            else:
                return False
        
        # 3. Проверяем cooldown
        if subscription.last_alert_at:
            hours_since_last = (now - subscription.last_alert_at).total_seconds() / 3600
            if hours_since_last < subscription.cooldown_hours:
                return False
        
        return True
```

### Buffer и Cooldown

- **Buffer (5%):** Автоматический сброс `alert_sent` когда цена поднимается выше `target_price * 1.05`
- **Cooldown (24 часа):** Минимальный период между повторными уведомлениями

Это предотвращает спам уведомлениями при колебаниях цены вокруг target_price.

### Отправка уведомлений

```python
def notify_price_drop(self, subscription: Subscription) -> None:
    text = (
        f"🔔 Цена снизилась!\n\n"
        f"📦 {subscription.product_name or 'Товар'}\n"
        f"💰 Новая цена: {subscription.current_price} ₽\n"
        f"🎯 Ваша цель: {subscription.target_price} ₽\n\n"
        f"🔗 {subscription.product_url}"
    )
    # Отправка через Telegram API
```

---

## CLI Client

Временный интерфейс для тестирования без необходимости настройки VPN/прокси для Telegram.

Реализован как REPL-приложение с командами:

* `start` — регистрация пользователя
* `add <ссылка>` — добавление подписки
* `list` — список подписок с ID, ценой, временем последней проверки
* `delete <id>` — удаление подписки
* `price <id>` — получение текущей цены из кэша
* `help` — справка
* `exit` — выход

Использует тот же HTTP клиент, что и Telegram бот, и переиспользует утилиту извлечения URL.

---

## Parsers

Отдельный слой получения данных с маркетплейсов.

Каждый маркетплейс реализуется отдельным классом.

Пример:

```python
class OzonParser(BaseParser):
    ...
```

### Извлечение данных

Ozon использует React Server Components и не отдает `__NEXT_DATA__`. Парсер извлекает данные из атрибутов `data-state` DOM-элементов, где хранится состояние React-компонентов.

Для товаров с вариантами (размер, цвет) парсер:

1. Извлекает SKU из URL (включая короткие ссылки через редирект)
2. Находит активный вариант по SKU
3. Извлекает цену и выбранные характеристики

---

# Слои приложения

```text
API / Bot
 ↓
Middleware / ConversationHandler
 ↓
Services (включая NotificationService)
 ↓
Repositories
 ↓
Database
```

---

## API Layer

Содержит:

```text
app/api/
├── routers/
├── schemas/
├── middleware/
└── dependencies.py
```

Отвечает за:

* HTTP запросы
* HTTP ответы
* Pydantic схемы
* Middleware (логирование, аутентификация)

Не содержит бизнес-логики.

### RequestLoggingMiddleware

Middleware для структурированного логирования всех HTTP запросов:

```python
logger.info(
    "http_request",
    method="POST",
    url="http://localhost:8000/api/v1/subscriptions",
    status_code=201,
    process_time="0.079s",
)
```

Заменяет стандартный uvicorn access log, который отключён через `--no-access-log`.

---

## Service Layer

Содержит:

```text
app/services/
```

Отвечает за:

* бизнес-логику
* сценарии работы системы

Примеры сервисов:

- **PriceParsingService** — оркестрирует процесс парсинга подписки, обновляет `last_check_at` при любой попытке и `last_success_at` при успехе
- **PriceService** — сохраняет историю цен, использует `PriceCache` для работы с Redis
- **SubscriptionService** — управляет подписками (создание, получение, удаление, обновление target_price, отметка об отправке уведомления)
- **UserService** — управляет пользователями
- **NotificationService** — умная логика уведомлений (проверка buffer, cooldown, отправка)

---

## Repository Layer

Содержит:

```text
app/repositories/
```

Отвечает за доступ к данным.

Не содержит бизнес-логики.

Примеры репозиториев:

- **SubscriptionRepository** — работа с подписками (включая `mark_alert_sent`, `reset_alert_status`)
- **PriceHistoryRepository** — работа с историей цен
- **ParseErrorRepository** — работа с ошибками парсинга

---

### Оптимизация запросов

Репозитории следуют принципу "один запрос вместо двух", если операция может быть выполнена атомарно.

Пример — удаление подписки:

```python
# Было: 2 запроса (SELECT + DELETE)
subscription = await repo.get(subscription_id)
if not subscription:
    return False
if subscription.user_id != user_id:
    return False
await repo.delete(subscription)

# Стало: 1 запрос (DELETE с WHERE)
deleted = await repo.delete_by_user(subscription_id, user_id)
if deleted:
    await session.commit()
return deleted
```

```SQL
DELETE FROM subscriptions WHERE id = :id AND user_id = :user_id
```

Это снижает нагрузку на БД и уменьшает latency.

Правило: Если базовый метод `BaseRepository` уже реализует нужную функциональность, переопределение запрещено (например, `get_all()` не переопределяется в `SubscriptionRepository`, если делает то же самое).

---

## Worker Layer

Содержит:

```text
app/workers/
```

Отвечает за фоновые задачи.

Компоненты:

- **celery_app.py** — конфигурация Celery
- **database.py** — фабрики engine/session для worker
- **http_client_manager.py** — ProcessBrowser singleton
- **tasks/** — определения задач (например, **parse_price**)
- **dependencies.py** — Dependency Injection для задач
- **settings.py** — константы (имена очередей, задач)
- **beat_schedule.py** — расписание периодических задач

---

## Bot Layer

Содержит:

```text
app/bot/
├── handlers/        # Обработчики команд и callback'ов
├── keyboards/       # Inline keyboard разметка
├── utils/           # Утилиты (safe_edit, url_parser)
├── client.py        # HTTP клиент для FastAPI
├── states.py        # Состояния ConversationHandler
└── main.py          # Точка входа
```

Отвечает за:

* взаимодействие с пользователем через Telegram
* inline keyboard навигацию
* ConversationHandler для интерактивных диалогов
* единый виджет UX
* graceful error handling

Не содержит бизнес-логики — все операции выполняются через API.

---

## Model Layer

Содержит:

```text
app/models/
```

ORM модели SQLAlchemy.

---

# Текущие модели

## User

```text
id
chat_id
username
created_at
```

---

## Subscription

```text
id
user_id
marketplace
product_url
product_name
current_price
target_price              # Целевая цена для уведомлений
is_active
status                    # IDLE или FAILED
last_check_at             # Время последней попытки парсинга (любой)
last_success_at           # Время последней успешной проверки
created_at
alert_sent                # Было ли отправлено уведомление о достижении target_price
last_alert_at             # Время последнего отправленного уведомления
cooldown_hours            # Период cooldown в часах между уведомлениями (default=24)
```

Разделение времени на `last_check_at` и `last_success_at` позволяет пользователю видеть:
- Когда система последний раз пыталась проверить цену (даже если с ошибкой)
- Насколько актуальны данные о цене

Поля `alert_sent`, `last_alert_at`, `cooldown_hours` реализуют систему умных уведомлений:
- `alert_sent` — флаг отправленного уведомления (сбрасывается при росте цены выше threshold)
- `last_alert_at` — время последнего уведомления (для проверки cooldown)
- `cooldown_hours` — период между уведомлениями (настраивается, по умолчанию 24 часа)

---

## PriceHistory

```text
id
subscription_id
price
created_at
```

---

## ParseError

```text
id
subscription_id
error_type
error_message
created_at
```

---

# Асинхронность

Проект использует async-first подход.

Асинхронными являются:

* FastAPI
* SQLAlchemy
* PostgreSQL driver
* Redis client
* HTTP client
* Telegram Bot

Запрещено использовать синхронные аналоги без необходимости.

### Celery и асинхронность

Celery задачи синхронные, но внутри используют `asyncio.run()` для вызова асинхронных сервисов. Это компромисс, позволяющий использовать асинхронный стек (SQLAlchemy, Playwright) в синхронных Celery задачах.

Для избежания конфликтов event loop:

* Воркер запускается с `--pool=prefork` (каждый процесс имеет свой event loop)
* Задача `check_all_subscriptions` создаёт собственный async engine через `create_worker_engine()` вместо использования глобального
* Синхронный Redis-клиент используется в воркере, асинхронный — в FastAPI
* Оба клиента переиспользуют соединения через singleton-паттерн

### Telegram Bot и синхронные HTTP-клиенты

В Celery задачах (например, `parse_price`) для отправки уведомлений используется **синхронный** `httpx.Client`, а не `httpx.AsyncClient`. Это связано с тем, что Celery задачи выполняются в prefork pool, где asyncio и async HTTP-клиенты вызывают ошибки DNS ([Errno -3]).

---

# Обработка ошибок

Общие принципы:

* ошибки логируются;
* ошибки не скрываются;
* пользователь получает понятное сообщение;
* технические детали остаются в логах.

### Ошибки парсинга

Все ошибки парсинга сохраняются в таблицу `parse_errors` с классификацией по типу:

* `ParserError` — базовое исключение парсера
* `ProductDataNotFoundError` — товар не найден
* `PriceNotFoundError` — цена не найдена
* Другие исключения — сетевые ошибки, таймауты и т.д.

Это позволяет анализировать частоту и типы ошибок для улучшения парсеров.

### Отслеживание попыток

`PriceParsingService` обновляет `last_check_at` при **любой** попытке парсинга (успешной или нет), а `last_success_at` — только при успешном получении цены. Это позволяет:

* Видеть, что система жива и пытается проверять цены
* Понимать, насколько актуальны данные о цене
* Выявлять проблемы с парсером

---

### Обработка недоступных товаров

Если товар удалён или недоступен на маркетплейсе, парсер возвращает ошибку (например, `ValueError("Ozon product schema not found")`).

**Текущее поведение:**
1. Ошибка логируется и сохраняется в `parse_errors`
2. Подписка помечается как `FAILED`
3. При следующей проверке (через `PRICE_CHECK_INTERVAL`) подписка снова попадает в очередь, так как `get_subscriptions_for_check` проверяет статусы `IDLE` и `FAILED`

**Проблема:**
Если товар удалён навсегда, система будет спамить маркетплейс запросами каждые N минут. За день это 720 запросов × запуск Playwright = значительная нагрузка на систему и маркетплейс.

**Решение (отложено):**
1. Детектировать редирект на страницу поиска (признак удалённого товара)
2. Счётчик ошибок — после N подряд ошибок деактивировать подписку автоматически
3. Новый статус `ARCHIVED` или `PRODUCT_UNAVAILABLE`, который исключается из проверки

**Временное решение:**
Пользователь может вручную удалить подписку через API/CLI/бот.

---

### Graceful Error Handling в Telegram Bot

Бот обрабатывает ошибки Telegram API для предотвращения каскадных ошибок и поломки виджетов:

```python
# Умный error_handler в main.py
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    error = context.error
    
    # Игнорируем устаревшие callback
    if isinstance(error, BadRequest) and (
        "query is too old" in str(error).lower()
        or "message is not modified" in str(error).lower()
    ):
        logger.warning("stale_callback_ignored", error=str(error)[:200])
        return
    
    # Игнорируем сетевые ошибки от прокси
    if isinstance(error, (NetworkError, TimedOut)):
        logger.warning("network_error_ignored", error=str(error)[:200])
        return
    
    # Логируем только важные ошибки
    logger.error("telegram_error", exception=str(error)[:500])
```

В обработчиках команд:

```python
except Exception as e:
    if is_stale_callback_error(e):
        return  # Не трогаем виджет
    
    # Показываем ошибку через "всплывашку"
    await query.answer("⚠️ Произошла ошибка. Попробуйте ещё раз.", show_alert=True)
```

Это обеспечивает:
- Виджет не ломается при временных проблемах
- Нет каскада ошибок (ошибка → попытка отредактировать → снова ошибка → ...)
- Пользователь видит понятные сообщения об ошибках
- Чистые логи без спама HTML от Cloudflare

---

# Retry Strategy

Для сетевых операций используется экспоненциальная задержка.

Примеры:

* ошибки маркетплейса;
* временная недоступность Telegram;
* сетевые таймауты.

### Celery Retry

Celery задачи автоматически ретраятся при ошибках:

* `max_retries=3` — максимум 3 попытки
* `retry_backoff=True` — экспоненциальная задержка
* `retry_backoff_max=600` — максимум 10 минут между ретраями
* `retry_jitter=True` — случайное смещение для избежания thundering herd

---

# Логирование

Используется structlog.

Формат:

```json
{
  "event": "price_changed",
  "subscription_id": 15,
  "old_price": 12990,
  "new_price": 11990
}
```

### HTTP логирование

Все HTTP запросы логируются через `RequestLoggingMiddleware`:

```json
{
  "event": "http_request",
  "method": "POST",
  "url": "http://localhost:8000/api/v1/subscriptions",
  "status_code": 201,
  "process_time": "0.079s"
}
```

Стандартный uvicorn access log отключён через `--no-access-log` для избежания дублирования.

### Rich Traceback

Celery worker использует Rich для форматирования traceback с locals:

```python
from rich.traceback import install
install(
    show_locals=True,
    locals_max_string=100,  # Строки обрезаются до 100 символов
    locals_max_length=10,   # Контейнеры до 10 элементов
    max_frames=15,          # Максимум 15 фреймов
)
```

**Truncation:** Длинные строки в логах обрезаются до 200 символов через `_truncate_long_fields` processor в structlog.

**Single Traceback:** Ошибка логируется один раз на верхнем уровне задачи (`_parse_price`), а не в каждом слое. Это устраняет дублирование traceback.

---

# Принятые архитектурные решения

## ADR-001

Решение:

Использовать RabbitMQ вместо Redis как основной брокер сообщений.

Причина:

RabbitMQ обеспечивает более надежную доставку сообщений и лучше подходит для дальнейшего масштабирования.

Статус:

Accepted

---

## ADR-002

Решение:

Использовать SQLAlchemy 2.0 Async.

Причина:

Единый современный ORM стек для FastAPI.

Статус:

Accepted

---

## ADR-003

Решение:

Использовать Telegram Bot как основной интерфейс пользователя.

Причина:

Минимальные затраты на frontend на раннем этапе проекта.

Статус:

Accepted

---

## ADR-004

Решение:

Использовать Celery с RabbitMQ для фоновых задач.

Причина:

* Надежная доставка задач через RabbitMQ
* Встроенная поддержка ретраев и откатов
* Возможность горизонтального масштабирования воркеров
* Мониторинг через Flower (будет добавлен позже)

Альтернативы:

* `asyncio` + `aio-pika` — сложнее в управлении, нет встроенных ретраев
* `arq` — меньше возможностей, меньше сообщество

Статус:

Accepted

---

## ADR-005

Решение:

Извлекать данные Ozon из атрибутов `data-state` вместо `__NEXT_DATA__`.

Причина:

Ozon перешел на React Server Components и больше не отдает `__NEXT_DATA__`. Атрибуты `data-state` содержат состояние React-компонентов и стабильнее, чем поиск по всему HTML.

Статус:

Accepted

---

## ADR-006

Решение:

Использовать Playwright (headless Chromium) вместо HTTP-клиентов для парсинга Ozon.

Причина:

Ozon использует продвинутую защиту от ботов, которая блокирует обычные HTTP-запросы:

* `httpx` возвращает 403 Forbidden
* `curl_cffi` с impersonate="chrome131" также возвращает 403
* Защита проверяет TLS fingerprint (JA3/JA4) и JavaScript challenges

Playwright запускает реальный браузер Chromium, который проходит все проверки.

Компромиссы:

* Парсинг занимает ~40 секунд вместо 1-2 секунд для HTTP-запроса
* Требует установки Chromium и системных зависимостей в Docker
* Потребляет больше памяти (~200-300 МБ на браузер)

Альтернативы, которые были отброшены:

* `httpx` — блокируется Ozon
* `curl_cffi` — блокируется Ozon
* Residential proxy — платное решение, отложено до необходимости масштабирования

Статус:

Accepted

---

## ADR-007

Решение:

Использовать раздельные поля `last_check_at` и `last_success_at` вместо одного `last_price_check_at`.

Причина:

Пользователю важно видеть:
- Когда система последний раз пыталась проверить цену (даже при ошибках)
- Насколько актуальны данные о цене

Одно поле не позволяло различить эти состояния. Например, если парсер 10 раз подряд не смог получить цену, пользователь видел старое время и думал, что система не работает.

Статус:

Accepted

---

## ADR-008

Решение:

Сделать интервал проверки цен конфигурируемым через `PRICE_CHECK_INTERVAL`.

Причина:

Разные сценарии использования требуют разных интервалов:
- Разработка/тестирование: 60 секунд (быстрая обратная связь)
- Продакшен: 900 секунд (15 минут, баланс между актуальностью и нагрузкой)
- Высокая нагрузка: 3600 секунд (1 час, снижение нагрузки на маркетплейс)

Минимальный интервал — 60 секунд, чтобы избежать перегрузки маркетплейсов и системы.

Статус:

Accepted

---

## ADR-009

Решение:

Запускать парсинг только через Celery Beat, без вызова `parse_price.delay()` при создании подписки.

Причина:

Ранее при создании подписки вызывался `parse_price.delay()`, а затем Beat тоже ставил задачу — возникало дублирование. Теперь парсинг запускается только через Beat в соответствии с `PRICE_CHECK_INTERVAL`.

Компромисс:

Первая цена для новой подписки появляется не мгновенно, а через один интервал проверки (до 15 минут).

Статус:

Accepted

---

## ADR-010

Решение:

Использовать Docker Compose profiles для опциональных сервисов.

Причина:

Telegram бот требует VPN/прокси для доступа к API Telegram. Не все окружения имеют такую возможность. Profiles позволяют:
- Запускать систему без бота (CLI режим) для разработки
- Запускать с ботом через `--profile bot` для продакшена

Статус:

Accepted

---

## ADR-011

Решение:

Использовать RequestLoggingMiddleware вместо стандартного uvicorn access log.

Причина:

* Структурированное логирование через structlog
* Единый формат логов для всего приложения
* Возможность добавления дополнительных полей (process_time, user_id и т.д.)
* Отключение uvicorn access log через `--no-access-log` для избежания дублирования

Статус:

Accepted

---

## ADR-012

Решение:

Использовать ProcessBrowser singleton per process вместо глобальных переменных.

Причина:

Глобальные переменные `_browser`, `_context`, `_page`, `_playwright` создавали неочевидное состояние и усложняли тестирование. Singleton-паттерн через класс `ProcessBrowser` обеспечивает:
- Явное управление жизненным циклом браузера
- Каждый worker-процесс имеет свой экземпляр
- Методы `get_page()` и `close()` для явного управления

Статус:

Accepted

---

## ADR-013

Решение:

Вынести фабрики engine/session в `app/workers/database.py`.

Причина:

Дублирование кода создания `create_async_engine()` и `async_sessionmaker()` в каждой задаче (`parse_price`, `check_all_subscriptions`). Фабрики `create_worker_engine()` и `create_worker_session_factory()` устраняют дублирование и централизуют конфигурацию.

Статус:

Accepted

---

## ADR-014

Решение:

Использовать PriceCache для инкапсуляции sync/async Redis логики.

Причина:

Дублирование кода `if self._redis_sync: ... elif self._redis: ...` в `PriceService`. Класс `PriceCache` инкапсулирует эту логику и предоставляет единый интерфейс `set()` и `get()`.

Статус:

Accepted

---

## ADR-015

Решение:

Использовать singleton-паттерн для Redis соединений.

Причина:

Функции `get_redis()` и `get_redis_sync()` создавали новое соединение при каждом вызове. Singleton через глобальные переменные `_async_redis` и `_sync_redis` переиспользует соединения и устраняет накладные расходы.

Статус:

Accepted

---

## ADR-016

Решение:

Использовать Rich traceback с ограничением locals и single traceback pattern.

Причина:

Traceback с locals полезен для отладки, но без ограничений выводит огромные HTML-страницы и дублируется между слоями. Конфигурация:
- `locals_max_string=100` — обрезка строк
- `locals_max_length=10` — обрезка контейнеров
- Truncation до 200 символов в structlog
- Single traceback — ошибка логируется один раз на верхнем уровне задачи

Статус:

Accepted

---

## ADR-017

Решение:

Использовать `@lru_cache` вместо глобальных переменных для singleton database engine в FastAPI.

Причина:

Ранее использовались глобальные переменные `_engine` и `_async_session_factory` с ручной проверкой `if _engine is None`. Это создавало неочевидное состояние и требовало ручного управления.

`@lru_cache` обеспечивает:
- Автоматический singleton (кэширует результат первого вызова)
- Потокобезопасность из коробки
- Ленивую инициализацию
- Чище код без глобальных переменных

Пример:

```python
# Было
_engine = None

def get_engine():
    global _engine
    if _engine is None:
        _engine = create_async_engine(...)
    return _engine

# Стало
@lru_cache
def get_engine():
    return create_async_engine(...)
```

Статус:

Accepted

---

## ADR-018

Решение:

Обновлять `last_check_at` только для успешно созданных задач в `check_all_subscriptions`.

Причина:

Ранее обновление происходило сразу после создания задачи:

```python
for subscription in subscriptions:
    parse_price.delay(subscription.id)
    await repo.mark_last_check_now(subscription.id)  # Если delay() упадёт — уже обновлено
```

Если `parse_price.delay()` упадёт после нескольких итераций, часть подписок уже обновлена (`last_check_at`), а часть — нет. Это создаёт рассинхронизацию: система считает, что проверила подписку, но задача не создана.

Новая реализация:
```python
successful_ids = []
for subscription in subscriptions:
    try:
        parse_price.delay(subscription.id)
        successful_ids.append(subscription.id)
    except Exception as e:
        logger.error("failed_to_create_task", subscription_id=subscription.id, error=str(e))

for sub_id in successful_ids:
    await repo.mark_last_check_now(sub_id)

await session.commit()
```

Это гарантирует атомарность: `last_check_at` обновляется только для подписок, для которых действительно созданы задачи.

Статус:

Accepted

---

## ADR-019

Решение:

Использовать Cloudflare Worker как прокси для доступа к Telegram API.

Причина:

Telegram API заблокирован в РФ. Cloudflare Worker проксирует запросы через свои серверы и обходит блокировки.

Преимущества:
- Бесплатный тариф Cloudflare Workers покрывает потребности проекта
- Низкая задержка (серверы Cloudflare по всему миру)
- Автоматическое масштабирование
- Не требует настройки VPN на сервере

Компромиссы:
- Зависимость от стороннего сервиса (Cloudflare)
- Возможны временные 502 ошибки (graceful handling реализован)
- Ограничения бесплатного тарифа (100k запросов/день)

Альтернативы:
- VPN на сервере — требует настройки и обслуживания
- Residential proxy — платное решение
- Прямой доступ — невозможен в РФ

Статус:

Accepted

---

## ADR-020

Решение:

Использовать единый виджет UX (редактирование сообщений) вместо создания новых сообщений.

Причина:

Создание новых сообщений при каждом действии приводит к:
- Спаму в чате
- Потере контекста пользователем
- Визуальному шуму

Единый виджет обеспечивает:
- Чистый чат без спама
- Пользователь не теряет контекст при навигации
- Плавный UX с редактированием вместо создания новых сообщений

Реализация:
```python
# Сохраняем ID сообщения
context.user_data["request_message_id"] = message.message_id

# Редактируем то же сообщение
await context.bot.edit_message_text(
    chat_id=chat_id,
    message_id=request_message_id,
    text=new_text,
    reply_markup=new_keyboard,
)
```

Компромиссы:
- Telegram API ограничивает частоту редактирования сообщений
- При устаревании callback (Query is too old) требуется graceful handling

Статус:

Accepted

---

## ADR-021

Решение:

Реализовать graceful error handling для ошибок Telegram API.

Причина:

При временных проблемах (устаревший callback, сетевые ошибки от Cloudflare прокси) бот не должен:
- Ломать виджет (сообщение должно оставаться в последнем успешном состоянии)
- Спамить пользователя сообщениями об ошибках
- Создавать каскад ошибок (ошибка → попытка отредактировать → снова ошибка)

Реализация:
```python
# Игнорирование устаревших callback
if is_stale_callback_error(e):
    return  # Не трогаем виджет

# Показ ошибки через "всплывашку"
await query.answer("⚠️ Произошла ошибка. Попробуйте ещё раз.", show_alert=True)
```

Это обеспечивает:
- Виджет не ломается при временных проблемах
- Пользователь видит понятные сообщения об ошибках
- Чистые логи без спама HTML от Cloudflare

Статус:

Accepted

---

## ADR-022

Решение:

Реализовать умную логику уведомлений с buffer (5%) и cooldown (24 часа).

Причина:

Простая проверка `current_price <= target_price` приводит к спаму уведомлениями при колебаниях цены вокруг target_price.

Умная логика обеспечивает:
- **Buffer (5%):** Автоматический сброс `alert_sent` когда цена поднимается выше `target_price * 1.05`. Это позволяет отправить новое уведомление при следующем падении цены.
- **Cooldown (24 часа):** Минимальный период между повторными уведомлениями. Это предотвращает спам при частых колебаниях цены.

Пример:
```
1. Цена: 100₽, target: 90₽, alert_sent: false
   ↓ Цена упала до 90₽
2. → Уведомление отправлено
   → alert_sent: true, last_alert_at: now
   ↓ Цена поднялась до 100₽ (> 94.5₽ threshold)
3. → alert_sent: false (автоматический сброс)
   ↓ Цена упала до 85₽
4. → Проверяем cooldown: прошло 2 часа < 24 часа
   → Не отправляем уведомление
   ↓ Прошло 25 часов, цена 85₽
5. → Уведомление отправлено
```

Константы:
```python
ALERT_RESET_BUFFER = 0.05  # 5% buffer для автоматического сброса
DEFAULT_COOLDOWN_HOURS = 24  # Cooldown между уведомлениями
```

Статус:

Accepted

---

## ADR-023

Решение:

Использовать ConversationHandler для интерактивных диалогов в Telegram Bot.

Причина:

Текстовые команды (например, `/set_target <id> <price>`) неудобны для пользователя. ConversationHandler позволяет:
- Управлять состоянием диалога (ожидание URL, ожидание цены)
- Обрабатывать отмену через fallback
- Поддерживать несколько entry_points для одного диалога
- Интегрироваться с inline keyboard навигацией

Пример:
```python
set_target_conversation_handler = ConversationHandler(
    entry_points=[
        CallbackQueryHandler(set_target_command, pattern=r"^set_target_select_\d+$"),
        CallbackQueryHandler(set_target_command, pattern=r"^set_target_new_\d+$"),
    ],
    states={
        WAITING_FOR_TARGET_PRICE: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, handle_target_price)
        ],
    },
    fallbacks=[
        CallbackQueryHandler(cancel_set_target, pattern=r"^cancel_target$"),
    ],
)
```

Это обеспечивает:
- Интуитивный UX для пользователя
- Чёткое управление состоянием диалога
- Возможность отмены на любом этапе

Статус:

Accepted

---

# Будущие архитектурные решения

Список решений, которые потребуется принять позже:

* Redis кэширование на уровне API (снижение нагрузки на БД)
* Настройка `cooldown_hours` для каждой подписки (пользовательский выбор)
* Покупка стабильного прокси для Telegram API (замена Cloudflare Worker)
* хранение графиков цен;
* пул браузеров для параллельного парсинга;
* residential proxy для масштабирования;
* Prometheus;
* Grafana;
* Kubernetes;
* CI/CD;
* авторизация через Telegram Login Widget;
* поддержка Wildberries и Яндекс.Маркет.

---

# Архитектурные принципы

При проектировании компонентов соблюдаются следующие принципы.

## Single Responsibility

Каждый сервис отвечает только за одну область ответственности.

Примеры:

- FastAPI — принимает запросы и управляет сценариями.
- Celery Worker — выполняет фоновые задачи.
- Parser — получает данные с маркетплейсов.
- NotificationService — умная логика уведомлений.
- Telegram Bot / CLI Client — взаимодействуют с пользователем.

---

## Weak Coupling

Компоненты должны быть слабо связаны между собой.

Каждый сервис взаимодействует только через публичные интерфейсы:

- HTTP API
- RabbitMQ
- PostgreSQL

Компоненты не должны зависеть от внутренней реализации друг друга.

---

## Failure Isolation

Отказ одного компонента не должен приводить к остановке всей системы.

Например:

- остановка Telegram Bot не влияет на парсинг;
- недоступность Parser не останавливает FastAPI;
- перезапуск Worker не влияет на API;
- временные проблемы с Cloudflare прокси не ломают виджет (graceful handling).

---

## Source of Truth

PostgreSQL является единственным источником истины.

Redis используется только как кэш.

RabbitMQ используется только для передачи сообщений.

---

## Stateless Services

Все сервисы проектируются максимально stateless.

После перезапуска любой сервис должен полностью восстановить работу, используя PostgreSQL и RabbitMQ.

Это позволяет горизонтально масштабировать систему без изменения бизнес-логики.

Исключение: `context.user_data` в Telegram Bot хранит состояние диалога (кэш подписок, ID сообщений), но это состояние временное и восстанавливается при необходимости.

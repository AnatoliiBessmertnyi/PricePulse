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
5. Отправляет уведомления при изменении цены.

---

# Высокоуровневая архитектура

```text
          Telegram / CLI Client
                    │
                    ▼
           Telegram Bot / CLI
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
                        (настраиваемый интервал)
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

# Основные компоненты

## FastAPI

Ответственность:

* REST API
* валидация данных
* работа с подписками
* регистрация пользователей
* удаление подписок
* структурированное логирование HTTP запросов через middleware

FastAPI не занимается парсингом.

---

## PostgreSQL

Источник истины (Source of Truth).

Хранит:

* пользователей
* подписки (включая `last_check_at` и `last_success_at`)
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

---

## Telegram Bot

Интерфейс пользователя.

Бот не содержит бизнес-логики.

Все операции выполняются через API.

Опциональный сервис — запускается через Docker Compose profile `bot`.

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
API
 ↓
Middleware
 ↓
Services
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
- **SubscriptionService** — управляет подписками (создание, получение, удаление)
- **UserService** — управляет пользователями

---

## Repository Layer

Содержит:

```text
app/repositories/
```

Отвечает за доступ к данным.

Не содержит бизнес-логики.

Примеры репозиториев:

- **SubscriptionRepository** — работа с подписками
- **PriceHistoryRepository** — работа с историей цен
- **ParseErrorRepository** — работа с ошибками парсинга

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
target_price
is_active
last_check_at        # Время последней попытки парсинга (любой)
last_success_at      # Время последней успешной проверки
created_at
```

Разделение времени на `last_check_at` и `last_success_at` позволяет пользователю видеть:
- Когда система последний раз пыталась проверить цену (даже если с ошибкой)
- Насколько актуальны данные о цене

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

# Будущие архитектурные решения

Список решений, которые потребуется принять позже:

* хранение графиков цен;
* пул браузеров для параллельного парсинга;
* residential proxy для масштабирования;
* Prometheus;
* Grafana;
* Kubernetes;
* CI/CD;
* уведомления об изменении цены через Telegram;
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
- перезапуск Worker не влияет на API.

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

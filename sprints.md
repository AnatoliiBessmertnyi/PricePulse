# PricePulse Roadmap

## Текущее состояние проекта

**Статус:** Sprint 1 — Завершен ✅

### Выполнено

- [x] Инициализация проекта
- [x] Документация проекта
- [x] Docker-инфраструктура
- [x] Полная интеграция API + Worker + Parser
- [x] CLI клиент для тестирования без Telegram
- [x] Конфигурируемый интервал проверки цен
- [x] Централизованное логирование с настраиваемым уровнем (structlog)
- [x] Рефакторинг и оптимизация кода (удаление неиспользуемого кода, константы, оптимизация парсера)
- [x] Финальная полировка кода (оптимизация запросов, атомарность, удаление дубликатов)


---

# Sprint 1 — Скелет и База

**Период:** День 1–14

## Цель

Поднять инфраструктуру проекта и реализовать полный цикл:

Telegram Bot → FastAPI → Celery → RabbitMQ → Worker → PostgreSQL

Пользователь должен иметь возможность добавить ссылку на товар, получить информацию о товаре (название, цена и выбранные характеристики) и сохранить первую цену.

---

## Задача 1. Docker-инфраструктура

Статус: ✅ Выполнено

### Подзадачи

* [x] PostgreSQL 16 контейнер
* [x] Redis контейнер
* [x] RabbitMQ контейнер
* [x] FastAPI контейнер
* [x] Celery Worker контейнер
* [x] Celery Beat контейнер
* [x] Init-контейнер для миграций
* [x] Проверить сетевое взаимодействие контейнеров
* [x] Проверить сохранение данных через volumes
* [x] Docker Compose profiles для опциональных сервисов (bot)

---

## Задача 2. Базовая конфигурация проекта

Статус: ✅ Выполнено

### Подзадачи

- [x] Pydantic Settings
- [x] Загрузка переменных окружения
- [x] Конфигурация БД
- [x] Конфигурация Redis
- [x] Конфигурация RabbitMQ
- [x] Конфигурация логирования
- [x] Конфигурируемый интервал проверки цен (`PRICE_CHECK_INTERVAL`)
- [x] Валидация минимального интервала (60 секунд)

---

## Задача 3. PostgreSQL и SQLAlchemy

Статус: ✅ Выполнено

### Модели

* [x] User
* [x] Subscription (с полями `last_check_at`, `last_success_at`)
* [x] PriceHistory
* [x] ParseError

### Дополнительно

* [x] Async SQLAlchemy 2.0
* [x] AsyncSession Factory
* [x] Alembic
* [x] Миграции (создание таблиц, добавление полей времени)
* [x] Корректные SQLAlchemy relationships с `back_populates`
* [x] Фабрики `create_worker_engine()` и `create_worker_session_factory()` в `app/workers/database.py`
* [x] `StrEnum` вместо `(str, Enum)` для `SubscriptionStatus`

---

## Задача 4. Repository Layer

Статус: ✅ Выполнено

### Подзадачи

* [x] BaseRepository
* [x] UserRepository
* [x] SubscriptionRepository (с методом `delete`)
* [x] PriceHistoryRepository
* [x] ParseErrorRepository

---

## Задача 5. Service Layer

Статус: ✅ Выполнено

### Подзадачи

* [x] SubscriptionService (с методом `delete_subscription`)
* [x] PriceService
* [x] UserService
* [x] PriceParsingService (с раздельным обновлением `last_check_at` и `last_success_at`)

---

## Задача 6. FastAPI

Статус: ✅ Выполнено

### Эндпоинты

- [x] POST /api/v1/users — регистрация пользователя
- [x] POST /api/v1/subscriptions — создание подписки
- [x] GET /api/v1/subscriptions/{user_id} — список подписок пользователя
- [x] GET /api/v1/subscriptions/{subscription_id}/prices — история цен
- [x] POST /api/v1/subscriptions/{subscription_id}/parse — ручной запуск парсинга
- [x] GET /api/v1/subscriptions/{subscription_id}/latest-price — последняя цена
- [x] DELETE /api/v1/subscriptions/{subscription_id} — удаление подписки
- [x] GET /health

### Дополнительно

- [x] Pydantic схемы (с полями `last_check_at`, `last_success_at`)
- [x] Валидация URL
- [x] Dependency Injection
- [x] Redis кэш для latest-price
- [x] RequestLoggingMiddleware для структурированного логирования HTTP запросов
- [x] PriceCache для инкапсуляции sync/async Redis логики

---

## Задача 7. Парсер маркетплейса

Статус: ✅ Выполнено

### Подзадачи

* [x] BaseParser
* [x] ParserFactory
* [x] OzonParser

### Результат

Получение:

* [x] Названия товара
* [x] Цены товара
* [x] Выбранных характеристик товара (цвет, размер и др.)

---

## Задача 8. Celery

Статус: ✅ Выполнено

### Подзадачи

* [x] Celery App
* [x] RabbitMQ Broker
* [x] parse_price_task()
* [x] Retry логика
* [x] Graceful Shutdown

### Дополнительно

* [x] Task acknowledgment (acks_late)
* [x] Prefetch multiplier (1)
* [x] Error tracking в БД
* [x] ProcessBrowser singleton (один браузер на worker-процесс)
* [x] Worker database factories (переиспользование engine/session)
* [x] `worker_max_tasks_per_child=1` для очистки ресурсов

---

## Задача 9. Интеграция API и Worker

Статус: ✅ Выполнено

### Подзадачи

* [x] Создание подписки
* [x] Первичный парсинг товара (через Beat, без дублирования задач)
* [x] Сохранение цены
* [x] Обновление `current_price`, `product_name`, `last_success_at` при успехе
* [x] Обновление `last_check_at` при любой попытке (включая ошибки)

---

## Задача 10. Redis

Статус: ✅ Выполнено

### Подзадачи

* [x] Подключение Redis
* [x] Асинхронный Redis клиент для FastAPI (`redis.asyncio.Redis`)
* [x] Синхронный Redis клиент для Celery Worker (`redis.Redis`)
* [x] Кеширование последней цены (TTL 1 час)
* [x] Ключ кэша: `price:latest:{subscription_id}`
* [x] Endpoint `/latest-price` с проверкой кэша перед БД
* [x] Redis connection singleton (переиспользование соединений)
* [x] PriceCache класс для инкапсуляции sync/async логики

---

## Задача 10.5. Периодический парсинг цен

Статус: ✅ Выполнено

### Подзадачи

- [x] Celery Beat (планировщик задач)
- [x] Задача `check_all_subscriptions` — получает все активные подписки
- [x] Массовая постановка задач на парсинг
- [x] Конфигурируемый интервал проверки через `PRICE_CHECK_INTERVAL`
- [x] Автоматическая конвертация секунд в crontab/timedelta
- [ ] Rate limiting (защита от блокировок) — отложено
- [x] Обработка ошибок и логирование
- [x] Интеграция Playwright для обхода защиты Ozon

### Результат

- Автоматический мониторинг цен по всем активным подпискам
- История цен обновляется регулярно (настраивается через `PRICE_CHECK_INTERVAL`)
- Playwright успешно обходит JavaScript challenges
- Парсинг занимает ~40 секунд на подписку (headless Chromium + тяжёлая страница Ozon)
- Цены кэшируются в Redis с TTL 1 час
- API возвращает данные из кэша мгновенно

### Технические детали

- **Celery Beat** отправляет задачу `check_all_subscriptions` с настраиваемым интервалом
- **Worker** получает все активные подписки и ставит задачи `parse_price`
- **Playwright** запускает headless Chromium для обхода защиты Ozon
- **Redis** кэширует последнюю цену с TTL 1 час
- **API** проверяет кэш перед обращением к БД

---

## Задача 10.6. CLI клиент для тестирования

Статус: ✅ Выполнено

### Описание

Временная замена Telegram бота для тестирования функциональности без необходимости настройки VPN/прокси для доступа к Telegram API.

### Команды

* [x] `start` — регистрация пользователя в системе
* [x] `add <ссылка>` — добавление подписки на товар (с извлечением URL из текста)
* [x] `list` — список подписок с отображением ID, цены, времени последней проверки
* [x] `delete <id>` — удаление подписки
* [x] `price <id>` — получение текущей цены из кэша
* [x] `help` — справка по командам
* [x] `exit` — выход из приложения

### Интеграция

* [x] HTTP клиент для взаимодействия с FastAPI
* [x] Переиспользование утилиты извлечения URL из `app/bot/utils/url_parser.py`
* [x] Отображение раздельной информации о времени (`last_check_at`, `last_success_at`)

---

## Задача 11. Telegram Bot

Статус: ⏳ В процессе

### Команды

* [x] /start — код реализован, требуется VPN/прокси для тестирования
* [x] /add — код реализован, требуется VPN/прокси для тестирования
* [x] /list — код реализован, требуется VPN/прокси для тестирования

### Интеграция

* [x] HTTP клиент для вызова FastAPI
* [x] Отображение списка подписок
* [ ] Настройка VPN/прокси для доступа к Telegram API
* [ ] Тестирование в реальном Telegram

### Примечание

Код бота полностью реализован и переиспользует ту же логику, что и CLI клиент. Для запуска требуется настройка VPN/прокси на рабочем ПК (на персональном ПК уже настроено через WSL).

---

## Задача 12. Логирование и мониторинг

Статус: ✅ Выполнено

### Подзадачи

* [x] Централизованная конфигурация логирования (`app/core/logging.py`)
* [x] structlog с человекочитаемым форматом (ConsoleRenderer)
* [x] Конфигурируемый уровень логирования через `LOG_LEVEL` в `.env`
* [x] Валидация уровня логирования (DEBUG, INFO, WARNING, ERROR, CRITICAL)
* [x] RequestLoggingMiddleware для HTTP запросов
* [x] Отключение дублирующего uvicorn access log
* [x] Настройка логирования для Celery Worker и Beat (`worker_hijack_root_logger=False`)
* [x] Настройка логирования для Telegram Bot
* [x] Настройка логирования для CLI клиента
* [x] Lazy инициализация database engine для корректной работы `echo` в зависимости от уровня
* [x] Устранение дублирования SQL логов (очистка handlers)
* [x] Унификация импортов logger во всех файлах проекта
* [x] Healthchecks
* [x] Проверка PostgreSQL
* [x] Проверка Redis
* [x] Проверка RabbitMQ
* [x] Rich traceback с ограничением locals (`locals_max_string=100`)
* [x] Truncation длинных строк в логах (200 символов)
* [x] Single traceback (ошибка логируется один раз на верхнем уровне задачи)
* [x] Устранение дублирования traceback между service и task слоями
* [x] Ruff конфигурация с ignore для русского проекта (RUF001-003, B008, S311)
* [x] per-file-ignores для CLI/scripts/bot/alembic

### Результат

- Единый формат логов для всех сервисов
- Возможность переключения уровня логирования через `.env` без изменения кода
- DEBUG режим показывает SQL запросы для отладки
- INFO режим показывает только важные события
- Логи пишутся в stdout (стандарт для контейнеризированных приложений)
- Docker автоматически собирает логи всех контейнеров
- Компактные traceback без дублирования и огромных HTML-выводов
- Чистый код без предупреждений ruff linter

---

## Задача 13. Рефакторинг и оптимизация кода

Статус: ✅ Выполнено

### Описание

Комплексный рефакторинг кодовой базы для улучшения качества, производительности и поддерживаемости.

### Подзадачи

#### Модель и миграции
* [x] Удаление неиспользуемых статусов из `SubscriptionStatus` (SCHEDULED, RUNNING, COMPLETED)
* [x] Удаление неиспользуемого поля `last_task_id` из модели `Subscription`
* [x] Создание миграции Alembic для ENUM типа (PostgreSQL)
* [x] Создание миграции для удаления колонки `last_task_id`
* [x] Добавление volumes в `docker-compose.yml` для локальной работы с миграциями

#### Парсер и сервисы
* [x] Объединение дублирующихся except блоков в `parse_price.py`
* [x] Оптимизация парсинга HTML в `OzonParser` (создание soup один раз)
* [x] Передача soup как параметра в приватные методы
* [x] Удаление неиспользуемого атрибута `_page` из `PriceParsingService`
* [x] Удаление присваивания `_page` в `dependencies.py`

#### Константы и магические числа
* [x] Создание файла `app/core/constants.py`
* [x] Вынос `REDIS_PRICE_TTL` (3600 секунд)
* [x] Вынос `PAGE_TIMEOUT_MS` (60000 миллисекунд)
* [x] Вынос `ERROR_MESSAGE_MAX_LENGTH` (200 символов)
* [x] Замена магических чисел на константы во всех файлах

#### Логирование
* [x] Настройка rich traceback с `locals_max_string=200`
* [x] Создание `_SoupProxy` для сокращения вывода BeautifulSoup в логах
* [x] Ограничение длины строк в логах (truncation)

### Результат

- **Чище код:** Удалены неиспользуемые поля, статусы и атрибуты
- **Быстрее парсинг:** HTML парсится один раз вместо трёх
- **Надёжнее ошибки:** Правильная обработка retry для разных типов исключений
- **Легче поддерживать:** Магические числа заменены на именованные константы
- **Чище логи:** Traceback не содержит огромных HTML-выводов
- **Правильные миграции:** ENUM типы корректно обновляются через Alembic

### Технические детали

**Миграции:**
- Autogenerate не работает для ENUM типов в PostgreSQL — требуется ручная доработка
- Для смены ENUM нужно: создать новый тип → мигрировать данные → удалить старый тип → переименовать
- Добавлены volumes в `docker-compose.yml` для сохранения файлов миграций локально

**Оптимизация парсера:**
- Было: `BeautifulSoup` создавался 3 раза (в `parse()`, `_extract_product_name()`, `_extract_selected_variant()`)
- Стало: `BeautifulSoup` создаётся один раз и передаётся как параметр
- Добавлен `_SoupProxy` с коротким `__repr__` для чистых логов

**Обработка ошибок:**
- `ParserError`, `ValueError` → не ретраим (ошибки парсинга)
- `ConnectionError`, `TimeoutError` → ретраим через Celery autoretry
- `SoftTimeLimitExceeded` → помечаем как failed без retry

**Константы:**
```python
# app/core/constants.py
REDIS_PRICE_TTL = 3600          # 1 hour
PAGE_TIMEOUT_MS = 60000         # 60 seconds
ERROR_MESSAGE_MAX_LENGTH = 200  # Максимальная длина сообщения об ошибке
```

---

## Задача 14. Финальная полировка кода

Статус: ✅ Выполнено

### Описание

Устранение мелких проблем для повышения качества кода и производительности.

### Подзадачи

#### Оптимизация запросов к БД
* [x] Удаление переопределения `get_all()` в `SubscriptionRepository` (дублировал базовый класс)
* [x] Добавление метода `delete_by_user()` для удаления подписки одним запросом вместо двух (SELECT + DELETE → DELETE)

#### Атомарность операций
* [x] `check_all_subscriptions` — обновление `last_check_at` только для успешно созданных задач
* [x] Предотвращение рассинхронизации при падении `parse_price.delay()`

#### Очистка кода
* [x] Удаление отладочных логов из `OzonParser` (`ozon_html_received`, `ozon_no_ld_json_found`, `ozon_data_state_blocks`)
* [x] Замена глобальных переменных на `@lru_cache` в `database.py`

### Результат

- **Меньше запросов:** `delete_subscription` делает 1 запрос вместо 2
- **Атомарность:** При ошибке создания задачи `last_check_at` не обновляется для неудачных подписок
- **Чище логи:** Удалены отладочные сообщения, оставлены только важные события
- **Лучше архитектура:** Использование `@lru_cache` вместо глобальных переменных для singleton-паттерна

### Технические детали

**Оптимизация удаления подписки:**
```python
# Было: 2 запроса
subscription = await repo.get(subscription_id)  # SELECT
if subscription.user_id != user_id: return False
await repo.delete(subscription)  # DELETE

# Стало: 1 запрос
deleted = await repo.delete_by_user(subscription_id, user_id)  # DELETE с WHERE
```

**Атомарность check_all_subscriptions:**
```python
# Было: обновление сразу после создания задачи
for subscription in subscriptions:
    parse_price.delay(subscription.id)
    await repo.mark_last_check_now(subscription.id)  # Если delay() упадёт — уже обновлено

# Стало: обновление только успешных задач
successful_ids = []
for subscription in subscriptions:
    parse_price.delay(subscription.id)
    successful_ids.append(subscription.id)

for sub_id in successful_ids:
    await repo.mark_last_check_now(sub_id)
```

---

# Критерии завершения Sprint 1

Все пункты ниже должны быть выполнены:

* [x] Пользователь добавляет ссылку через API (Telegram — в следующей задаче)
* [x] FastAPI сохраняет подписку
* [x] Парсинг запускается автоматически через Beat (без дублирования задач)
* [x] RabbitMQ доставляет задачу воркеру
* [x] Воркер получает данные из БД
* [x] Парсер получает цену товара
* [x] Цена сохраняется в PostgreSQL
* [x] История цен сохраняется
* [x] Периодический мониторинг цен работает (конфигурируемый интервал)
* [x] Подписки можно удалять
* [x] CLI клиент для тестирования без Telegram
* [ ] Уведомления об изменении цены отправляются в Telegram (Задача 11)
* [x] Система запускается через Docker Compose
* [x] Healthcheck показывает состояние сервисов
* [x] Последняя цена кэшируется в Redis
* [x] Playwright обходит защиту Ozon
* [x] Раздельное отслеживание времени последней попытки и успешной проверки
* [x] Централизованное логирование с настраиваемым уровнем
* [x] Финальная полировка кода (оптимизация запросов, атомарность)

---

# Технический долг

Список задач, которые сознательно отложены.

## Sprint 2+

* [ ] **Обработка мёртвых подписок** — детектирование удалённых/недоступных товаров и автоматическая деактивация подписок
* [ ] Поддержка Wildberries
* [ ] Поддержка Яндекс.Маркет
* [ ] Графики изменения цен
* [ ] Авторизация через Telegram Login Widget
* [ ] Rate Limiting (защита от блокировок Ozon)
* [ ] JSON формат логов для продакшена (сейчас человекочитаемый)
* [ ] Prometheus
* [ ] Grafana
* [ ] CI/CD (требует самохостный runner или альтернатива из-за ограничений GitHub Actions в РФ)
* [ ] Kubernetes
* [ ] Настройка VPN/прокси для Telegram бота на рабочем ПК
* [ ] Улучшение парсера Ozon (обработка блокировок и изменения layout)
* [ ] Оптимизация скорости парсинга (блокировка ресурсов через page.route)
* [ ] Самохостный GitHub Actions runner для CI/CD
```

---

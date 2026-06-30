import sys

import structlog

from app.bot.client import HTTPClient
from app.bot.utils.url_parser import clean_and_validate_url

logger = structlog.get_logger()


def setup_logging():
    """Настройка structlog для CLI"""
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.format_exc_info,
            structlog.dev.ConsoleRenderer(),
        ],
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


class CLIApp:
    """Простой CLI клиент для тестирования PricePulse"""

    def __init__(self):
        self.user_id: int | None = None
        self.chat_id: int = 12345  # Имитация Telegram chat_id
        self.username: str = "cli_user"

    async def start(self):
        """Команда start — регистрация пользователя"""
        try:
            async with HTTPClient() as client:
                user_data = await client.create_user(
                    chat_id=self.chat_id,
                    username=self.username,
                )
                self.user_id = user_data.get("id")

            print(f"\n✅ Привет, {self.username}! 👋")
            print(f"Вы зарегистрированы в системе PricePulse (user_id={self.user_id})")
            print("Доступные команды:")
            print("  add <ссылка> — добавить подписку на товар")
            print("  list — показать ваши подписки")
            print("  help — показать справку")
            print("  exit — выйти\n")

        except Exception as e:
            logger.error("start_failed", error=str(e))
            print(f"\n❌ Ошибка регистрации: {e}\n")

    async def add(self, args: list[str]):
        """Команда add — добавление подписки"""
        if not args:
            print("\nИспользование: add <ссылка на товар>")
            print("Пример: add https://www.ozon.ru/product/smartfon-samsung-galaxy-a54-256gb/\n")
            return

        text = " ".join(args)
        url, marketplace = clean_and_validate_url(text)

        if not url:
            print("\n❌ Не удалось найти корректную ссылку в сообщении.")
            print("Убедитесь, что вы отправили ссылку на товар с поддерживаемого маркетплейса (ozon.ru).\n")
            return

        if not marketplace:
            print(f"\n❌ Маркетплейс не поддерживается.")
            print(f"Поддерживаемые маркетплейсы: Ozon (ozon.ru)")
            print(f"Отправленная ссылка: {url}\n")
            return

        if not self.user_id:
            print("\n⚠️ Сначала зарегистрируйтесь командой 'start'\n")
            return

        try:
            async with HTTPClient() as client:
                subscription_data = await client.create_subscription(
                    user_id=self.user_id,
                    marketplace=marketplace,
                    product_url=url,
                )

            subscription_id = subscription_data.get("id")
            product_name = subscription_data.get("product_name")
            current_price = subscription_data.get("current_price")

            print("\n✅ Подписка успешно добавлена!")
            if product_name:
                print(f"📦 Товар: {product_name}")
            print(f"🔗 Ссылка: {url}")
            if current_price is not None:
                print(f"💰 Цена: {current_price} ₽")
            print(f"🆔 ID подписки: {subscription_id}")
            print("\nСистема будет проверять цену каждые 15 минут.\n")

        except Exception as e:
            logger.error("add_failed", error=str(e))
            error_message = str(e)
            if "400" in error_message:
                print(f"\n❌ Ошибка: некорректные данные. Проверьте ссылку.\n")
            elif "404" in error_message:
                print(f"\n❌ Ошибка: товар не найден. Проверьте ссылку.\n")
            else:
                print(f"\n❌ Произошла ошибка: {e}\n")

    async def list_subscriptions(self):
        """Команда list — список подписок"""
        if not self.user_id:
            print("\n⚠️ Сначала зарегистрируйтесь командой 'start'\n")
            return

        try:
            async with HTTPClient() as client:
                subscriptions = await client.get_user_subscriptions(self.user_id)

            if not subscriptions:
                print("\n📋 У вас пока нет подписок.")
                print("Используйте 'add <ссылка>', чтобы добавить подписку на товар.\n")
                return

            print(f"\n📋 Ваши подписки ({len(subscriptions)}):\n")

            for idx, sub in enumerate(subscriptions, 1):
                subscription_id = sub.get("id")  # Реальный ID из БД
                product_name = sub.get("product_name") or "Без названия"
                product_url = sub.get("product_url")
                current_price = sub.get("current_price")
                marketplace = sub.get("marketplace", "").upper()
                is_active = sub.get("is_active", True)
                last_check = sub.get("last_check_at")
                last_success = sub.get("last_success_at")

                print(f"{idx}. [ID: {subscription_id}] {product_name}")
                if marketplace:
                    print(f"   🏪 {marketplace}")
                if current_price is not None:
                    price_value = float(current_price)
                    print(f"   💰 {price_value:,.2f} ₽")
                else:
                    print(f"   💰 Цена не определена")
                
                # Показываем информацию о времени
                if last_success:
                    from datetime import datetime
                    try:
                        if isinstance(last_success, str):
                            success_time = datetime.fromisoformat(last_success.replace('Z', '+00:00'))
                        else:
                            success_time = last_success
                        print(f"   🕐 Последняя проверка: {success_time.strftime('%Y-%m-%d %H:%M:%S')}")
                    except:
                        print(f"   🕐 Последняя проверка: {last_success}")
                    
                    if last_check and last_check != last_success:
                        try:
                            if isinstance(last_check, str):
                                check_time = datetime.fromisoformat(last_check.replace('Z', '+00:00'))
                            else:
                                check_time = last_check
                            print(f"   ⚠️ Последняя попытка: {check_time.strftime('%Y-%m-%d %H:%M:%S')} (без успеха)")
                        except:
                            print(f"   ⚠️ Последняя попытка: {last_check} (без успеха)")
                else:
                    print(f"   🕐 Цена ещё не получена")
                    if last_check:
                        try:
                            if isinstance(last_check, str):
                                check_time = datetime.fromisoformat(last_check.replace('Z', '+00:00'))
                            else:
                                check_time = last_check
                            print(f"   ⚠️ Последняя попытка: {check_time.strftime('%Y-%m-%d %H:%M:%S')}")
                        except:
                            print(f"   ⚠️ Последняя попытка: {last_check}")
                
                print(f"   🔗 {product_url}")
                if not is_active:
                    print(f"   ⚠️ Неактивна")
                print()

        except Exception as e:
            logger.error("list_failed", error=str(e))
            print(f"\n❌ Ошибка при получении списка: {e}\n")

    async def price(self, args: list[str]):
        """Команда price — получить текущую цену подписки"""
        if not args:
            print("\nИспользование: price <subscription_id>")
            print("Пример: price 1\n")
            return

        try:
            subscription_id = int(args[0])
        except ValueError:
            print("\n❌ ID подписки должен быть числом\n")
            return

        try:
            async with HTTPClient() as client:
                # Получаем последнюю цену
                response = await client._request(
                    "GET",
                    f"/api/v1/subscriptions/{subscription_id}/latest-price",
                )
                
                if response.status_code == 404:
                    print(f"\n⏳ Цена для подписки #{subscription_id} ещё не получена.")
                    print("Подождите 10-15 секунд и попробуйте снова.\n")
                    return
                
                response.raise_for_status()
                data = response.json()
                
                price = data.get("price")
                source = data.get("source", "unknown")
                
                print(f"\n💰 Подписка #{subscription_id}: {price:,.2f} ₽")
                print(f"📊 Источник: {source}\n")

        except Exception as e:
            logger.error("price_failed", error=str(e))
            print(f"\n❌ Ошибка: {e}\n")

    async def delete(self, args: list[str]):
        """Команда delete — удаление подписки"""
        if not args:
            print("\nИспользование: delete <subscription_id>")
            print("Пример: delete 1\n")
            return

        try:
            subscription_id = int(args[0])
        except ValueError:
            print("\n❌ ID подписки должен быть числом\n")
            return

        if not self.user_id:
            print("\n⚠️ Сначала зарегистрируйтесь командой 'start'\n")
            return

        try:
            async with HTTPClient() as client:
                success = await client.delete_subscription(
                    subscription_id=subscription_id,
                    user_id=self.user_id,
                )

            if success:
                print(f"\n✅ Подписка #{subscription_id} удалена\n")
            else:
                print(f"\n❌ Подписка #{subscription_id} не найдена\n")

        except Exception as e:
            logger.error("delete_failed", error=str(e))
            print(f"\n❌ Ошибка при удалении: {e}\n")

    def show_help(self):
        """Показать справку"""
        print("\n📖 Доступные команды:")
        print("  start              — зарегистрироваться в системе")
        print("  add <ссылка>       — добавить подписку на товар")
        print("  list               — показать ваши подписки")
        print("  delete <id>        — удалить подписку")
        print("  price <id>         — получить текущую цену подписки")
        print("  help               — показать эту справку")
        print("  exit, quit         — выйти из приложения")
        print("\nПримеры:")
        print("  add https://www.ozon.ru/product/smartfon-samsung-galaxy-a54-256gb/")
        print("  delete 1")
        print("  price 1\n")


async def main_loop():
    """Главный цикл CLI приложения"""
    app = CLIApp()

    print("\n" + "=" * 60)
    print("🚀 PricePulse CLI — мониторинг цен на маркетплейсах")
    print("=" * 60)
    print("Введите 'help' для списка команд, 'exit' для выхода.\n")

    while True:
        try:
            # Читаем ввод пользователя
            user_input = input("pricepulse> ").strip()

            if not user_input:
                continue

            # Парсим команду и аргументы
            parts = user_input.split()
            command = parts[0].lower()
            args = parts[1:]

            # Обрабатываем команды
            if command in ("exit", "quit", "q"):
                print("\n👋 До свидания!\n")
                break
            elif command == "help":
                app.show_help()
            elif command == "start":
                await app.start()
            elif command == "add":
                await app.add(args)
            elif command == "list":
                await app.list_subscriptions()
            elif command == "price":
                await app.price(args)
            elif command == "delete":
                await app.delete(args)
            else:
                print(f"\n❓ Неизвестная команда: '{command}'")
                print("Введите 'help' для списка команд.\n")

        except KeyboardInterrupt:
            print("\n\n👋 До свидания!\n")
            break
        except EOFError:
            print("\n\n👋 До свидания!\n")
            break
        except Exception as e:
            logger.error("cli_error", error=str(e))
            print(f"\n❌ Ошибка: {e}\n")


def main():
    """Точка входа для CLI"""
    setup_logging()

    import asyncio
    asyncio.run(main_loop())


if __name__ == "__main__":
    main()

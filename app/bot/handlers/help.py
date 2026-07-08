from telegram import Update
from telegram.ext import ContextTypes

from app.bot.keyboards.main_menu import get_back_to_main_keyboard
from app.core.logging import get_logger

logger = get_logger(__name__)


async def help_command(
    update: Update,
    _context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """
    Обработчик команды /help

    Показывает справку по командам бота.
    """
    logger.info(
        "help_command",
        chat_id=update.effective_user.id if update.effective_user else None,
    )
    help_text = (
        "ℹ️ Справка по PricePulse\n\n"
        "📋 Основные команды:\n\n"
        "/start — Запустить бота и показать меню\n"
        "/help — Показать эту справку\n\n"
        "🎯 Как пользоваться:\n\n"
        "1️⃣ Добавить подписку:\n"
        '   • Нажмите "➕ Добавить товар"\n'
        "   • Отправьте ссылку на товар с Ozon\n"
        "   • Можно отправить текст с ссылкой:\n"
        '     "Смотри что я нашел! https://ozon.ru/product/..."\n\n'
        "2️⃣ Посмотреть подписки:\n"
        '   • Нажмите "📋 Мои подписки"\n'
        "   • Увидите список с текущими ценами\n\n"
        "3️⃣ Удалить подписку:\n"
        '   • Нажмите "❌ Удалить подписку"\n'
        "   • Выберите товар из списка\n"
        "   • Подтвердите удаление\n\n"
        "🏪 Поддерживаемые маркетплейсы:\n"
        "• Ozon (ozon.ru)\n\n"
        "💡 Как это работает:\n"
        "Система проверяет цены каждые 15 минут и уведомляет "
        "вас при снижении цены."
    )

    if update.callback_query:
        await update.callback_query.edit_message_text(
            help_text, reply_markup=get_back_to_main_keyboard()
        )
    else:
        await update.message.reply_text(
            help_text, reply_markup=get_back_to_main_keyboard()
        )

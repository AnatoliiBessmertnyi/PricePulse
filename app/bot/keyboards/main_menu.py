"""Главное меню бота с навигационными кнопками"""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def get_main_menu_keyboard() -> InlineKeyboardMarkup:
    """
    Создать клавиатуру главного меню

    Returns:
        InlineKeyboardMarkup с кнопками навигации
    """
    keyboard = [
        [
            InlineKeyboardButton("📋 Мои подписки", callback_data="menu_list"),
            InlineKeyboardButton("🗄 Архивные", callback_data="menu_archived"),
        ],
        [
            InlineKeyboardButton("➕ Добавить подписку", callback_data="menu_add"),
            InlineKeyboardButton("❌ Удалить подписку", callback_data="menu_delete"),
        ],
        [InlineKeyboardButton("ℹ️ Помощь", callback_data="menu_help")],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_back_to_main_keyboard() -> InlineKeyboardMarkup:
    """
    Создать клавиатуру с кнопкой "Назад в меню"

    Returns:
        InlineKeyboardMarkup с кнопкой возврата
    """
    keyboard = [[InlineKeyboardButton("◀️ Назад в меню", callback_data="back_main")]]
    return InlineKeyboardMarkup(keyboard)

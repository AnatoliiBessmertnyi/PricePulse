"""Клавиатуры для работы со списком подписок"""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def get_subscriptions_list_keyboard(
    subscriptions: list[dict],
    page: int = 0,
    total_pages: int = 1,
    action: str = "view",
    show_refresh: bool = False,
) -> InlineKeyboardMarkup:
    """
    Создать клавиатуру для списка подписок с пагинацией

    Args:
        subscriptions: Список подписок на теку странице
        page: Текущая страница (0-indexed)
        total_pages: Общее количество страниц
        action: Тип действия ("view" для просмотра, "delete" для удаления)
        show_refresh: Показать кнопку "Обновить"

    Returns:
        InlineKeyboardMarkup с кнопками навигации
    """
    keyboard = []
    if action == "delete":
        for sub in subscriptions:
            sub_id = sub.get("id")
            product_name = sub.get("product_name") or "Без названия"
            if len(product_name) > 35:
                product_name = product_name[:32] + "..."

            button_text = f"❌ {product_name}"
            callback_data = f"delete_confirm_{sub_id}"
            keyboard.append(
                [InlineKeyboardButton(button_text, callback_data=callback_data)]
            )

    if total_pages > 1:
        pagination_row = []

        if page > 0:
            pagination_row.append(
                InlineKeyboardButton(
                    "◀️ Назад", callback_data=f"page_{action}_{page - 1}"
                )
            )

        pagination_row.append(
            InlineKeyboardButton(f"{page + 1}/{total_pages}", callback_data="noop")
        )

        if page < total_pages - 1:
            pagination_row.append(
                InlineKeyboardButton(
                    "Вперёд ▶️", callback_data=f"page_{action}_{page + 1}"
                )
            )

        keyboard.append(pagination_row)

    nav_row = []
    if show_refresh:
        nav_row.append(
            InlineKeyboardButton("🔄 Обновить", callback_data="refresh_list")
        )

    nav_row.append(InlineKeyboardButton("◀️ Назад в меню", callback_data="back_main"))
    keyboard.append(nav_row)
    return InlineKeyboardMarkup(keyboard)


def get_delete_confirmation_keyboard(subscription_id: int) -> InlineKeyboardMarkup:
    """
    Создать клавиатуру подтверждения удаления

    Args:
        subscription_id: ID подписки для удаления

    Returns:
        InlineKeyboardMarkup с кнопками подтверждения/отмены
    """
    keyboard = [
        [
            InlineKeyboardButton(
                "✅ Да, удалить", callback_data=f"delete_yes_{subscription_id}"
            ),
            InlineKeyboardButton("❌ Отмена", callback_data="menu_delete"),
        ],
        [InlineKeyboardButton("◀️ Назад в меню", callback_data="back_main")],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_cancel_keyboard() -> InlineKeyboardMarkup:
    """
    Создать клавиатуру с кнопкой отмены

    Returns:
        InlineKeyboardMarkup с кнопкой отмены
    """
    keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data="cancel_add")]]
    return InlineKeyboardMarkup(keyboard)

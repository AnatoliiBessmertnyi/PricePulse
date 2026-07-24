"""Клавиатуры для работы со списком подписок"""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def get_subscriptions_list_keyboard(
    subscriptions: list[dict],
    page: int = 0,
    total_pages: int = 1,
    action: str = "view",
    show_refresh: bool = False,
) -> InlineKeyboardMarkup:
    """Клавиатура списка подписок с пагинацией и действиями."""
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
    elif action == "view":
        keyboard.append(
            [
                InlineKeyboardButton(
                    "🎯 Установить цену", callback_data="set_target_menu"
                )
            ]
        )
        keyboard.append(
            [
                InlineKeyboardButton(
                    "⏱ Настроить интервал", callback_data="set_cooldown_menu"
                )
            ]
        )
        keyboard.append(
            [InlineKeyboardButton("📊 Графики цен", callback_data="menu_chart")]
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

    nav_row.append(InlineKeyboardButton("🗄 Архивные", callback_data="menu_archived"))
    keyboard.append(nav_row)
    keyboard.append([InlineKeyboardButton("◀️ Назад в меню", callback_data="back_main")])
    return InlineKeyboardMarkup(keyboard)


def get_delete_confirmation_keyboard(subscription_id: int) -> InlineKeyboardMarkup:
    """Клавиатура подтверждения удаления подписки."""
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
    """Клавиатура отмены добавления подписки."""
    keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data="cancel_add")]]
    return InlineKeyboardMarkup(keyboard)


def get_target_subscription_keyboard(
    subscriptions: list[dict], page: int = 0, total_pages: int = 1
) -> InlineKeyboardMarkup:
    """Клавиатура выбора подписки для установки целевой цены."""
    keyboard = []
    for sub in subscriptions:
        sub_id = sub.get("id")
        product_name = sub.get("product_name") or "Без названия"
        current_price = sub.get("current_price")
        target_price = sub.get("target_price")

        if len(product_name) > 30:
            product_name = product_name[:27] + "..."

        button_text = f"📦 {product_name}"
        if current_price is not None:
            price_str = f"{float(current_price):,.0f}₽"
            button_text += f" | 💰 {price_str}"
        if target_price is not None:
            target_str = f"🎯 {float(target_price):,.0f}₽"
            button_text += f" | {target_str}"

        keyboard.append(
            [
                InlineKeyboardButton(
                    button_text, callback_data=f"set_target_select_{sub_id}"
                )
            ]
        )

    if total_pages > 1:
        pagination_row = []

        if page > 0:
            pagination_row.append(
                InlineKeyboardButton(
                    "◀️ Назад", callback_data=f"page_set_target_{page - 1}"
                )
            )

        pagination_row.append(
            InlineKeyboardButton(f"{page + 1}/{total_pages}", callback_data="noop")
        )

        if page < total_pages - 1:
            pagination_row.append(
                InlineKeyboardButton(
                    "Вперёд ▶️", callback_data=f"page_set_target_{page + 1}"
                )
            )

        keyboard.append(pagination_row)

    keyboard.append(
        [InlineKeyboardButton("◀️ Назад к списку", callback_data="menu_list")]
    )

    return InlineKeyboardMarkup(keyboard)


def get_cancel_target_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура отмены установки целевой цены из меню."""
    keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data="cancel_target")]]
    return InlineKeyboardMarkup(keyboard)


def get_subscription_created_keyboard(subscription_id: int) -> InlineKeyboardMarkup:
    """Клавиатура после успешного создания подписки."""
    keyboard = [
        [
            InlineKeyboardButton(
                "🎯 Установить целевую цену",
                callback_data=f"set_target_new_{subscription_id}",
            )
        ],
        [InlineKeyboardButton("🏠 В главное меню", callback_data="back_main")],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_empty_subscriptions_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для пустого списка активных подписок."""
    keyboard = [
        [InlineKeyboardButton("➕ Добавить подписку", callback_data="menu_add")],
        [InlineKeyboardButton("🗄 Архивные подписки", callback_data="menu_archived")],
        [InlineKeyboardButton("🏠 Главное меню", callback_data="back_main")],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_archived_subscriptions_keyboard(
    archived_subs: list[dict],
) -> InlineKeyboardMarkup:
    """Клавиатура списка архивных подписок."""
    keyboard = []
    for sub in archived_subs:
        name = (sub.get("product_name") or "Без названия")[:40]
        sub_id = sub["id"]
        keyboard.append(
            [
                InlineKeyboardButton(
                    f"♻️ {name}", callback_data=f"reactivate_confirm_{sub_id}"
                )
            ]
        )

    keyboard.append(
        [InlineKeyboardButton("◀️ Назад к списку", callback_data="menu_list")]
    )
    return InlineKeyboardMarkup(keyboard)


def get_empty_archived_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для пустого списка архивных подписок."""
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("🏠 Назад в меню", callback_data="back_main")]]
    )


def get_cooldown_subscription_keyboard(
    subscriptions: list[dict], page: int = 0, total_pages: int = 1
) -> InlineKeyboardMarkup:
    """Клавиатура выбора подписки для настройки интервала уведомлений."""
    keyboard = []
    for sub in subscriptions:
        sub_id = sub.get("id")
        product_name = sub.get("product_name") or "Без названия"
        cooldown = sub.get("cooldown_hours", 24)

        if len(product_name) > 30:
            product_name = product_name[:27] + "..."

        button_text = f"⏱ {product_name} ({cooldown}ч)"
        keyboard.append(
            [
                InlineKeyboardButton(
                    button_text, callback_data=f"set_cooldown_select_{sub_id}"
                )
            ]
        )

    if total_pages > 1:
        pagination_row = []
        if page > 0:
            pagination_row.append(
                InlineKeyboardButton(
                    "◀️ Назад", callback_data=f"page_set_cooldown_{page - 1}"
                )
            )
        pagination_row.append(
            InlineKeyboardButton(f"{page + 1}/{total_pages}", callback_data="noop")
        )
        if page < total_pages - 1:
            pagination_row.append(
                InlineKeyboardButton(
                    "Вперёд ▶️", callback_data=f"page_set_cooldown_{page + 1}"
                )
            )
        keyboard.append(pagination_row)

    keyboard.append(
        [InlineKeyboardButton("◀️ Назад к списку", callback_data="menu_list")]
    )
    return InlineKeyboardMarkup(keyboard)


def get_chart_subscription_keyboard(
    subscriptions: list[dict], page: int = 0, total_pages: int = 1
) -> InlineKeyboardMarkup:
    """Клавиатура выбора подписки для просмотра графика цен."""
    keyboard = []
    for sub in subscriptions:
        sub_id = sub.get("id")
        display_name = sub.get("display_name") or "Без названия"
        if len(display_name) > 30:
            display_name = display_name[:27] + "..."

        keyboard.append(
            [
                InlineKeyboardButton(
                    f"📊 {display_name}", callback_data=f"chart_select_{sub_id}"
                )
            ]
        )

    if total_pages > 1:
        pagination_row = []
        if page > 0:
            pagination_row.append(
                InlineKeyboardButton("◀️", callback_data=f"page_chart_{page - 1}")
            )
        pagination_row.append(
            InlineKeyboardButton(f"{page + 1}/{total_pages}", callback_data="noop")
        )
        if page < total_pages - 1:
            pagination_row.append(
                InlineKeyboardButton("▶️", callback_data=f"page_chart_{page + 1}")
            )
        keyboard.append(pagination_row)

    keyboard.append(
        [InlineKeyboardButton("◀️ Назад к списку", callback_data="menu_list")]
    )
    return InlineKeyboardMarkup(keyboard)


def get_chart_period_keyboard(
    subscription_id: int, current_period: str
) -> InlineKeyboardMarkup:
    """Клавиатура выбора периода для графика цен."""
    btn_7d = "✅ 7 дней" if current_period == "7d" else "7 дней"
    btn_30d = "✅ 30 дней" if current_period == "30d" else "30 дней"
    btn_all = "✅ Всё время" if current_period == "all" else "Всё время"

    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    btn_7d, callback_data=f"chart_period_{subscription_id}_7d"
                ),
                InlineKeyboardButton(
                    btn_30d, callback_data=f"chart_period_{subscription_id}_30d"
                ),
                InlineKeyboardButton(
                    btn_all, callback_data=f"chart_period_{subscription_id}_all"
                ),
            ],
            [
                InlineKeyboardButton(
                    "◀️ Назад к выбору подписки", callback_data="menu_chart"
                )
            ],
        ]
    )


def get_empty_delete_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для пустого списка удаляемых подписок."""
    keyboard = [
        [InlineKeyboardButton("➕ Добавить подписку", callback_data="menu_add")],
        [InlineKeyboardButton("◀️ Назад в меню", callback_data="back_main")],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_chart_error_keyboard(subscription_id: int) -> InlineKeyboardMarkup:
    """Клавиатура обработки ошибки построения графика."""
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "🔄 Повторить попытку",
                    callback_data=f"chart_select_{subscription_id}",
                )
            ],
            [
                InlineKeyboardButton(
                    "◀️ Назад к выбору подписки", callback_data="menu_chart"
                )
            ],
        ]
    )


def get_price_drop_keyboard(subscription_id: int) -> InlineKeyboardMarkup:
    """Клавиатура действий в уведомлении о снижении цены."""
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "🎯 Изменить цель", callback_data=f"change_target_{subscription_id}"
                ),
                InlineKeyboardButton(
                    "🗄 В архив", callback_data=f"archive_notify_{subscription_id}"
                ),
            ],
        ]
    )


def get_target_price_error_keyboard(subscription_id: int) -> InlineKeyboardMarkup:
    """Клавиатура обработки ошибки установки целевой цены."""
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "🔄 Повторить", callback_data=f"set_target_select_{subscription_id}"
                ),
                InlineKeyboardButton("◀️ К списку", callback_data="menu_list"),
            ],
        ]
    )


def get_cooldown_error_keyboard(subscription_id: int) -> InlineKeyboardMarkup:
    """Клавиатура отмены изменения цели из уведомления."""
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "🔄 Повторить",
                    callback_data=f"set_cooldown_select_{subscription_id}",
                ),
                InlineKeyboardButton("◀️ К списку", callback_data="menu_list"),
            ],
        ]
    )


def get_notification_target_cancel_keyboard(
    subscription_id: int,
) -> InlineKeyboardMarkup:
    """Клавиатура отмены изменения цели прямо из уведомления."""
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "❌ Отмена", callback_data=f"cancel_notify_target_{subscription_id}"
                )
            ]
        ]
    )

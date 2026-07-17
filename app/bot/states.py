"""Состояния для ConversationHandler бота"""

WAITING_FOR_URL = 1  # Состояние ожидания URL при добавлении подписки
CONFIRMING_DELETE = 2  # Состояние подтверждения удаления
WAITING_FOR_TARGET_PRICE = 3  # Состояние ожидания target_price
WAITING_COOLDOWN_HOURS = 4  # Состояние ожидания ввода часов для cooldown

"""
DEPRECATED: Этот файл оставлен для обратной совместимости.
Используйте admin_handlers.py и user_handlers.py напрямую.
"""
# Для обратной совместимости импортируем роутеры
from app.handlers.admin_handlers import router as admin_router
from app.handlers.user_handlers import router as user_router

# Экспортируем для старого кода
router = user_router  # Для совместимости, если где-то используется handlers.router

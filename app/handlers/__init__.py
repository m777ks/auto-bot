"""
Модуль обработчиков бота.
Импортирует роутеры для подключения в диспетчер.
"""
from app.handlers.admin_handlers import router as admin_router
from app.handlers.user_handlers import router as user_router

__all__ = ['admin_router', 'user_router']

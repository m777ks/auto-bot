import logging

from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery
from db.ORM import LoggerORM
from config_data.config import ConfigEnv, load_config

config: ConfigEnv = load_config()
logger = logging.getLogger(__name__)


class LoggingMiddleware(BaseMiddleware):
    """
    Middleware для логирования
    """
    async def __call__(self, handler, event, data):
        """
        Вызывается для любого события.
        """
        if isinstance(event, Message):
            # Логируем сообщение
            print(f"LOGGING MESSAGE: {event.text}")
            await LoggerORM.create_log(
                user_id=event.from_user.id,
                user_name=event.from_user.username,
                action=event.text,
                type="message",
            )

                
        elif isinstance(event, CallbackQuery):
            # Логируем callback-запрос
            print(f"LOGGING CALLBACK: {event.data}")
            await LoggerORM.create_log(
                user_id=event.from_user.id,
                user_name=event.from_user.username,
                action=event.data,
                type="callback",
            )

        
        # Продолжаем обработку
        return await handler(event, data)

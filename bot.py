import asyncio
import logging
import limited_aiogram

from aiogram import Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import text

from app.handlers.admin_handlers import router as admin_router
from app.handlers.user_handlers import router as user_router
from app.keybords.main_menu import set_main_menu
from app.middlewares.logger_middleware import LoggingMiddleware
from app.middlewares.album_middleware import AlbumMiddleware

from aiogram.fsm.storage.redis import RedisStorage
from app.sender import sender
from app.service.redis_client import redis
from config_data.config import ConfigEnv, load_config
from db.database import async_engine
from db.ORM import PostsORM

# Инициализируем логгер
logger = logging.getLogger(__name__)

# Загружаем конфиг в переменную config
config: ConfigEnv = load_config()
bot = limited_aiogram.LimitedBot(token=config.tg_bot.token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))

storage = RedisStorage(redis=redis)
scheduler = AsyncIOScheduler(timezone="Europe/Moscow")


async def heartbeat():
    """Фоновая задача: обновляет статус бота в Redis."""
    while True:
        try:
            await redis.set("bot:heartbeat", "alive", ex=30)  # ключ живёт 30 секунд
            logger.debug("Heartbeat sent to Redis")
        except Exception as e:
            logger.error(f"Heartbeat error: {e}")
        await asyncio.sleep(10)


async def check_posts_no_copy(posts: list):
    """Проверка через получение информации о чате (без спама)"""
    deleted_ids = []
    checked = 0
    
    for post in posts:
        try:
            # Пытаемся получить информацию о сообщении
            # Этот метод НЕ копирует сообщение
            await bot.get_chat(config.tg_bot.channel_id)
            
            # Если дошли сюда - канал доступен
            # Теперь проверяем конкретное сообщение через edit
            try:
                # Пытаемся "отредактировать" сообщение (но не редактируем)
                # Если сообщение не существует - получим ошибку
                await bot.edit_message_reply_markup(
                    chat_id=config.tg_bot.channel_id,
                    message_id=post.post_id,
                    reply_markup=None
                )
                checked += 1
            except TelegramBadRequest as e:
                if "message to edit not found" in str(e).lower() or \
                   "message not found" in str(e).lower():
                    deleted_ids.append(post.id)
                elif "message is not modified" in str(e).lower():
                    # Сообщение существует, просто не изменилось
                    checked += 1
                else:
                    raise
                    
        except Exception as e:
            logger.warning(f"Ошибка проверки {post.id}: {e}")
        
        await asyncio.sleep(0.1)  # Меньше задержка, т.к. не копируем
    
    return deleted_ids, checked


async def main():
    # Конфигурируем логирование
    logging.basicConfig(
        level=logging.INFO,
        format='%(filename)s:%(lineno)d #%(levelname)-8s '
               '[%(asctime)s] - %(name)s - %(message)s')

    # Выводим в консоль информацию о начале запуска бота
    logger.info('Starting bot')

    # Проверяем соединение с PostgreSQL
    async with async_engine.connect() as conn:
        res = await conn.execute(text('SELECT VERSION()'))
        logger.info(f'Starting {res.first()[0]}')

    dp = Dispatcher(bot=bot, storage=storage)

    # Регистрируем middleware
    dp.callback_query.middleware(LoggingMiddleware())
    dp.message.middleware(LoggingMiddleware())
    dp.message.middleware(AlbumMiddleware(latency=0.5, admin_ids=config.tg_bot.admin_ids))

    # Роутер админов должен быть первым (приоритет обработки supergroup)
    dp.include_router(admin_router)
    dp.include_router(user_router)

    dp.include_router(sender.router)

    # Настраиваем главное меню бота
    await set_main_menu(bot)

    # Запускаем heartbeat в фоне
    asyncio.create_task(heartbeat())

    # Запускаем scheduler для периодической проверки постов
    scheduler.add_job(
        check_posts_no_copy,
        'interval',
        hours=1,  # Проверяем каждые 1 час
        id='check_deleted_posts',
        replace_existing=True
    )
    scheduler.start()
    logger.info("Scheduler запущен. Проверка постов каждые 1 час.")

    # Пропускаем накопившиеся апдейты и запускаем polling
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == '__main__':
    asyncio.run(main())

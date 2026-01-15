import asyncio
import logging
import limited_aiogram

from aiogram import Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
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


async def main():
    # await start_http_server()
    # scheduler.start()


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

    # Пропускаем накопившиеся апдейты и запускаем polling
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == '__main__':
    asyncio.run(main())

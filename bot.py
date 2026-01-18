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


async def check_deleted_posts():
    """
    Проверяет существуют ли посты в канале.
    Если пост удалён — помечает его в БД.
    """
    logger.info("[CHECK_POSTS] Начинаю проверку постов на удаление...")
    
    try:
        posts = await PostsORM.get_active_posts()
        logger.info(f"[CHECK_POSTS] Найдено {len(posts)} активных постов для проверки")
        
        deleted_ids = []
        checked = 0
        
        for post in posts:
            try:
                # Пытаемся "отредактировать" reply_markup
                # Если сообщение существует - получим "message is not modified"
                # Если не существует - получим "message not found"
                await bot.edit_message_reply_markup(
                    chat_id=config.tg_bot.channel_id,
                    message_id=post.post_id,
                    reply_markup=None
                )
                checked += 1
                
            except TelegramBadRequest as e:
                error_msg = str(e).lower()
                
                if "message to edit not found" in error_msg or \
                "message not found" in error_msg:
                    # Пост удалён из канала
                    deleted_ids.append(post.id)
                    logger.info(f"[CHECK_POSTS] Пост ID={post.id} (TG: {post.post_id}) удалён из канала")
                    
                elif "message is not modified" in error_msg or \
                    "message can't be edited" in error_msg or \
                    "there is no reply markup" in error_msg:
                    # Сообщение существует, просто не изменилось или нет markup
                    checked += 1
                    
                else:
                    logger.warning(f"[CHECK_POSTS] Ошибка проверки поста {post.id}: {e}")
                    
            except Exception as e:
                logger.warning(f"[CHECK_POSTS] Неизвестная ошибка для поста {post.id}: {e}")
            
            # Небольшая задержка
            await asyncio.sleep(0.5)
        
        # Помечаем удалённые посты
        if deleted_ids:
            count = await PostsORM.mark_posts_as_deleted(deleted_ids)
            logger.info(f"[CHECK_POSTS] Помечено как удалённые: {count} постов")
        
        logger.info(f"[CHECK_POSTS] Проверка завершена. Проверено: {checked}, удалено: {len(deleted_ids)}")
        
    except Exception as e:
        logger.error(f"[CHECK_POSTS] Ошибка при проверке постов: {e}")


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
        check_deleted_posts,
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

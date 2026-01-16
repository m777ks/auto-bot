"""
Обработчики для пользователей:
- Регистрация и команды
- Выбор языка
- Отправка сообщений в топики
- Модерация чата
"""
import asyncio
import logging
from datetime import datetime

from aiogram.fsm.context import FSMContext
from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery

from app.service.functions import check_throttle
from app.service.redis_client import redis
from app.keybords.keybords import kb_language
from config_data.config import ConfigEnv, load_config
from db.ORM import DataBase, ThreadORM
from app.lexicon.lexicon import LEXICON

config: ConfigEnv = load_config()
router = Router()
logger = logging.getLogger(__name__)


# ==================== КОМАНДЫ ====================

@router.message(Command(commands='start'), F.chat.type == "private")
async def command_start_handler(message: Message, state: FSMContext):
    if await check_throttle(message.from_user.id, message.text):
        return
    await state.clear()

    user_id = message.from_user.id
    user_name = message.from_user.username or "NO_USERNAME"

    if user_id in config.tg_bot.admin_ids:
        await message.answer("Пришли объявление для публикации")
        return

    await DataBase.insert_user(user_id, user_name)
    await message.answer(LEXICON['select_language'], reply_markup=kb_language())


@router.callback_query(F.data.startswith('language_'))
async def process_language(callback: CallbackQuery, state: FSMContext):
    if await check_throttle(callback.from_user.id, callback.data):
        return
    
    try:
        await callback.message.delete()
    except Exception as e:
        logger.warning(f"Не удалось удалить сообщение: {e}")

    language = callback.data.split('_')[1]
    await DataBase.update_user_language(callback.from_user.id, language)
    await callback.message.answer(LEXICON[f'form_post_{language}'])


@router.message(Command(commands='select_language'), F.chat.type == "private")
async def command_select_language_handler(message: Message, state: FSMContext):
    if await check_throttle(message.from_user.id, message.text):
        return
    
    try:
        await message.delete()
    except Exception as e:
        logger.warning(f"Не удалось удалить сообщение: {e}")

    await message.answer(LEXICON['select_language'], reply_markup=kb_language())


@router.message(Command(commands='info'), F.chat.type == "private")
async def command_info_handler(message: Message, state: FSMContext):
    if await check_throttle(message.from_user.id, message.text):
        return
    
    try:
        await message.delete()
    except Exception as e:
        logger.warning(f"Не удалось удалить сообщение: {e}")

    user = await DataBase.get_user(message.from_user.id)
    if user:
        lang = user.language.value if hasattr(user.language, 'value') else user.language
        await message.answer(LEXICON[f'form_post_{lang}'])


# ==================== СООБЩЕНИЯ В ТОПИКИ ====================

@router.message(F.chat.type == "private")
async def process_user_message(message: Message, bot: Bot, album: list[Message] = None):
    """Обработка сообщений от пользователей в личке"""
    if await check_throttle(message.from_user.id, message.text):
        return
    
    user_id = message.from_user.id
    user_name = message.from_user.username or "NO_USERNAME"
    
    # Пропускаем админов - их обрабатывает admin_handlers
    if user_id in config.tg_bot.admin_ids:
        return
    
    TG_MESSAGE_GROUP_ID = config.tg_bot.tg_message_group_id
    
    try:
        thread = await ThreadORM.get_or_create_thread(user_id, user_name)
        
        if not thread:
            # Используем Redis lock для предотвращения создания дубликатов
            lock_key = f"create_topic:{user_id}"
            lock = await redis.get(lock_key)
            
            if lock:
                # Другой запрос уже создаёт топик, ждём
                await asyncio.sleep(1)
                thread = await ThreadORM.get_or_create_thread(user_id, user_name)
            else:
                # Устанавливаем блокировку
                await redis.set(lock_key, "1", ex=10)
                
                try:
                    # Ещё раз проверяем после получения блокировки
                    thread = await ThreadORM.get_or_create_thread(user_id, user_name)
                    
                    if not thread:
                        topic_name = f"@{user_name} (ID: {user_id})"
                        
                        forum_topic = await bot.create_forum_topic(
                            chat_id=TG_MESSAGE_GROUP_ID,
                            name=topic_name
                        )
                        
                        thread = await ThreadORM.get_or_create_thread(
                            user_id=user_id,
                            user_name=user_name,
                            thread_id=forum_topic.message_thread_id
                        )
                        
                        await bot.send_message(
                            chat_id=TG_MESSAGE_GROUP_ID,
                            message_thread_id=thread.thread_id,
                            text=f"🆕 Новое обращение от пользователя:\n"
                                 f"👤 Username: @{user_name}\n"
                                 f"🆔 User ID: {user_id}\n"
                                 f"📅 Время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                        )
                finally:
                    await redis.delete(lock_key)
        
        # Пересылаем сообщения (сохраняет информацию об отправителе)
        if album:
            # Пересылаем альбом целиком
            message_ids = [msg.message_id for msg in album]
            await bot.forward_messages(
                chat_id=TG_MESSAGE_GROUP_ID,
                from_chat_id=album[0].chat.id,
                message_ids=message_ids,
                message_thread_id=thread.thread_id
            )
        else:
            # Пересылаем одиночное сообщение
            await bot.forward_message(
                chat_id=TG_MESSAGE_GROUP_ID,
                from_chat_id=message.chat.id,
                message_id=message.message_id,
                message_thread_id=thread.thread_id
            )
        
        # Подтверждаем получение реакцией
        try:
            from aiogram.types import ReactionTypeEmoji
            await message.react([ReactionTypeEmoji(emoji="👍")])
        except Exception:
            pass  # Игнорируем ошибки реакции
        
    except Exception as e:
        logger.error(f"Ошибка при обработке сообщения от пользователя {user_id}: {e}")
        await message.answer("❌ Произошла ошибка при отправке сообщения. Попробуйте позже.")


# ==================== МОДЕРАЦИЯ ЧАТА ====================

@router.message(F.chat.name == config.tg_bot.name_chat)
async def process_chat_message(message: Message, bot: Bot):
    """Удаление сообщений не от админов в чате"""
    if message.from_user.id in config.tg_bot.admin_ids:
        return

    await message.delete()
    
    key = f"user:{message.from_user.id}:messages"
    user_name = message.from_user.username

    is_violation = await redis.get(key)
    if not is_violation:
        message_info = await message.answer(
            text=f'Здравствуйте! @{user_name}\nДля размещения объявления, напишите боту в личку\n @Auto_georgian_bot'
        )
        await redis.set(key, '1', ex=19)
        await asyncio.sleep(20)
        await message_info.delete()

"""
Обработчики для админов:
- Создание и публикация постов через GPT
- Ответы пользователям из топиков
"""
import asyncio
import logging
from datetime import datetime

from aiogram.fsm.context import FSMContext
from aiogram import Router, F, Bot
from aiogram.filters import StateFilter
from aiogram.types import Message, CallbackQuery, InputMediaPhoto, InputMediaVideo, InputMediaDocument, InputMediaAudio
from aiogram.fsm.state import StatesGroup, State
from aiogram.dispatcher.event.handler import SkipHandler

from app.service.openai_service import generate_post_text
from app.keybords.keybords import kb_admin_post_actions, kb_admin_cancel
from config_data.config import ConfigEnv, load_config
from s3.s3_client import upload_to_s3
from db.ORM import PostsORM, ThreadORM

config: ConfigEnv = load_config()
router = Router()
logger = logging.getLogger(__name__)

# Список admin_ids для фильтра
ADMIN_IDS = config.tg_bot.admin_ids

# ID группы для модерации и топиков
MODERATION_GROUP_ID = config.tg_bot.tg_message_group_id

# ID канала для модерации
CHANNEL_ID = config.tg_bot.channel_id
BOT_USERNAME = "Auto_georgian_bot"


# FSM состояния для работы админа с постами
class AdminPostStates(StatesGroup):
    waiting_for_text = State()  # Ожидание текста после получения медиа
    waiting_for_manual_text = State()
    waiting_for_gpt_correction = State()



# ==================== МОДЕРАЦИЯ КАНАЛА ====================

@router.message(F.chat.id == CHANNEL_ID, F.media_group_id)
async def moderate_channel_media_group(message: Message, bot: Bot, album: list[Message] = None):
    """Модерация медиагрупп в канале - удаление всех фото альбома"""
    
    user_id = message.from_user.id if message.from_user else 0
    user_name = message.from_user.username if message.from_user else "Unknown"
    
    logger.info(f"[CHANNEL_MOD] Медиагруппа от {user_id}:{user_name}")
    
    # Не удаляем сообщения от бота
    if message.from_user and message.from_user.is_bot:
        return
    
    # Не удаляем сообщения от админов
    if message.from_user and message.from_user.id in ADMIN_IDS:
        return
    
    # Не удаляем посты канала (от имени канала)
    if message.sender_chat and message.sender_chat.id == CHANNEL_ID:
        return
    
    try:
        # Собираем все message_id из альбома
        if album:
            message_ids_all = [msg.message_id for msg in album]
        else:
            message_ids_all = [message.message_id]
        
        # Удаляем все сообщения медиагруппы
        await bot.delete_messages(chat_id=CHANNEL_ID, message_ids=message_ids_all)
        logger.info(f"[CHANNEL_MOD] Удалено {len(message_ids_all)} сообщений медиагруппы от {user_id}")
        
        # Отправляем уведомление с дедупликацией через Redis
        from app.service.redis_client import redis
        
        key = f"channel_warning:{user_id}"
        is_warned = await redis.get(key)
        
        if not is_warned:
            warning_msg = await bot.send_message(
                chat_id=CHANNEL_ID,
                text=f"📢 Для размещения объявлений пишите боту @{BOT_USERNAME}",
                disable_notification=True
            )
            await redis.set(key, "1", ex=25)
            
            await asyncio.sleep(20)
            try:
                await warning_msg.delete()
            except Exception:
                pass
        
    except Exception as e:
        logger.warning(f"[CHANNEL_MOD] Ошибка модерации медиагруппы: {e}")


@router.message(F.chat.id == CHANNEL_ID)
async def moderate_channel_messages(message: Message, bot: Bot):
    """Модерация сообщений в канале - удаление и уведомление"""
    
    logger.info(f"[CHANNEL_MOD] chat_id={message.chat.id}, type={message.chat.type}")

    # Не удаляем сообщения от бота
    if message.from_user and message.from_user.is_bot:
        return
    
    # Не удаляем сообщения от админов
    if message.from_user and message.from_user.id in ADMIN_IDS:
        return
    
    # Не удаляем посты канала (от имени канала)
    if message.sender_chat and message.sender_chat.id == CHANNEL_ID:
        return
    
    # Проверяем, является ли сообщение системным (вход/выход/и т.д.)
    is_service_message = any([
        message.new_chat_members,
        message.left_chat_member,
        message.new_chat_title,
        message.new_chat_photo,
        message.delete_chat_photo,
        message.pinned_message,
        message.video_chat_started,
        message.video_chat_ended,
        message.video_chat_participants_invited,
    ])
    
    user_id = message.from_user.id if message.from_user else 0
    
    try:
        # Удаляем сообщение
        await message.delete()
        logger.info(f"[CHANNEL_MOD] Удалено сообщение от user_id={user_id}, service={is_service_message}")
        
        # Для системных сообщений не шлём уведомление
        if is_service_message:
            return
        
        # Отправляем уведомление с дедупликацией через Redis
        from app.service.redis_client import redis
        
        key = f"channel_warning:{user_id}"
        is_warned = await redis.get(key)
        
        if not is_warned:
            warning_msg = await bot.send_message(
                chat_id=CHANNEL_ID,
                text=f"📢 Для размещения объявлений пишите боту @{BOT_USERNAME}",
                disable_notification=True
            )
            await redis.set(key, "1", ex=25)  # Блокируем повторные на 25 сек
            
            # Удаляем уведомление через 20 секунд
            await asyncio.sleep(20)
            try:
                await warning_msg.delete()
            except Exception:
                pass
        
    except Exception as e:
        logger.warning(f"[CHANNEL_MOD] Ошибка модерации канала: {e}")



# ==================== СОЗДАНИЕ ПОСТОВ ====================

def extract_forward_user_id(message: Message) -> int | None:
    """Извлекает ID оригинального отправителя из пересланного сообщения"""
    if not message.forward_origin:
        return None
    
    origin = message.forward_origin
    
    # Пересылка от пользователя
    if hasattr(origin, 'sender_user') and origin.sender_user:
        return origin.sender_user.id
    
    # Пересылка из чата (группы)
    if hasattr(origin, 'sender_chat') and origin.sender_chat:
        return origin.sender_chat.id
    
    # Пересылка из канала
    if hasattr(origin, 'chat') and origin.chat:
        return origin.chat.id
    
    return None


def extract_sender_info(message: Message) -> str | None:
    """Извлекает информацию об отправителе (имя, username) из пересланного сообщения"""
    if not message.forward_origin:
        return None
    
    origin = message.forward_origin
    
    # Пересылка от пользователя
    if hasattr(origin, 'sender_user') and origin.sender_user:
        user = origin.sender_user
        parts = []
        
        # Имя
        name = user.first_name or ""
        if user.last_name:
            name += f" {user.last_name}"
        if name:
            parts.append(name)
        
        # Username
        if user.username:
            parts.append(f"@{user.username}")
            parts.append(f"https://t.me/{user.username}")
        
        return " ".join(parts) if parts else None
    
    # Пересылка из чата
    if hasattr(origin, 'sender_chat') and origin.sender_chat:
        chat = origin.sender_chat
        if chat.username:
            return f"{chat.title or ''} @{chat.username}"
        return chat.title
    
    return None


from aiogram.filters import Command

@router.message(Command("cancel"), F.chat.type == "private", F.from_user.id.in_(ADMIN_IDS))
async def admin_cancel_command(message: Message, state: FSMContext):
    """Отмена текущего действия"""
    current_state = await state.get_state()
    if current_state:
        await state.clear()
        await message.answer("✅ Действие отменено. Можешь начать заново.")
    else:
        await message.answer("Нет активного действия для отмены.")


@router.message(
    F.chat.type == "private", 
    F.from_user.id.in_(ADMIN_IDS),
    ~StateFilter(AdminPostStates.waiting_for_manual_text, AdminPostStates.waiting_for_gpt_correction)
)
async def process_admin_media(message: Message, bot: Bot, state: FSMContext, album: list[Message] = None):
    """Обработка медиа от админа для создания поста"""
    
    # Проверяем состояние вручную
    current_state = await state.get_state()
    logger.info(f"[ADMIN_MEDIA] ВХОД: state={current_state}, album={album is not None}, photo={message.photo is not None}")
    
    # Если приходит новое медиа в состоянии ожидания текста - обновляем медиа
    if current_state == AdminPostStates.waiting_for_text:
        if album or message.photo or message.video:
            logger.info("[ADMIN_MEDIA] Обновляем медиа в состоянии waiting_for_text")
            # Продолжаем обработку - заменим pending_media
        else:
            # Это текст - передаём управление process_pending_text
            logger.info("[ADMIN_MEDIA] Пропускаем текст -> process_pending_text")
            raise SkipHandler()
    
    # DEBUG: Логируем что пришло
    logger.info(f"[ADMIN_MEDIA] album={album is not None}, photo={message.photo is not None}, video={message.video is not None}")
    logger.info(f"[ADMIN_MEDIA] caption={message.caption}, text={message.text}")
    if album:
        for i, msg in enumerate(album):
            logger.info(f"[ADMIN_MEDIA] album[{i}]: caption={msg.caption}, text={msg.text}, forward={msg.forward_origin}")
    
    # Проверяем есть ли медиа (в альбоме или одиночное)
    has_media = album or message.photo or message.video
    
    if not has_media:
        # Если это текст без медиа и не команда - сохраняем как описание для следующего медиа
        if message.text and not message.text.startswith('/'):
            # Проверяем, возможно это пересланный пост с текстом
            if message.forward_origin:
                forward_user_id = extract_forward_user_id(message)
                sender_info = extract_sender_info(message)
                await state.update_data(
                    pending_text=message.text, 
                    forward_user_id=forward_user_id,
                    sender_info=sender_info
                )
                await message.answer("📝 Текст сохранён. Теперь пришли медиа (фото/видео) для объявления.")
            else:
                await message.answer("📷 Пришли медиа (фото/видео) с описанием для создания объявления")
        return
    
    await message.answer("⏳ Обрабатываю объявление...")
    
    try:
        media_file_ids = []
        original_text = ""
        forward_user_id = None
        sender_info = None  # Информация об отправителе для GPT
        
        # Получаем сохранённый текст из состояния (если был пересланный текст)
        state_data = await state.get_data()
        pending_text = state_data.get("pending_text", "")
        saved_forward_user_id = state_data.get("forward_user_id")
        saved_sender_info = state_data.get("sender_info")
        
        if album:
            for msg in album:
                if msg.photo:
                    media_file_ids.append({"type": "photo", "file_id": msg.photo[-1].file_id})
                elif msg.video:
                    media_file_ids.append({"type": "video", "file_id": msg.video.file_id})
                # Собираем текст из caption или text пересланных сообщений
                if not original_text:
                    original_text = msg.caption or msg.text or ""
                # Извлекаем информацию из пересылки
                if not forward_user_id and msg.forward_origin:
                    forward_user_id = extract_forward_user_id(msg)
                    sender_info = extract_sender_info(msg)
        else:
            if message.photo:
                media_file_ids.append({"type": "photo", "file_id": message.photo[-1].file_id})
            elif message.video:
                media_file_ids.append({"type": "video", "file_id": message.video.file_id})
            original_text = message.caption or message.text or ""
            # Извлекаем информацию из пересылки
            if message.forward_origin:
                forward_user_id = extract_forward_user_id(message)
                sender_info = extract_sender_info(message)
        
        # Если forward_user_id не найден в медиа, используем сохранённый
        if not forward_user_id and saved_forward_user_id:
            forward_user_id = saved_forward_user_id
        if not sender_info and saved_sender_info:
            sender_info = saved_sender_info
        
        # Если текст не найден в медиа, используем сохранённый
        if not original_text and pending_text:
            original_text = pending_text
            await state.update_data(pending_text=None)  # Очищаем сохранённый текст
        
        if not original_text:
            # Сохраняем медиа и просим ввести текст
            await state.set_state(AdminPostStates.waiting_for_text)
            await state.update_data(pending_media=media_file_ids, forward_user_id=forward_user_id, sender_info=sender_info)
            await message.answer(
                "📝 Медиа получено! Теперь отправь или перешли текст объявления."
            )
            return
        
        generated_text = await generate_post_text(original_text, sender_info=sender_info)
        
        # user_id - пользователь из пересылки, или админ если пересылки нет
        post_user_id = forward_user_id or message.from_user.id
        
        await state.update_data(
            media_file_ids=media_file_ids,
            original_text=original_text,
            generated_text=generated_text,
            admin_id=message.from_user.id,
            user_id=post_user_id  # ID пользователя для поста
        )
        
        if len(media_file_ids) > 1:
            media_group = []
            for i, media in enumerate(media_file_ids):
                caption = generated_text if i == 0 else None
                if media["type"] == "photo":
                    media_group.append(InputMediaPhoto(media=media["file_id"], caption=caption))
                elif media["type"] == "video":
                    media_group.append(InputMediaVideo(media=media["file_id"], caption=caption))
            await bot.send_media_group(chat_id=message.chat.id, media=media_group)
        else:
            media = media_file_ids[0]
            if media["type"] == "photo":
                await bot.send_photo(chat_id=message.chat.id, photo=media["file_id"], caption=generated_text)
            elif media["type"] == "video":
                await bot.send_video(chat_id=message.chat.id, video=media["file_id"], caption=generated_text)
        
        await message.answer("👆 Превью объявления\n\nВыбери действие:", reply_markup=kb_admin_post_actions())
        
    except Exception as e:
        logger.error(f"Ошибка при обработке медиа от админа: {e}")
        await message.answer(f"❌ Ошибка при генерации текста: {str(e)[:200]}", parse_mode=None)


@router.message(F.chat.type == "private", AdminPostStates.waiting_for_text)
async def process_pending_text(message: Message, bot: Bot, state: FSMContext):
    """Получение текста после того как медиа уже загружено"""
    
    logger.info(f"[PENDING_TEXT] Получен текст от {message.from_user.id}: {message.text[:50] if message.text else 'None'}...")
    
    # Получаем текст из сообщения
    original_text = message.text or message.caption or ""
    
    if not original_text:
        await message.answer("❌ Пришли текст объявления (текстом или пересланным сообщением)")
        return
    
    await message.answer("⏳ Генерирую текст объявления...")
    
    try:
        data = await state.get_data()
        media_file_ids = data.get("pending_media", [])
        saved_forward_user_id = data.get("forward_user_id")
        saved_sender_info = data.get("sender_info")
        
        if not media_file_ids:
            await state.clear()
            await message.answer("❌ Медиа не найдено. Начни заново — отправь фото/видео.")
            return
        
        # Извлекаем информацию из пересылки текста
        forward_user_id = None
        sender_info = None
        if message.forward_origin:
            forward_user_id = extract_forward_user_id(message)
            sender_info = extract_sender_info(message)
        
        # Используем сохранённые данные если не нашли в текущем сообщении
        if not forward_user_id:
            forward_user_id = saved_forward_user_id
        if not sender_info:
            sender_info = saved_sender_info
        
        # user_id - пользователь из пересылки, или админ если пересылки нет
        post_user_id = forward_user_id or message.from_user.id
        
        # Генерируем текст через GPT с информацией об отправителе
        generated_text = await generate_post_text(original_text, sender_info=sender_info)
        
        # Сохраняем данные
        await state.set_state(None)
        await state.update_data(
            media_file_ids=media_file_ids,
            original_text=original_text,
            generated_text=generated_text,
            admin_id=message.from_user.id,
            user_id=post_user_id,  # ID пользователя для поста
            pending_media=None
        )
        
        # Отправляем превью
        if len(media_file_ids) > 1:
            media_group = []
            for i, media in enumerate(media_file_ids):
                caption = generated_text if i == 0 else None
                if media["type"] == "photo":
                    media_group.append(InputMediaPhoto(media=media["file_id"], caption=caption))
                elif media["type"] == "video":
                    media_group.append(InputMediaVideo(media=media["file_id"], caption=caption))
            await bot.send_media_group(chat_id=message.chat.id, media=media_group)
        else:
            media = media_file_ids[0]
            if media["type"] == "photo":
                await bot.send_photo(chat_id=message.chat.id, photo=media["file_id"], caption=generated_text)
            elif media["type"] == "video":
                await bot.send_video(chat_id=message.chat.id, video=media["file_id"], caption=generated_text)
        
        await message.answer("👆 Превью объявления\n\nВыбери действие:", reply_markup=kb_admin_post_actions())
        
    except Exception as e:
        logger.error(f"Ошибка при обработке текста: {e}")
        await state.clear()
        await message.answer(f"❌ Ошибка: {str(e)[:200]}", parse_mode=None)


@router.callback_query(F.data == "admin_post_publish")
async def admin_publish_post(callback: CallbackQuery, bot: Bot, state: FSMContext):
    """Публикация поста в канал"""
    data = await state.get_data()
    
    if not data.get("media_file_ids"):
        await callback.answer("❌ Нет данных для публикации", show_alert=True)
        return
    
    await callback.message.edit_text("⏳ Публикую пост...")
    
    try:
        media_file_ids = data["media_file_ids"]
        post_text = data.get("generated_text") or data.get("manual_text", "")
        admin_id = data.get("admin_id")
        
        s3_keys = []
        for i, media in enumerate(media_file_ids):
            file = await bot.get_file(media["file_id"])
            file_bytes = await bot.download_file(file.file_path)
            
            ext = "jpg" if media["type"] == "photo" else "mp4"
            file_name = f"posts/{admin_id}/{datetime.now().strftime('%Y%m%d_%H%M%S')}_{i}.{ext}"
            
            s3_key = await upload_to_s3(file_bytes, file_name)
            if s3_key:
                s3_keys.append(s3_key)
        
        channel_id = config.tg_bot.channel_id
        
        post_id = 0
        post_message_ids = []
        
        if len(media_file_ids) > 1:
            media_group = []
            for i, media in enumerate(media_file_ids):
                caption = post_text if i == 0 else None
                if media["type"] == "photo":
                    media_group.append(InputMediaPhoto(media=media["file_id"], caption=caption))
                elif media["type"] == "video":
                    media_group.append(InputMediaVideo(media=media["file_id"], caption=caption))
            
            sent_messages = await bot.send_media_group(chat_id=channel_id, media=media_group)
            # Сохраняем ВСЕ message_id для медиагруппы
            post_message_ids = [msg.message_id for msg in sent_messages]
            post_id = post_message_ids[0] if post_message_ids else 0
        else:
            media = media_file_ids[0]
            if media["type"] == "photo":
                sent_msg = await bot.send_photo(chat_id=channel_id, photo=media["file_id"], caption=post_text)
            else:
                sent_msg = await bot.send_video(chat_id=channel_id, video=media["file_id"], caption=post_text)
            post_id = sent_msg.message_id
            post_message_ids = [post_id]
        
        # user_id - пользователь из пересылки, admin_id - кто публиковал
        user_id = data.get("user_id") or admin_id
        
        await PostsORM.create_post(
            user_id=user_id,
            post_id=post_id,
            post_message_ids=post_message_ids,
            post_text=post_text,
            post_media_list=s3_keys,
            admin_id=admin_id
        )
        
        await state.clear()
        await callback.message.edit_text(
            f"✅ Пост успешно опубликован!\n\n"
            f"📢 Канал: {config.tg_bot.channel_url}\n"
            f"🆔 ID поста: {post_id}"
        )
        
    except Exception as e:
        logger.error(f"Ошибка при публикации поста: {e}")
        await callback.message.edit_text(f"❌ Ошибка при публикации: {str(e)[:200]}", parse_mode=None)


@router.callback_query(F.data == "admin_post_manual")
async def admin_manual_input(callback: CallbackQuery, state: FSMContext):
    """Переход в режим ручного ввода текста"""
    await state.set_state(AdminPostStates.waiting_for_manual_text)
    await callback.message.edit_text(
        "✏️ Введи текст объявления вручную:\n\n"
        "Отправь текст, который хочешь использовать для публикации.",
        reply_markup=kb_admin_cancel()
    )


@router.message(StateFilter(AdminPostStates.waiting_for_manual_text), F.text)
async def admin_receive_manual_text(message: Message, bot: Bot, state: FSMContext):
    """Получение ручного текста от админа"""
    manual_text = message.text
    data = await state.get_data()
    
    await state.update_data(generated_text=manual_text, manual_text=manual_text)
    await state.set_state(None)
    
    media_file_ids = data.get("media_file_ids", [])
    
    if media_file_ids:
        if len(media_file_ids) > 1:
            media_group = []
            for i, media in enumerate(media_file_ids):
                caption = manual_text if i == 0 else None
                if media["type"] == "photo":
                    media_group.append(InputMediaPhoto(media=media["file_id"], caption=caption))
                elif media["type"] == "video":
                    media_group.append(InputMediaVideo(media=media["file_id"], caption=caption))
            await bot.send_media_group(chat_id=message.chat.id, media=media_group)
        else:
            media = media_file_ids[0]
            if media["type"] == "photo":
                await bot.send_photo(chat_id=message.chat.id, photo=media["file_id"], caption=manual_text)
            elif media["type"] == "video":
                await bot.send_video(chat_id=message.chat.id, video=media["file_id"], caption=manual_text)
    
    await message.answer("👆 Превью с новым текстом\n\nВыбери действие:", reply_markup=kb_admin_post_actions())


@router.callback_query(F.data == "admin_post_gpt_correct")
async def admin_gpt_correction(callback: CallbackQuery, state: FSMContext):
    """Переход в режим корректировки через GPT"""
    await state.set_state(AdminPostStates.waiting_for_gpt_correction)
    await callback.message.edit_text(
        "💬 Введи комментарий для GPT:\n\n"
        "Например:\n"
        "- «Сделай текст короче»\n"
        "- «Добавь больше эмодзи»\n"
        "- «Укажи что торг уместен»",
        reply_markup=kb_admin_cancel()
    )


@router.message(StateFilter(AdminPostStates.waiting_for_gpt_correction), F.text)
async def admin_receive_gpt_correction(message: Message, bot: Bot, state: FSMContext):
    """Получение комментария для корректировки через GPT"""
    correction = message.text
    data = await state.get_data()
    
    await message.answer("⏳ Корректирую текст через GPT...")
    
    try:
        original_text = data.get("original_text", "")
        current_text = data.get("generated_text", original_text)
        
        new_text = await generate_post_text(current_text, correction)
        
        await state.update_data(generated_text=new_text)
        await state.set_state(None)
        
        media_file_ids = data.get("media_file_ids", [])
        
        if media_file_ids:
            if len(media_file_ids) > 1:
                media_group = []
                for i, media in enumerate(media_file_ids):
                    caption = new_text if i == 0 else None
                    if media["type"] == "photo":
                        media_group.append(InputMediaPhoto(media=media["file_id"], caption=caption))
                    elif media["type"] == "video":
                        media_group.append(InputMediaVideo(media=media["file_id"], caption=caption))
                await bot.send_media_group(chat_id=message.chat.id, media=media_group)
            else:
                media = media_file_ids[0]
                if media["type"] == "photo":
                    await bot.send_photo(chat_id=message.chat.id, photo=media["file_id"], caption=new_text)
                elif media["type"] == "video":
                    await bot.send_video(chat_id=message.chat.id, video=media["file_id"], caption=new_text)
        
        await message.answer("👆 Превью с обновленным текстом\n\nВыбери действие:", reply_markup=kb_admin_post_actions())
        
    except Exception as e:
        logger.error(f"Ошибка при корректировке текста: {e}")
        await message.answer(f"❌ Ошибка при корректировке: {str(e)[:200]}", parse_mode=None)
        await state.set_state(None)


@router.callback_query(F.data == "admin_post_cancel")
async def admin_cancel_post(callback: CallbackQuery, state: FSMContext):
    """Отмена создания поста"""
    await state.clear()
    await callback.message.edit_text("❌ Создание поста отменено.\n\nПришли новое объявление для публикации.")


# ==================== ОТВЕТЫ В ТОПИКАХ ====================

@router.message(
    F.chat.type == "supergroup",
    F.chat.id == MODERATION_GROUP_ID,
    F.from_user.id.in_(ADMIN_IDS),
    F.message_thread_id.is_not(None)  # Только в топиках
)
async def process_admin_reply(message: Message, bot: Bot, album: list[Message] = None):
    """Обработка ответов админа из топика группы"""
    logger.info(f"[ADMIN_REPLY] Получено сообщение от админа: thread_id={message.message_thread_id}")
    
    user_id = await ThreadORM.get_user_by_thread_id(message.message_thread_id)
    logger.info(f"[ADMIN_REPLY] Найден user_id={user_id} для thread_id={message.message_thread_id}")
    
    if not user_id:
        await message.reply("❌ Не найден пользователь для этого топика")
        return
    
    try:
        if album:
            media_group = []
            for i, msg in enumerate(album):
                caption = msg.caption if i == 0 else None
                
                if msg.photo:
                    media_group.append(InputMediaPhoto(media=msg.photo[-1].file_id, caption=caption))
                elif msg.video:
                    media_group.append(InputMediaVideo(media=msg.video.file_id, caption=caption))
                elif msg.document:
                    media_group.append(InputMediaDocument(media=msg.document.file_id, caption=caption))
                elif msg.audio:
                    media_group.append(InputMediaAudio(media=msg.audio.file_id, caption=caption))
            
            if media_group:
                await bot.send_media_group(chat_id=user_id, media=media_group)
        
        elif message.text:
            await bot.send_message(chat_id=user_id, text=message.text)
        elif message.photo:
            await bot.send_photo(chat_id=user_id, photo=message.photo[-1].file_id, caption=message.caption)
        elif message.video:
            await bot.send_video(chat_id=user_id, video=message.video.file_id, caption=message.caption)
        elif message.document:
            await bot.send_document(chat_id=user_id, document=message.document.file_id, caption=message.caption)
        elif message.voice:
            await bot.send_voice(chat_id=user_id, voice=message.voice.file_id, caption=message.caption)
        elif message.audio:
            await bot.send_audio(chat_id=user_id, audio=message.audio.file_id, caption=message.caption)
        elif message.sticker:
            await bot.send_sticker(chat_id=user_id, sticker=message.sticker.file_id)
        
        # Подтверждаем отправку реакцией
        try:
            from aiogram.types import ReactionTypeEmoji
            await message.react([ReactionTypeEmoji(emoji="✅")])
        except Exception as react_error:
            logger.warning(f"Не удалось поставить реакцию: {react_error}")
        
    except Exception as e:
        logger.error(f"Ошибка при отправке сообщения пользователю {user_id}: {e}")
        await message.reply(f"❌ Ошибка при отправке: {str(e)[:100]}", parse_mode=None)


# ==================== МОДЕРАЦИЯ ГРУППЫ ====================

@router.message(
    F.chat.id == MODERATION_GROUP_ID,
    F.from_user.id.not_in(ADMIN_IDS),
    ~F.from_user.is_bot  # Не удаляем сообщения от ботов (включая себя)
)
async def delete_non_admin_messages(message: Message):
    """Удаление сообщений от не-админов в группе"""
    try:
        await message.delete()
        logger.info(f"[MODERATION] Удалено сообщение от user_id={message.from_user.id} в группе")
    except Exception as e:
        logger.warning(f"[MODERATION] Не удалось удалить сообщение: {e}")


@router.message(
    F.chat.id == MODERATION_GROUP_ID,
    F.content_type.in_({
        "new_chat_members",
        "left_chat_member",
        "new_chat_title",
        "new_chat_photo",
        "delete_chat_photo",
        "pinned_message",
        "proximity_alert_triggered",
        "forum_topic_created",
        "forum_topic_closed",
        "forum_topic_reopened",
        "forum_topic_edited",
        "general_forum_topic_hidden",
        "general_forum_topic_unhidden",
        "video_chat_scheduled",
        "video_chat_started",
        "video_chat_ended",
        "video_chat_participants_invited",
    })
)
async def delete_service_messages(message: Message):
    """Удаление сервисных сообщений в группе"""
    try:
        await message.delete()
        logger.info(f"[MODERATION] Удалено сервисное сообщение типа {message.content_type}")
    except Exception as e:
        logger.warning(f"[MODERATION] Не удалось удалить сервисное сообщение: {e}")


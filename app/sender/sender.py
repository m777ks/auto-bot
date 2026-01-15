import asyncio
import json
import logging
import os
import time

from aiogram import F, Bot, Router, types
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, FSInputFile
from aiogram.utils.media_group import MediaGroupBuilder
from config_data.config import ConfigEnv, load_config
from aiogram.filters import Command, StateFilter
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from app.middlewares.album_middleware import AlbumMiddleware
from aiogram.fsm.storage.redis import Redis

from db.ORM import DataBase

logger = logging.getLogger(__name__)
config: ConfigEnv = load_config()

# Список администраторов
ADMIN_IDS = config.tg_bot.admin_ids

router = Router()
router.message.middleware(AlbumMiddleware(0.5, ADMIN_IDS))
admin_ids = ADMIN_IDS

class FSMFillForm(StatesGroup):
    SEND_type = State()
    SEND_ids = State()
    SEND_text = State()
    SEND_process = State()

@router.message(Command(commands="start_mailing"), StateFilter(FSMFillForm.SEND_process))
async def start_mailing_process(message: types.Message):
    if message.from_user.id not in admin_ids:
        logger.warning(
            f"Попытка несанкционированного доступа от пользователя {message.from_user.id}:{message.from_user.username}")
        await message.reply("У вас нет прав для выполнения этой команды.")
        return
    await message.answer("Рассылка уже запущена")



# Главная команда для начала рассылки
@router.message(Command(commands="start_mailing"))
async def start_mailing(message: types.Message):
    if message.from_user.id not in admin_ids:
        logger.warning(
            f"Попытка несанкционированного доступа от пользователя {message.from_user.id}:{message.from_user.username}")
        await message.reply("У вас нет прав для выполнения этой команды.")
        return

    logger.info(f"Начата новая рассылка администратором {message.from_user.id}:{message.from_user.username}")
    # Создаём кнопки
    button_1 = InlineKeyboardButton(text="Отправить избранным", callback_data="send_selected")
    button_2 = InlineKeyboardButton(text="Отправить всем", callback_data="send_all")
    button_3 = InlineKeyboardButton(text="Исключить ID", callback_data="exclude_ids")

    # Создаём клавиатуру и добавляем кнопки
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[button_1], [button_2], [button_3]])
    await message.reply("Выберите, кому вы хотите отправить сообщение:", reply_markup=keyboard)


@router.message(Command(commands="reset"))
async def reset_state(message: types.Message, state: FSMContext):
    await state.clear()
    logger.info(f"Состояние сброшено пользователем {message.from_user.id}:{message.from_user.username}")


# Обработка выбора рассылки
@router.callback_query(lambda c: c.data in ["send_selected", "send_all", "exclude_ids"])
async def select_recipients(callback: types.CallbackQuery, state: FSMContext):
    logger.info(
        f"Выбран тип рассылки '{callback.data}' пользователем {callback.from_user.id}:{callback.from_user.username}")
    await state.set_state(FSMFillForm.SEND_type)
    await state.update_data(type=callback.data)

    if callback.data == "send_selected":
        await callback.message.reply("Введите ID пользователей через запятую, которым хотите отправить сообщение:")
        await state.set_state(FSMFillForm.SEND_ids)
    elif callback.data == "exclude_ids":
        await callback.message.reply("Введите ID пользователей через запятую, которых хотите исключить из рассылки:")
        await state.set_state(FSMFillForm.SEND_ids)
    else:
        await callback.message.reply("Введите сообщение для рассылки:")
        await state.set_state(FSMFillForm.SEND_text)
        await state.update_data(type=callback.data)


# Обработка ввода ID (для избранных или исключённых)
@router.message(StateFilter(FSMFillForm.SEND_ids))
async def process_ids(message: types.Message, state: FSMContext):
    await state.set_state(FSMFillForm.SEND_ids)
    ids = [int(user_id.strip()) for user_id in message.text.split(",") if user_id.strip().isdigit()]
    await state.update_data(ids=ids)
    await message.reply("Введите сообщение для рассылки:")
    await state.set_state(FSMFillForm.SEND_text)


@router.message(StateFilter(FSMFillForm.SEND_text), F.media_group_id)
async def accept_photos(message: types.Message, bot: Bot, state: FSMContext, album: list = None):
    logger.info(
        f"Получена медиагруппа от {message.from_user.id}:{message.from_user.username}. Количество файлов: {len(album)}")

    try:
        # Собираем информацию о медиафайлах
        media_messages = []

        for msg in album:
            media_info = {
                'caption': msg.caption,
                'media_group_id': msg.media_group_id
            }

            if msg.photo:
                media_info['type'] = 'photo'
                media_info['file_id'] = msg.photo[-1].file_id
            elif msg.video:
                media_info['type'] = 'video'
                media_info['file_id'] = msg.video.file_id
            elif msg.document:
                media_info['type'] = 'document'
                media_info['file_id'] = msg.document.file_id

            media_messages.append(media_info)

        # Сохраняем информацию о медиагруппе в состояние
        await state.update_data(media_messages=media_messages)

        # Создаем медиагруппу для предпросмотра
        preview_group = MediaGroupBuilder(caption=media_messages[0].get('caption', None))

        for media in media_messages:
            preview_group.add(
                type=media['type'],
                media=media['file_id'],
                caption=media.get('caption')
            )

        # Отправляем предпросмотр
        await message.answer_media_group(media=preview_group.build())

        # Создаем кнопки подтверждения
        btn_yes = InlineKeyboardButton(text="Да", callback_data="yes")
        btn_no = InlineKeyboardButton(text="Нет", callback_data="no")
        keyboard = InlineKeyboardMarkup(inline_keyboard=[[btn_yes], [btn_no]])

        await message.answer(
            "Вы уверены, что хотите отправить эту медиагруппу?\n\n"
            "Выберите 'Да' для подтверждения или 'Нет' для отмены.",
            reply_markup=keyboard
        )

        logger.info(f'Пришла медиагруппа от пользователя {message.from_user.id}:{message.from_user.username}')
        logger.debug(f"Медиагруппа успешно обработана и сохранена в состояние")
    except Exception as e:
        logger.error(f"Ошибка при обработке медиагруппы: {e}", exc_info=True)
        await message.reply("Произошла ошибка при обработке медиафайлов. Пожалуйста, попробуйте снова.")
        return


# Обработка ввода сообщения
@router.message(StateFilter(FSMFillForm.SEND_text))
async def process_message(message: types.Message, state: FSMContext):
    logger.info(f"Получено сообщение для рассылки от {message.from_user.id}:{message.from_user.username}")

    try:
        await state.set_state(FSMFillForm.SEND_text)

        # Сохраняем всю информацию о сообщении
        message_data = {
            'text': message.text,
            'photo': message.photo[-1].file_id if message.photo else None,
            'video': message.video.file_id if message.video else None,
            'document': message.document.file_id if message.document else None,
            'audio': message.audio.file_id if message.audio else None,
            'voice': message.voice.file_id if message.voice else None,
            'caption': message.caption,
        }

        await state.update_data(message_data=message_data)

        # Формируем текст подтверждения
        confirm_text = "Вы уверены, что хотите отправить это сообщение?\n\n"
        if message.photo:
            confirm_text += "Фото"
            if message.caption:
                confirm_text += f" с подписью: {message.caption}"
        elif message.video:
            confirm_text += "Видео"
            if message.caption:
                confirm_text += f" с подписью: {message.caption}"
        elif message.document:
            confirm_text += "Документ"
            if message.caption:
                confirm_text += f" с подписью: {message.caption}"
        elif message.text:
            confirm_text += f"Текст: {message.text}"

        confirm_text += "\n\nВыберите 'Да' для подтверждения или 'Нет' для отмены."
        btn_yes = InlineKeyboardButton(text="Да", callback_data="SEND_yes")
        btn_no = InlineKeyboardButton(text="Нет", callback_data="SEND_no")
        keyboard = InlineKeyboardMarkup(inline_keyboard=[[btn_yes], [btn_no]])

        # Отправляем пользователю его сообщение для предварительного просмотра

        if message.photo:
            await message.reply_photo(
                photo=message.photo[-1].file_id,
                caption=message.caption
            )
        elif message.video:
            await message.reply_video(
                video=message.video.file_id,
                caption=message.caption
            )
        elif message.document:
            await message.reply_document(
                document=message.document.file_id,
                caption=message.caption
            )
        elif message.audio:
            await message.reply_audio(
                audio=message.audio.file_id,
                caption=message.caption
            )
        elif message.voice:
            await message.reply_voice(
                voice=message.voice.file_id,
                caption=message.caption
            )
        elif message.text:
            await message.reply(message.text)

        await message.reply(confirm_text, reply_markup=keyboard)
        logger.debug(f"Сообщение успешно обработано и сохранено в состояние")
    except Exception as e:
        logger.error(f"Ошибка при обработке сообщения: {e}", exc_info=True)
        await message.reply("Произошла ошибка при обработке сообщения. Пожалуйста, попробуйте снова.")
        return


# Подтверждение рассылки
@router.callback_query(lambda c: c.data in ["SEND_yes", "SEND_no"])
async def confirm_mailing(callback: types.CallbackQuery, state: FSMContext, bot: Bot):
    await callback.message.delete()
    if callback.data == "SEND_no":
        logger.info(f"Рассылка отменена пользователем {callback.from_user.id}:{callback.from_user.username}")
        await callback.message.answer("Рассылка отменена.")
        await state.clear()
        return

    await state.set_state(FSMFillForm.SEND_process)
    logger.info(f"Начата рассылка от пользователя {callback.from_user.id}:{callback.from_user.username}")
    mailing_data = await state.get_data()

    # Логируем тип рассылки и количество получателей
    recipient_ids = []
    if mailing_data["type"] == "send_all":
        recipient_ids = await DataBase.get_all_user_ids()
        logger.info(f"Тип рассылки: всем пользователям. Количество получателей: {len(recipient_ids)}")
    elif mailing_data["type"] == "send_selected":
        recipient_ids = mailing_data["ids"]
        logger.info(f"Тип рассылки: выбранным пользователям. Количество получателей: {len(recipient_ids)}")
    elif mailing_data["type"] == "exclude_ids":
        all_ids = await DataBase.get_all_user_ids()
        recipient_ids = [user_id for user_id in all_ids if user_id not in mailing_data["ids"]]
        logger.info(f"Тип рассылки: всем кроме исключенных. Количество получателей: {len(recipient_ids)}")

    await callback.message.answer(
        f"Начата рассылка от пользователя {callback.from_user.id}:{callback.from_user.username}\nТип рассылки: всем пользователям. Количество получателей: {len(recipient_ids)}")

    mailing_data = mailing_data['message_data']

    success_count = 0
    error_count = 0
    start_time = time.time()
    for user_id in recipient_ids:
        try:
            if 'media_messages' in mailing_data:
                # Используем MediaGroupBuilder для медиагрупп
                media_group = MediaGroupBuilder(caption=mailing_data['media_messages'][0].get('caption'))
                for media in mailing_data['media_messages']:
                    media_group.add(
                        type=media['type'],
                        media=media['file_id']
                    )
                await bot.send_media_group(user_id, media=media_group.build())
            elif mailing_data.get('photo'):
                await bot.send_photo(user_id, mailing_data['photo'], caption=mailing_data.get('caption'))
            elif mailing_data.get('video'):
                await bot.send_video(user_id, mailing_data['video'], caption=mailing_data.get('caption'))
            elif mailing_data.get('document'):
                await bot.send_document(user_id, mailing_data['document'], caption=mailing_data.get('caption'))
            elif mailing_data.get('audio'):
                await bot.send_audio(user_id, mailing_data['audio'], caption=mailing_data.get('caption'))
            elif mailing_data.get('voice'):
                await bot.send_voice(user_id, mailing_data['voice'], caption=mailing_data.get('caption'))
            elif mailing_data.get('text'):
                await bot.send_message(user_id, mailing_data['text'])
            success_count += 1
            logger.debug(f"Успешная отправка пользователю {user_id}")

            await asyncio.sleep(0.5)
        except Exception as e:
            error_count += 1

            logger.info(f"Ошибка при отправке пользователю {user_id}: {e}")

    end_time = time.time()
    duration = end_time - start_time

    logger.info(f"Рассылка завершена. Успешно: {success_count}, Ошибок: {error_count}, Время: {duration:.2f} сек.")
    await callback.message.answer(
        f"Рассылка завершена.\n"
        f"Успешно отправлено: {success_count}\n"
        f"Ошибок: {error_count}\n"
        f"Время выполнения: {duration:.2f} сек."
    )
    await state.clear()




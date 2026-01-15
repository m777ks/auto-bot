import os

from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton, WebAppInfo
from app.lexicon.lexicon import LEXICON
from config_data.config import load_config, ConfigEnv


config: ConfigEnv = load_config()



def kb_language() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=LEXICON['language_ru'], callback_data='language_ru')],
        [InlineKeyboardButton(text=LEXICON['language_en'], callback_data='language_en')],
        [InlineKeyboardButton(text=LEXICON['language_ge'], callback_data='language_ge')],
    ])


def kb_admin_post_actions() -> InlineKeyboardMarkup:
    """Клавиатура для действий с постом админа"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Пост в группу", callback_data="admin_post_publish")],
        [InlineKeyboardButton(text="✏️ Ручной ввод", callback_data="admin_post_manual")],
        [InlineKeyboardButton(text="💬 Ввод комента для GPT", callback_data="admin_post_gpt_correct")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="admin_post_cancel")],
    ])


def kb_admin_cancel() -> InlineKeyboardMarkup:
    """Клавиатура отмены"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data="admin_post_cancel")],
    ])
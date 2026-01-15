from aiogram import Bot
from aiogram.types import BotCommand, BotCommandScopeAllPrivateChats, BotCommandScopeDefault

LEXICON_COMMANDS: dict[str, str] = {
    '/start': 'start',
    '/info': 'info',
    '/select_language': 'select_language',
}


# Функция для настройки кнопки Menu бота
async def set_main_menu(bot: Bot):
    main_menu_commands = [BotCommand(
        command=command,
        description=description) for command, description in LEXICON_COMMANDS.items()]
    # Удаляем команды для всех чатов (групп и личных)
    await bot.delete_my_commands()

    await bot.set_my_commands(commands=main_menu_commands, scope=BotCommandScopeAllPrivateChats())
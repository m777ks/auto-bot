import logging
from openai import AsyncOpenAI
from config_data.config import ConfigEnv, load_config

config: ConfigEnv = load_config()
logger = logging.getLogger(__name__)

client = AsyncOpenAI(api_key=config.openai.api_key)

SYSTEM_PROMPT = """Ты — помощник по созданию объявлений о продаже автомобилей для Telegram-канала.

Твоя задача: на основе присланного текста составить объявление СТРОГО по следующему шаблону:

[Марка] [Модель] [Комплектация]
Year: [год]
Mileage: [пробег] km
VIN: [вин-номер]
Engine: [объем] [тип двигателя]
Drive: [привод]
City: [город]

[Описание состояния - 2-8 предложений]

💵 [цена]
📞 [контакты]

ВАЖНЫЕ ПРАВИЛА:
1. Используй ТОЛЬКО информацию из присланного текста
2. Если информации НЕТ — ПРОПУСТИ эту строку полностью (не пиши шаблон!)
3. НЕ ВЫДУМЫВАЙ контакты — если телефон/username не указаны, пропусти строку 📞
4. Цена может быть в $, € или других валютах — сохраняй как есть
5. Тип двигателя на английском: turbo, diesel, hybrid, electric
6. Привод: FWD, RWD, AWD, 4WD
7. Описание кратко на русском
8. Отвечай ТОЛЬКО готовым объявлением
9. НЕ добавляй эмодзи кроме 💵 и 📞

Пример готового объявления:
Audi Q7 Premium Plus 45+
Year: 2022
Mileage: 49000 km
VIN: WA1LJBF79ND017836
Engine: 2.0 turbo
Drive: AWD Quattro
City: Tbilisi

Машина в отличном состоянии. Полностью обслужен мотор, бодро едет.
Комплектация с круиз-контролем и мультимедиа.

💵 3700€
📞 +38269123456 @username
"""


async def generate_post_text(
    user_text: str, 
    correction: str = None,
    sender_info: str = None
) -> str:
    """
    Генерирует текст объявления с помощью GPT-4o-mini
    
    Args:
        user_text: Исходный текст от пользователя
        correction: Дополнительные указания для корректировки
        sender_info: Информация об отправителе (имя, username)
        
    Returns:
        Сгенерированный текст объявления
    """
    try:
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT}
        ]
        
        # Формируем текст с информацией об отправителе
        full_text = user_text
        if sender_info:
            full_text += f"\n\nКонтакт отправителя: {sender_info}"
        
        if correction:
            messages.append({
                "role": "user", 
                "content": f"Исходный текст объявления:\n{full_text}\n\nДополнительные указания для корректировки:\n{correction}"
            })
        else:
            messages.append({
                "role": "user",
                "content": full_text
            })
        
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            temperature=0.7,
            max_tokens=1000
        )
        
        return response.choices[0].message.content
        
    except Exception as e:
        logger.error(f"Ошибка при генерации текста через OpenAI: {e}")
        raise e



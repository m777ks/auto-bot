"""
Модуль для инициализации Redis клиента.
Используется для избежания циклических импортов.
"""
from aiogram.fsm.storage.redis import Redis
from config_data.config import ConfigEnv, load_config

config: ConfigEnv = load_config()

redis = Redis(
    host=config.redis.host,
    port=config.redis.port,
    password=config.redis.password
)

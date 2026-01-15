from dataclasses import dataclass
from environs import Env


@dataclass
class TgBot:
    token: str
    admin_ids: list[int]
    channel_id: int
    channel_url: str
    tg_message_group_id: int
    name_chat: str


@dataclass
class Postgres:
    host: str
    port: int
    user: str
    password: str
    database: str

@dataclass
class S3:
    key_id: str
    key_secret: str
    url: str
    name: str

@dataclass
class Redis:
    host: str
    port: int
    password: str

@dataclass
class OPENAI:
    api_key: str

@dataclass
class ConfigEnv:
    tg_bot: TgBot
    postgres: Postgres
    redis: Redis
    s3: S3
    openai: OPENAI

def load_config(path: str | None = None) -> ConfigEnv:
    env = Env()
    env.read_env(path)
    return ConfigEnv(
        tg_bot=TgBot(
            token=env('BOT_TOKEN'),
            admin_ids=list(map(int, env.list('ADMIN_IDS'))),
            channel_id=int(env('TG_CHANNEL_ID')),
            channel_url=env('TG_CHANNEL_URL'),
            tg_message_group_id=int(env('TG_MESSAGE_GROUP_ID')),
            name_chat=env('NAME_CHAT'),
        ),
        postgres=Postgres(
            host=env('POSTGRES_HOST'),
            port=env('POSTGRES_PORT'),
            user=env('POSTGRES_USER'),
            password=env('POSTGRES_PASSWORD'),
            database=env('POSTGRES_DB'),
        ),
        redis=Redis(
            host=env('REDIS_HOST'),
            port=env('REDIS_PORT'),
            password=env('REDIS_PASSWORD'),
        ),
        s3=S3(
            key_id=env('S3_ACCESS'),
            key_secret=env('S3_SECRET'),
            url=env('S3_ENDPOINT'),
            name=env('S3_BUCKET')
        ),
        openai=OPENAI(
            api_key=env('OPENAI_API_KEY')
        ),
    )
config: ConfigEnv = load_config()


def DATABASE_URL_asyncpg():
    """
    Формирует URL подключения для asyncpg
    """
    return f'postgresql+asyncpg://{config.postgres.user}:{config.postgres.password}@{config.postgres.host}:{config.postgres.port}/{config.postgres.database}'


def DATABASE_URL_psycorg():
    """
    Формирует URL подключения для psycopg
    """
    return f'postgresql+psycopg://{config.postgres.user}:{config.postgres.password}@{config.postgres.host}:{config.postgres.port}/{config.postgres.database}'

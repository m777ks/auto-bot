from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.orm import sessionmaker

from config_data.config import DATABASE_URL_psycorg, DATABASE_URL_asyncpg

# Синхронный движок и сессия
engine = create_engine(DATABASE_URL_psycorg(), echo=False)
session_factory = sessionmaker(bind=engine)

# асинхронный движок и сессия
async_engine = create_async_engine(
    url=DATABASE_URL_asyncpg(),
    echo=False
)
session_factory_async = async_sessionmaker(async_engine, expire_on_commit=False)

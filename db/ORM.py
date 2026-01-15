import logging
import random
from datetime import datetime, timedelta, timezone
import re
from typing import Optional

from sqlalchemy.orm import joinedload

from db.database import *
from db.models import *
from sqlalchemy.future import select
from sqlalchemy import update, delete, func, insert
from sqlalchemy.exc import IntegrityError
from config_data.config import ConfigEnv, load_config

config: ConfigEnv = load_config()

# Инициализируем логгер
logger = logging.getLogger(__name__)


class LoggerORM:

    @staticmethod
    async def create_log(user_id, user_name, action, type):
        """
        Создание лога в базе данных
        """
        async with session_factory_async() as session:
            new_log = Logger(user_id=user_id, user_name=user_name, action=action, type=type)
            session.add(new_log)
            await session.commit()


class DataBase:
    @staticmethod
    async def insert_user(user_id: int, user_name: str):
        """Добавляет нового пользователя в БД или обновляет данные существующего"""
        async with session_factory_async() as session:
            # Проверка, существует ли пользователь
            query = select(Users).filter(Users.user_id == user_id)
            result = await session.execute(query)
            user = result.scalar_one_or_none()

            if user:
                return user
            else:
                # Если пользователь не найден, создаем нового
                user = Users(
                    user_id=user_id,
                    user_name=user_name,
                )
                session.add(user)

            # Сохраняем изменения
            try:
                await session.commit()
                logger.info(f"Пользователь {user_id} успешно добавлен в базу данных")
                return user
            except IntegrityError as e:
                logger.error(f"Error inserting user: {e}")
                await session.rollback()
                return False
            return True


    @staticmethod
    async def get_all_users():
        """Возвращает все записи из таблицы users."""
        async with session_factory_async() as session:
            try:
                query = select(Users)
                result = await session.execute(query)
                users = result.scalars().all()
                return users
            except Exception as e:
                logger.error(f"Ошибка при получении пользователей: {e}")
                return []


    @staticmethod
    async def get_all_user_ids():
        """
        Получает список всех ID пользователей из базы данных.
        :return: Список ID пользователей.
        """
        async with session_factory_async() as session:
            try:
                # Выполняем запрос к базе данных
                query = select(Users.user_id)
                result = await session.execute(query)

                # Извлекаем все ID из результата
                user_ids = result.scalars().all()  # .scalars() возвращает плоский список значений

                return user_ids
            except Exception as e:
                # Логируем ошибку и возвращаем пустой список
                logger.error(f"Ошибка при получении ID пользователей: {e}")
                return []

    @staticmethod
    async def get_user(user_id: int):
        """Получает пользователя по ID"""
        async with session_factory_async() as session:
            query = select(Users).filter(Users.user_id == user_id)
            result = await session.execute(query)
            return result.scalar_one_or_none()

    @staticmethod
    async def delete_user(user_id: int) -> bool:
        """
        Удаляет пользователя из базы данных по user_id.
        Также удаляет все записи конструктора этого пользователя.
        Возвращает True, если пользователь был удалён, иначе False.
        """
        async with session_factory_async() as session:
            try:
                query = select(Users).filter(Users.user_id == user_id)
                result = await session.execute(query)
                user = result.scalar_one_or_none()

                if not user:
                    return False

                await session.delete(user)
                await session.commit()
                return True

            except Exception as e:
                await session.rollback()
                logger.error(f"[DB] Ошибка при удалении пользователя {user_id}: {e}")
                return False

    @staticmethod
    async def update_user_language(user_id: int, language: str):
        """Обновляет язык пользователя"""
        async with session_factory_async() as session:
            try:
                query = (
                    update(Users)
                    .where(Users.user_id == user_id)
                    .values(language=UserLanguage(language))
                )
                await session.execute(query)
                await session.commit()
                return True
            except Exception as e:
                await session.rollback()
                logger.error(f"[DB] Ошибка при обновлении языка пользователя {user_id}: {e}")
                return False


class ThreadORM:
    """Класс для работы с топиками пользователей"""
    
    @staticmethod
    async def get_or_create_thread(user_id: int, user_name: str, thread_id: int = None):
        """
        Получает или создает топик для пользователя
        :param user_id: ID пользователя
        :param user_name: Username пользователя
        :param thread_id: ID топика (если создается)
        :return: UserThread объект
        """
        async with session_factory_async() as session:
            try:
                # Проверяем, есть ли уже топик для пользователя
                query = select(UserThread).filter(UserThread.user_id == user_id)
                result = await session.execute(query)
                thread = result.scalar_one_or_none()
                
                if thread:
                    return thread
                
                # Если топика нет и передан thread_id, создаем новый
                if thread_id:
                    new_thread = UserThread(
                        user_id=user_id,
                        user_name=user_name,
                        thread_id=thread_id
                    )
                    session.add(new_thread)
                    await session.commit()
                    await session.refresh(new_thread)
                    logger.info(f"Создан новый топик для пользователя {user_id}: thread_id={thread_id}")
                    return new_thread
                
                return None
            except Exception as e:
                await session.rollback()
                logger.error(f"[DB] Ошибка при работе с топиком для пользователя {user_id}: {e}")
                return None
    
    @staticmethod
    async def get_thread_by_id(thread_id: int):
        """
        Получает информацию о топике по его ID
        :param thread_id: ID топика
        :return: UserThread объект или None
        """
        async with session_factory_async() as session:
            try:
                query = select(UserThread).filter(UserThread.thread_id == thread_id)
                result = await session.execute(query)
                return result.scalar_one_or_none()
            except Exception as e:
                logger.error(f"[DB] Ошибка при получении топика {thread_id}: {e}")
                return None
    
    @staticmethod
    async def get_user_by_thread_id(thread_id: int):
        """
        Получает user_id по thread_id
        :param thread_id: ID топика
        :return: user_id или None
        """
        logger.info(f"[ThreadORM] Ищем user_id для thread_id={thread_id}")
        thread = await ThreadORM.get_thread_by_id(thread_id)
        if thread:
            logger.info(f"[ThreadORM] Найден thread: user_id={thread.user_id}")
        else:
            logger.warning(f"[ThreadORM] Thread не найден для thread_id={thread_id}")
        return thread.user_id if thread else None


class PostsORM:
    """Класс для работы с постами пользователей"""
    
    @staticmethod
    async def create_post(
        user_id: int,
        post_id: int,
        post_text: str = None,
        post_media_list: list[str] = None,
        admin_id: int = None,
        tariff_user: UserTariff = UserTariff.free
    ) -> Optional[UserPosts]:
        """
        Создает новый пост в базе данных
        
        Args:
            user_id: ID пользователя
            post_id: ID поста в Telegram
            post_text: Текст поста
            post_media_list: Список ключей медиа в S3
            admin_id: ID админа, опубликовавшего пост
            tariff_user: Тариф пользователя
            
        Returns:
            Объект UserPosts или None
        """
        async with session_factory_async() as session:
            try:
                new_post = UserPosts(
                    user_id=user_id,
                    post_id=post_id,
                    post_text=post_text,
                    post_media_list=post_media_list,
                    is_published=True,
                    date_published=datetime.now(timezone.utc),
                    admin_id=admin_id,
                    tariff_user=tariff_user
                )
                session.add(new_post)
                await session.commit()
                await session.refresh(new_post)
                logger.info(f"Создан новый пост ID={new_post.id} для пользователя {user_id}")
                return new_post
            except Exception as e:
                await session.rollback()
                logger.error(f"[DB] Ошибка при создании поста для пользователя {user_id}: {e}")
                return None
    
    @staticmethod
    async def get_post_by_id(post_id: int) -> Optional[UserPosts]:
        """Получает пост по ID"""
        async with session_factory_async() as session:
            try:
                query = select(UserPosts).filter(UserPosts.id == post_id)
                result = await session.execute(query)
                return result.scalar_one_or_none()
            except Exception as e:
                logger.error(f"[DB] Ошибка при получении поста {post_id}: {e}")
                return None
    
    @staticmethod
    async def get_user_posts(user_id: int) -> list[UserPosts]:
        """Получает все посты пользователя"""
        async with session_factory_async() as session:
            try:
                query = select(UserPosts).filter(UserPosts.user_id == user_id).order_by(UserPosts.created_at.desc())
                result = await session.execute(query)
                return result.scalars().all()
            except Exception as e:
                logger.error(f"[DB] Ошибка при получении постов пользователя {user_id}: {e}")
                return []


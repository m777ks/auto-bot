from datetime import datetime
from sqlalchemy import Column, DateTime, Integer, String, BigInteger, ForeignKey, JSON, Boolean, Enum, Text, Table, \
    UniqueConstraint, ARRAY
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
import enum

Base = declarative_base()

class UserStatus(enum.Enum):
    active = 'active'
    blocked = 'blocked'
    deleted = 'deleted'

class UserLanguage(enum.Enum):
    ru = 'ru'
    en = 'en'
    ge = 'ge'

class UserTariff(enum.Enum):
    free = 'free'
    pro = 'pro'
    premium = 'premium'

class Users(Base):
    """
    Модель пользователя в системе
    """
    __tablename__ = 'users'

    # Основные поля
    user_id = Column(BigInteger, primary_key=True, index=True)
    user_name = Column(String, nullable=True)
    name = Column(String, nullable=True)
    phone_number = Column(String, nullable=True)
    language = Column(Enum(UserLanguage), default=UserLanguage.ru)


    created_at = Column(DateTime(timezone=True), default=datetime.now)
    updated_at = Column(DateTime(timezone=True), onupdate=datetime.now, nullable=True)

    user_status = Column(Enum(UserStatus), default=UserStatus.active)
    user_tariff = Column(Enum(UserTariff), default=UserTariff.free)


    total_posts = Column(Integer, default=0)

    # заметки
    notes = Column(Text, nullable=True)

class UserPosts(Base):
    """
    Модель для постов пользователя
    """
    __tablename__ = 'user_posts'

    id = Column(Integer, primary_key=True)
    user_id = Column(BigInteger)
    post_id = Column(BigInteger)
    post_text = Column(Text, nullable=True)
    post_media_list = Column(ARRAY(String), nullable=True)

    is_published = Column(Boolean, default=False)
    date_published = Column(DateTime(timezone=True), nullable=True)
    admin_id = Column(BigInteger, nullable=True)
    tariff_user = Column(Enum(UserTariff), default=UserTariff.free)
    


    created_at = Column(DateTime(timezone=True), default=datetime.now)
    updated_at = Column(DateTime(timezone=True), onupdate=datetime.now, nullable=True)


class UserThread(Base):
    """
    Модель для хранения информации о топиках пользователей в группе
    """
    __tablename__ = 'user_threads'

    id = Column(Integer, primary_key=True)
    user_id = Column(BigInteger, unique=True, index=True)
    user_name = Column(String, nullable=True)
    thread_id = Column(Integer, nullable=False)
    
    created_at = Column(DateTime(timezone=True), default=datetime.now)
    updated_at = Column(DateTime(timezone=True), onupdate=datetime.now, nullable=True)

class Logger(Base):
    """
    Модель для логирования действий пользователей
    """
    __tablename__ = 'logger'

    id = Column(Integer, primary_key=True)
    timestamp = Column(DateTime(timezone=True), default=datetime.now)
    user_id = Column(BigInteger)
    user_name = Column(String, nullable=True)
    type = Column(String)
    action = Column(String)

from django.db import models
from django.contrib.postgres.fields import ArrayField


class UserStatus(models.TextChoices):
    ACTIVE = 'active', 'Активен'
    BLOCKED = 'blocked', 'Заблокирован'
    DELETED = 'deleted', 'Удален'


class UserLanguage(models.TextChoices):
    RU = 'ru', 'Русский'
    EN = 'en', 'English'
    GE = 'ge', 'Georgian'


class UserTariff(models.TextChoices):
    FREE = 'free', 'Бесплатный'
    PRO = 'pro', 'Pro'
    PREMIUM = 'premium', 'Premium'


class Users(models.Model):
    """Модель пользователя"""
    user_id = models.BigIntegerField(primary_key=True, verbose_name='Telegram ID')
    user_name = models.CharField(max_length=255, null=True, blank=True, verbose_name='Username')
    name = models.CharField(max_length=255, null=True, blank=True, verbose_name='Имя')
    phone_number = models.CharField(max_length=50, null=True, blank=True, verbose_name='Телефон')
    language = models.CharField(
        max_length=10, 
        choices=UserLanguage.choices, 
        default=UserLanguage.RU,
        verbose_name='Язык'
    )
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата регистрации')
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True, verbose_name='Обновлен')
    
    user_status = models.CharField(
        max_length=20, 
        choices=UserStatus.choices, 
        default=UserStatus.ACTIVE,
        verbose_name='Статус'
    )
    user_tariff = models.CharField(
        max_length=20, 
        choices=UserTariff.choices, 
        default=UserTariff.FREE,
        verbose_name='Тариф'
    )
    
    total_posts = models.IntegerField(default=0, verbose_name='Всего постов')
    notes = models.TextField(null=True, blank=True, verbose_name='Заметки')

    class Meta:
        db_table = 'users'
        managed = False
        verbose_name = 'Пользователь'
        verbose_name_plural = 'Пользователи'
        ordering = ['-created_at']

    def __str__(self):
        return f"@{self.user_name}" if self.user_name else f"ID: {self.user_id}"


class UserPosts(models.Model):
    """Модель постов пользователей"""
    id = models.AutoField(primary_key=True)
    user_id = models.BigIntegerField(verbose_name='User ID')
    post_id = models.BigIntegerField(verbose_name='Post ID в Telegram')
    post_message_ids = ArrayField(
        models.BigIntegerField(),
        null=True,
        blank=True,
        verbose_name='Все Message IDs (для медиагрупп)'
    )
    post_text = models.TextField(null=True, blank=True, verbose_name='Текст поста')
    post_media_list = ArrayField(
        models.CharField(max_length=500),
        null=True,
        blank=True,
        verbose_name='Медиа (S3 ключи)'
    )
    
    is_published = models.BooleanField(default=False, verbose_name='Опубликован')
    is_deleted = models.BooleanField(default=False, verbose_name='Удалён в Telegram')
    date_published = models.DateTimeField(null=True, blank=True, verbose_name='Дата публикации')
    date_deleted = models.DateTimeField(null=True, blank=True, verbose_name='Дата удаления')
    admin_id = models.BigIntegerField(null=True, blank=True, verbose_name='Admin ID')
    tariff_user = models.CharField(
        max_length=20, 
        choices=UserTariff.choices, 
        default=UserTariff.FREE,
        verbose_name='Тариф пользователя'
    )
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Создан')
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True, verbose_name='Обновлен')

    class Meta:
        db_table = 'user_posts'
        managed = False
        verbose_name = 'Пост'
        verbose_name_plural = 'Посты'
        ordering = ['-created_at']

    def __str__(self):
        return f"Пост #{self.post_id} от {self.user_id}"


class UserThread(models.Model):
    """Модель топиков пользователей"""
    id = models.AutoField(primary_key=True)
    user_id = models.BigIntegerField(unique=True, verbose_name='User ID')
    user_name = models.CharField(max_length=255, null=True, blank=True, verbose_name='Username')
    thread_id = models.IntegerField(verbose_name='Thread ID')
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Создан')
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True, verbose_name='Обновлен')

    class Meta:
        db_table = 'user_threads'
        managed = False
        verbose_name = 'Топик пользователя'
        verbose_name_plural = 'Топики пользователей'
        ordering = ['-created_at']

    def __str__(self):
        return f"@{self.user_name} → Thread #{self.thread_id}"


class Logger(models.Model):
    """Модель логов"""
    id = models.AutoField(primary_key=True)
    timestamp = models.DateTimeField(auto_now_add=True, verbose_name='Время')
    user_id = models.BigIntegerField(verbose_name='User ID')
    user_name = models.CharField(max_length=255, null=True, blank=True, verbose_name='Username')
    type = models.CharField(max_length=100, verbose_name='Тип')
    action = models.CharField(max_length=500, verbose_name='Действие')

    class Meta:
        db_table = 'logger'
        managed = False
        verbose_name = 'Лог'
        verbose_name_plural = 'Логи'
        ordering = ['-timestamp']

    def __str__(self):
        action_preview = (self.action or "")[:50]
        return f"[{self.type}] {self.user_name}: {action_preview}"

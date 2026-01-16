from django.contrib import admin
from django.contrib import messages
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.urls import reverse
from urllib.parse import urlencode
from .models import Users, UserPosts, UserThread, Logger

import requests
import os


@admin.register(Users)
class UsersAdmin(admin.ModelAdmin):
    list_display = [
        'user_id', 
        'user_name_link', 
        'name', 
        'language_badge', 
        'status_badge', 
        'tariff_badge',
        'total_posts',
        'created_at'
    ]
    list_filter = ['user_status', 'user_tariff', 'language', 'created_at']
    search_fields = ['user_id', 'user_name', 'name', 'phone_number']
    readonly_fields = ['user_id', 'created_at', 'updated_at']
    list_per_page = 50
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('user_id', 'user_name', 'name', 'phone_number')
        }),
        ('Настройки', {
            'fields': ('language', 'user_status', 'user_tariff')
        }),
        ('Статистика', {
            'fields': ('total_posts',)
        }),
        ('Заметки', {
            'fields': ('notes',),
            'classes': ('collapse',)
        }),
        ('Даты', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def user_name_link(self, obj):
        if obj.user_name:
            return format_html(
                '<a href="https://t.me/{}" target="_blank">@{}</a>',
                obj.user_name, obj.user_name
            )
        return '-'
    user_name_link.short_description = 'Username'
    
    def language_badge(self, obj):
        flags = {'ru': '🇷🇺', 'en': '🇬🇧', 'ge': '🇬🇪'}
        flag = flags.get(obj.language, '🌍')
        return format_html('<span>{} {}</span>', flag, obj.language.upper())
    language_badge.short_description = 'Язык'
    
    def status_badge(self, obj):
        colors = {
            'active': '#28a745',
            'blocked': '#dc3545', 
            'deleted': '#6c757d'
        }
        labels = {
            'active': 'Активен',
            'blocked': 'Заблокирован',
            'deleted': 'Удален'
        }
        color = colors.get(obj.user_status, '#6c757d')
        label = labels.get(obj.user_status, obj.user_status)
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 4px; font-size: 11px;">{}</span>',
            color, label
        )
    status_badge.short_description = 'Статус'
    
    def tariff_badge(self, obj):
        colors = {
            'free': '#6c757d',
            'pro': '#007bff',
            'premium': '#ffc107'
        }
        color = colors.get(obj.user_tariff, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 4px; font-size: 11px; text-transform: uppercase;">{}</span>',
            color, obj.user_tariff
        )
    tariff_badge.short_description = 'Тариф'


@admin.register(UserPosts)
class UserPostsAdmin(admin.ModelAdmin):
    list_display = [
        'id',
        'user_id',
        'post_id',
        'short_text',
        'status_badge',
        'media_count',
        'admin_id',
        'date_published',
        'created_at'
    ]
    list_filter = ['is_published', 'is_deleted', 'tariff_user', 'date_published', 'created_at']
    search_fields = ['user_id', 'post_id', 'post_text', 'admin_id']
    readonly_fields = ['id', 'created_at', 'updated_at', 'post_media_preview', 'is_deleted', 'date_deleted']
    list_per_page = 50
    actions = ['check_posts_exist', 'repost_to_channel', 'delete_from_channel']
    change_list_template = 'admin/bot/userposts_changelist.html'
    
    fieldsets = (
        ('Информация о посте', {
            'fields': ('user_id', 'post_id', 'admin_id')
        }),
        ('Контент', {
            'fields': ('post_text', 'post_media_list', 'post_media_preview')
        }),
        ('Статус', {
            'fields': ('is_published', 'is_deleted', 'date_published', 'date_deleted', 'tariff_user')
        }),
        ('Даты', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    @admin.action(description='🔍 Проверить существование постов в Telegram')
    def check_posts_exist(self, request, queryset):
        """Проверяет существуют ли выбранные посты в канале Telegram"""
        import sys
        from pathlib import Path
        BASE_DIR = Path(__file__).resolve().parent.parent.parent
        sys.path.append(str(BASE_DIR))
        from config_data.config import load_config
        
        config = load_config()
        bot_token = config.tg_bot.token
        channel_id = config.tg_bot.channel_id
        
        deleted_count = 0
        checked_count = 0
        
        for post in queryset.filter(is_published=True, is_deleted=False):
            try:
                # Используем getChat для проверки (copyMessage требует chat_id назначения)
                # Вместо этого попробуем forwardMessage к себе
                url = f"https://api.telegram.org/bot{bot_token}/copyMessage"
                response = requests.post(url, json={
                    'chat_id': config.tg_bot.admin_ids[0],
                    'from_chat_id': channel_id,
                    'message_id': post.post_id,
                    'disable_notification': True
                }, timeout=10)
                
                result = response.json()
                
                if result.get('ok'):
                    # Пост существует, удаляем скопированное сообщение
                    copied_msg_id = result['result']['message_id']
                    delete_url = f"https://api.telegram.org/bot{bot_token}/deleteMessage"
                    requests.post(delete_url, json={
                        'chat_id': config.tg_bot.admin_ids[0],
                        'message_id': copied_msg_id
                    }, timeout=10)
                    checked_count += 1
                else:
                    error_desc = result.get('description', '').lower()
                    if 'message to copy not found' in error_desc or 'message not found' in error_desc:
                        # Пост удалён
                        from django.utils import timezone
                        post.is_deleted = True
                        post.date_deleted = timezone.now()
                        post.save(update_fields=['is_deleted', 'date_deleted'])
                        deleted_count += 1
                    else:
                        checked_count += 1
                        
            except Exception as e:
                self.message_user(request, f"Ошибка при проверке поста {post.id}: {e}", messages.WARNING)
        
        if deleted_count > 0:
            self.message_user(
                request, 
                f"✅ Проверено: {checked_count + deleted_count}. Помечено как удалённые: {deleted_count}",
                messages.SUCCESS
            )
        else:
            self.message_user(
                request,
                f"✅ Проверено: {checked_count}. Все посты на месте.",
                messages.SUCCESS
            )
    
    @admin.action(description='🔄 Повторно опубликовать в канал')
    def repost_to_channel(self, request, queryset):
        """Повторно публикует выбранные посты в канал"""
        import sys
        from pathlib import Path
        from datetime import datetime, timezone as tz
        import boto3
        from botocore.client import Config
        
        BASE_DIR = Path(__file__).resolve().parent.parent.parent
        sys.path.append(str(BASE_DIR))
        from config_data.config import load_config
        
        config = load_config()
        bot_token = config.tg_bot.token
        channel_id = config.tg_bot.channel_id
        
        # S3 клиент для presigned URL
        s3_client = boto3.client(
            's3',
            config=Config(signature_version='s3v4'),
            endpoint_url=config.s3.url,
            aws_access_key_id=config.s3.key_id,
            aws_secret_access_key=config.s3.key_secret,
        )
        
        success_count = 0
        error_count = 0
        
        for post in queryset:
            try:
                post_text = post.post_text or ''
                media_keys = post.post_media_list or []
                
                # Генерируем presigned URLs для медиа
                media_items = []
                for key in media_keys:
                    presigned_url = s3_client.generate_presigned_url(
                        ClientMethod='get_object',
                        Params={'Bucket': config.s3.name, 'Key': key},
                        ExpiresIn=3600
                    )
                    ext = key.lower().split('.')[-1] if '.' in key else ''
                    if ext in ['jpg', 'jpeg', 'png', 'gif', 'webp']:
                        media_type = 'photo'
                    elif ext in ['mp4', 'mov', 'avi', 'webm']:
                        media_type = 'video'
                    else:
                        media_type = 'document'
                    media_items.append({'type': media_type, 'url': presigned_url})
                
                # Отправляем в Telegram
                if len(media_items) == 0:
                    # Только текст
                    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
                    response = requests.post(url, json={
                        'chat_id': channel_id,
                        'text': post_text,
                        'parse_mode': 'HTML'
                    }, timeout=30)
                    result = response.json()
                    
                elif len(media_items) == 1:
                    # Одно медиа
                    if media_items[0]['type'] == 'photo':
                        url = f"https://api.telegram.org/bot{bot_token}/sendPhoto"
                        data = {'chat_id': channel_id, 'photo': media_items[0]['url']}
                    else:
                        url = f"https://api.telegram.org/bot{bot_token}/sendVideo"
                        data = {'chat_id': channel_id, 'video': media_items[0]['url']}
                    
                    if post_text:
                        data['caption'] = post_text
                        data['parse_mode'] = 'HTML'
                    
                    response = requests.post(url, json=data, timeout=60)
                    result = response.json()
                    
                else:
                    # Медиагруппа
                    url = f"https://api.telegram.org/bot{bot_token}/sendMediaGroup"
                    media = []
                    for i, item in enumerate(media_items):
                        media_obj = {'type': item['type'], 'media': item['url']}
                        if i == 0 and post_text:
                            media_obj['caption'] = post_text
                            media_obj['parse_mode'] = 'HTML'
                        media.append(media_obj)
                    
                    response = requests.post(url, json={
                        'chat_id': channel_id,
                        'media': media
                    }, timeout=60)
                    result = response.json()
                
                if result.get('ok'):
                    # Получаем все message_id
                    new_post_id = 0
                    new_post_message_ids = []
                    
                    if 'result' in result:
                        if isinstance(result['result'], list):
                            # Медиагруппа
                            new_post_message_ids = [msg['message_id'] for msg in result['result']]
                            new_post_id = new_post_message_ids[0] if new_post_message_ids else 0
                        else:
                            new_post_id = result['result']['message_id']
                            new_post_message_ids = [new_post_id]
                    
                    # Создаём новую запись поста
                    UserPosts.objects.create(
                        user_id=post.user_id,
                        post_id=new_post_id,
                        post_message_ids=new_post_message_ids if new_post_message_ids else None,
                        post_text=post.post_text,
                        post_media_list=post.post_media_list,
                        is_published=True,
                        date_published=datetime.now(tz.utc),
                        admin_id=request.user.id,
                        tariff_user=post.tariff_user,
                    )
                    success_count += 1
                else:
                    error_msg = result.get('description', 'Неизвестная ошибка')
                    self.message_user(request, f"Ошибка поста {post.id}: {error_msg}", messages.WARNING)
                    error_count += 1
                    
            except Exception as e:
                self.message_user(request, f"Ошибка поста {post.id}: {e}", messages.ERROR)
                error_count += 1
        
        if success_count > 0:
            self.message_user(
                request,
                f"🚀 Опубликовано: {success_count} постов" + (f", ошибок: {error_count}" if error_count else ""),
                messages.SUCCESS
            )
    
    @admin.action(description='🗑️ Удалить из канала Telegram')
    def delete_from_channel(self, request, queryset):
        """Удаляет выбранные посты из канала Telegram"""
        import sys
        from pathlib import Path
        from django.utils import timezone
        
        BASE_DIR = Path(__file__).resolve().parent.parent.parent
        sys.path.append(str(BASE_DIR))
        from config_data.config import load_config
        
        config = load_config()
        bot_token = config.tg_bot.token
        channel_id = config.tg_bot.channel_id
        
        deleted_count = 0
        already_deleted = 0
        error_count = 0
        messages_deleted = 0
        
        for post in queryset.filter(is_published=True):
            # Пропускаем уже удалённые
            if post.is_deleted:
                already_deleted += 1
                continue
            
            try:
                # Собираем все message_id для удаления
                message_ids_to_delete = []
                
                # Если есть массив всех ID — используем его
                if post.post_message_ids:
                    message_ids_to_delete = list(post.post_message_ids)
                else:
                    # Иначе используем только post_id
                    message_ids_to_delete = [post.post_id]
                
                post_deleted = False
                
                for msg_id in message_ids_to_delete:
                    url = f"https://api.telegram.org/bot{bot_token}/deleteMessage"
                    response = requests.post(url, json={
                        'chat_id': channel_id,
                        'message_id': msg_id
                    }, timeout=10)
                    
                    result = response.json()
                    
                    if result.get('ok'):
                        messages_deleted += 1
                        post_deleted = True
                    else:
                        error_desc = result.get('description', '').lower()
                        if 'message to delete not found' in error_desc or 'message not found' in error_desc:
                            # Сообщение уже было удалено
                            post_deleted = True
                        # Другие ошибки игнорируем для отдельных сообщений
                
                if post_deleted:
                    post.is_deleted = True
                    post.date_deleted = timezone.now()
                    post.save(update_fields=['is_deleted', 'date_deleted'])
                    deleted_count += 1
                else:
                    error_count += 1
                        
            except Exception as e:
                self.message_user(request, f"Ошибка поста {post.id}: {e}", messages.ERROR)
                error_count += 1
        
        msg_parts = []
        if deleted_count > 0:
            msg_parts.append(f"🗑️ Удалено постов: {deleted_count} (сообщений: {messages_deleted})")
        if already_deleted > 0:
            msg_parts.append(f"уже удалены: {already_deleted}")
        if error_count > 0:
            msg_parts.append(f"ошибок: {error_count}")
        
        if msg_parts:
            self.message_user(request, ", ".join(msg_parts), messages.SUCCESS if deleted_count > 0 else messages.WARNING)
        else:
            self.message_user(request, "Нет постов для удаления", messages.INFO)
    
    def short_text(self, obj):
        if obj.post_text:
            text = obj.post_text[:100]
            if len(obj.post_text) > 100:
                text += '...'
            return text
        return '-'
    short_text.short_description = 'Текст'
    
    def status_badge(self, obj):
        if obj.is_deleted:
            return format_html(
                '<span style="background-color: #dc3545; color: white; padding: 3px 8px; border-radius: 4px; font-size: 11px;">🗑️ Удалён</span>'
            )
        if obj.is_published:
            return format_html(
                '<span style="background-color: #28a745; color: white; padding: 3px 8px; border-radius: 4px; font-size: 11px;">✓ Опубликован</span>'
            )
        return format_html(
            '<span style="background-color: #ffc107; color: black; padding: 3px 8px; border-radius: 4px; font-size: 11px;">Черновик</span>'
        )
    status_badge.short_description = 'Статус'
    
    def media_count(self, obj):
        if obj.post_media_list:
            count = len(obj.post_media_list)
            return format_html(
                '<span style="background-color: #17a2b8; color: white; padding: 3px 8px; border-radius: 4px; font-size: 11px;">📷 {}</span>',
                count
            )
        return '-'
    media_count.short_description = 'Медиа'
    
    def post_media_preview(self, obj):
        """Превью медиафайлов с presigned URL"""
        if not obj.post_media_list:
            return '-'
        
        html_parts = ['<div style="display: flex; flex-wrap: wrap; gap: 10px;">']
        
        for i, key in enumerate(obj.post_media_list, 1):
            # Определяем тип файла по расширению
            ext = key.lower().split('.')[-1] if '.' in key else ''
            filename = key.split('/')[-1]
            
            # Генерируем URL для presigned через view
            preview_url = f"/s3-preview/?{urlencode({'key': key})}"
            
            if ext in ['jpg', 'jpeg', 'png', 'gif', 'webp']:
                # Изображение — показываем превью
                html_parts.append(f'''
                    <div style="text-align: center;">
                        <a href="{preview_url}" target="_blank">
                            <img src="{preview_url}" 
                                 style="max-width: 150px; max-height: 150px; border-radius: 8px; 
                                        box-shadow: 0 2px 4px rgba(0,0,0,0.2); cursor: pointer;"
                                 loading="lazy"
                                 onerror="this.style.display='none'; this.nextElementSibling.style.display='flex';" />
                            <div style="display: none; width: 150px; height: 100px; background: #444; 
                                        border-radius: 8px; align-items: center; justify-content: center;">
                                <span style="font-size: 30px;">🖼️</span>
                            </div>
                        </a>
                        <div style="font-size: 10px; color: #888; margin-top: 4px; max-width: 150px; 
                                    overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">
                            {filename}
                        </div>
                    </div>
                ''')
            elif ext in ['mp4', 'mov', 'avi', 'webm']:
                # Видео — иконка со ссылкой
                html_parts.append(f'''
                    <div style="text-align: center;">
                        <a href="{preview_url}" target="_blank" style="text-decoration: none;">
                            <div style="width: 150px; height: 100px; background: #333; border-radius: 8px;
                                        display: flex; align-items: center; justify-content: center;
                                        box-shadow: 0 2px 4px rgba(0,0,0,0.2);">
                                <span style="font-size: 40px;">🎬</span>
                            </div>
                        </a>
                        <div style="font-size: 10px; color: #888; margin-top: 4px; max-width: 150px; 
                                    overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">
                            {filename}
                        </div>
                    </div>
                ''')
            else:
                # Другой файл
                html_parts.append(f'''
                    <div style="text-align: center;">
                        <a href="{preview_url}" target="_blank" style="text-decoration: none;">
                            <div style="width: 100px; height: 60px; background: #555; border-radius: 8px;
                                        display: flex; align-items: center; justify-content: center;">
                                <span style="font-size: 24px;">📎</span>
                            </div>
                        </a>
                        <div style="font-size: 10px; color: #888; margin-top: 4px;">
                            {filename}
                        </div>
                    </div>
                ''')
        
        html_parts.append('</div>')
        return mark_safe(''.join(html_parts))
    post_media_preview.short_description = 'Превью медиа'


@admin.register(UserThread)
class UserThreadAdmin(admin.ModelAdmin):
    list_display = ['id', 'user_id', 'user_name_link', 'thread_id', 'created_at']
    list_filter = ['created_at']
    search_fields = ['user_id', 'user_name', 'thread_id']
    readonly_fields = ['id', 'created_at', 'updated_at']
    list_per_page = 50
    
    def user_name_link(self, obj):
        if obj.user_name:
            return format_html(
                '<a href="https://t.me/{}" target="_blank">@{}</a>',
                obj.user_name, obj.user_name
            )
        return '-'
    user_name_link.short_description = 'Username'


@admin.register(Logger)
class LoggerAdmin(admin.ModelAdmin):
    list_display = ['id', 'timestamp', 'user_id', 'user_name', 'type_badge', 'action_short']
    list_filter = ['type', 'timestamp']
    search_fields = ['user_id', 'user_name', 'action', 'type']
    readonly_fields = ['id', 'timestamp', 'user_id', 'user_name', 'type', 'action']
    list_per_page = 100
    date_hierarchy = 'timestamp'
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False
    
    def type_badge(self, obj):
        colors = {
            'message': '#007bff',
            'callback': '#6f42c1',
            'command': '#28a745',
            'error': '#dc3545',
        }
        color = colors.get(obj.type.lower(), '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 2px 6px; border-radius: 3px; font-size: 10px;">{}</span>',
            color, obj.type
        )
    type_badge.short_description = 'Тип'
    
    def action_short(self, obj):
        if not obj.action:
            return '-'
        if len(obj.action) > 80:
            return obj.action[:80] + '...'
        return obj.action
    action_short.short_description = 'Действие'


# Настройка заголовков админки
admin.site.site_header = '🚗 Auto Georgian Bot'
admin.site.site_title = 'Auto Georgian Bot Admin'
admin.site.index_title = 'Панель управления'

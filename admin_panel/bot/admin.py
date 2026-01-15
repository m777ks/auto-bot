from django.contrib import admin
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from .models import Users, UserPosts, UserThread, Logger


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
        'published_badge',
        'media_count',
        'admin_id',
        'date_published',
        'created_at'
    ]
    list_filter = ['is_published', 'tariff_user', 'date_published', 'created_at']
    search_fields = ['user_id', 'post_id', 'post_text', 'admin_id']
    readonly_fields = ['id', 'created_at', 'updated_at', 'post_media_preview']
    list_per_page = 50
    
    fieldsets = (
        ('Информация о посте', {
            'fields': ('user_id', 'post_id', 'admin_id')
        }),
        ('Контент', {
            'fields': ('post_text', 'post_media_list', 'post_media_preview')
        }),
        ('Статус', {
            'fields': ('is_published', 'date_published', 'tariff_user')
        }),
        ('Даты', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def short_text(self, obj):
        if obj.post_text:
            text = obj.post_text[:100]
            if len(obj.post_text) > 100:
                text += '...'
            return text
        return '-'
    short_text.short_description = 'Текст'
    
    def published_badge(self, obj):
        if obj.is_published:
            return format_html(
                '<span style="background-color: #28a745; color: white; padding: 3px 8px; border-radius: 4px; font-size: 11px;">✓ Опубликован</span>'
            )
        return format_html(
            '<span style="background-color: #ffc107; color: black; padding: 3px 8px; border-radius: 4px; font-size: 11px;">Черновик</span>'
        )
    published_badge.short_description = 'Статус'
    
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
        if obj.post_media_list:
            items = []
            for key in obj.post_media_list:
                items.append(f'<li><code>{key}</code></li>')
            return mark_safe(f'<ul>{"".join(items)}</ul>')
        return '-'
    post_media_preview.short_description = 'Список медиа'


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

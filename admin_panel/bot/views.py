import boto3
import requests
import uuid
from io import BytesIO
from datetime import datetime, timezone

from botocore.client import Config
from django.http import JsonResponse, HttpResponseRedirect
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render, redirect
from django.contrib import messages
from django.urls import reverse

import sys
from pathlib import Path
BASE_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(BASE_DIR))
from config_data.config import load_config

config = load_config()

# Создаём S3 клиент один раз при загрузке модуля
s3_client = boto3.client(
    's3',
    config=Config(signature_version='s3v4'),
    endpoint_url=config.s3.url,
    aws_access_key_id=config.s3.key_id,
    aws_secret_access_key=config.s3.key_secret,
)

BOT_TOKEN = config.tg_bot.token
CHANNEL_ID = config.tg_bot.channel_id


@staff_member_required
def get_presigned_url(request):
    """Генерирует presigned URL для S3 объекта и редиректит на него"""
    key = request.GET.get('key', '')
    
    if not key:
        return JsonResponse({'error': 'No key provided'}, status=400)
    
    try:
        url = s3_client.generate_presigned_url(
            ClientMethod='get_object',
            Params={
                'Bucket': config.s3.name,
                'Key': key
            },
            ExpiresIn=3600  # 1 час
        )
        return HttpResponseRedirect(url)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


def upload_to_s3(file_obj, filename: str) -> str:
    """Загружает файл в S3 и возвращает ключ"""
    key = f"posts/admin/{datetime.now().strftime('%Y%m%d_%H%M%S')}_{filename}"
    try:
        s3_client.upload_fileobj(file_obj, config.s3.name, key)
        return key
    except Exception as e:
        raise Exception(f"Ошибка загрузки в S3: {e}")


def send_telegram_message(text: str) -> dict:
    """Отправляет текстовое сообщение в канал"""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    response = requests.post(url, json={
        'chat_id': CHANNEL_ID,
        'text': text,
        'parse_mode': 'HTML'
    }, timeout=30)
    return response.json()


def send_telegram_photo(photo_url: str, caption: str = None) -> dict:
    """Отправляет фото в канал"""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
    data = {
        'chat_id': CHANNEL_ID,
        'photo': photo_url,
    }
    if caption:
        data['caption'] = caption
        data['parse_mode'] = 'HTML'
    response = requests.post(url, json=data, timeout=30)
    return response.json()


def send_telegram_media_group(media_items: list, caption: str = None) -> dict:
    """Отправляет группу медиа в канал"""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMediaGroup"
    
    media = []
    for i, item in enumerate(media_items):
        media_obj = {
            'type': item['type'],
            'media': item['url'],
        }
        # Caption только к первому элементу
        if i == 0 and caption:
            media_obj['caption'] = caption
            media_obj['parse_mode'] = 'HTML'
        media.append(media_obj)
    
    response = requests.post(url, json={
        'chat_id': CHANNEL_ID,
        'media': media
    }, timeout=60)
    return response.json()


@staff_member_required
def create_post(request):
    """Страница создания и публикации поста"""
    from .models import UserPosts
    
    if request.method == 'POST':
        post_text = request.POST.get('post_text', '').strip()
        user_id = request.POST.get('user_id', '0')
        files = request.FILES.getlist('media_files')
        
        try:
            user_id = int(user_id) if user_id else 0
        except ValueError:
            user_id = 0
        
        if not post_text and not files:
            messages.error(request, 'Укажите текст или загрузите медиафайлы')
            return redirect('admin:create_post')
        
        try:
            s3_keys = []
            media_items = []
            
            # Загружаем файлы в S3
            for file in files:
                key = upload_to_s3(file, file.name)
                s3_keys.append(key)
                
                # Генерируем presigned URL для отправки в Telegram
                presigned_url = s3_client.generate_presigned_url(
                    ClientMethod='get_object',
                    Params={'Bucket': config.s3.name, 'Key': key},
                    ExpiresIn=3600
                )
                
                # Определяем тип медиа
                ext = file.name.lower().split('.')[-1]
                if ext in ['jpg', 'jpeg', 'png', 'gif', 'webp']:
                    media_type = 'photo'
                elif ext in ['mp4', 'mov', 'avi', 'webm']:
                    media_type = 'video'
                else:
                    media_type = 'document'
                
                media_items.append({
                    'type': media_type,
                    'url': presigned_url
                })
            
            # Отправляем в Telegram
            if len(media_items) == 0:
                # Только текст
                result = send_telegram_message(post_text)
            elif len(media_items) == 1:
                # Одно фото/видео
                if media_items[0]['type'] == 'photo':
                    result = send_telegram_photo(media_items[0]['url'], post_text)
                else:
                    # Для видео используем sendVideo
                    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendVideo"
                    data = {
                        'chat_id': CHANNEL_ID,
                        'video': media_items[0]['url'],
                    }
                    if post_text:
                        data['caption'] = post_text
                        data['parse_mode'] = 'HTML'
                    response = requests.post(url, json=data, timeout=60)
                    result = response.json()
            else:
                # Несколько медиа
                result = send_telegram_media_group(media_items, post_text)
            
            if not result.get('ok'):
                error_msg = result.get('description', 'Неизвестная ошибка')
                messages.error(request, f'Ошибка Telegram: {error_msg}')
                return redirect('admin:create_post')
            
            # Получаем message_id (все ID для медиагруппы)
            post_id = 0
            post_message_ids = []
            
            if 'result' in result:
                if isinstance(result['result'], list):
                    # Медиагруппа — сохраняем все message_id
                    post_message_ids = [msg['message_id'] for msg in result['result']]
                    post_id = post_message_ids[0] if post_message_ids else 0
                else:
                    post_id = result['result']['message_id']
                    post_message_ids = [post_id]
            
            # Сохраняем в БД
            post = UserPosts.objects.create(
                user_id=user_id,
                post_id=post_id,
                post_message_ids=post_message_ids if post_message_ids else None,
                post_text=post_text,
                post_media_list=s3_keys if s3_keys else None,
                is_published=True,
                date_published=datetime.now(timezone.utc),
                admin_id=request.user.id,
            )
            
            messages.success(request, f'✅ Пост #{post.id} успешно опубликован в канал!')
            return redirect('admin:bot_userposts_changelist')
            
        except Exception as e:
            messages.error(request, f'Ошибка: {str(e)}')
            return redirect('admin:create_post')
    
    # GET — показываем форму
    context = {
        'title': 'Создать пост',
        'site_header': '🚗 Auto Georgian Bot',
    }
    return render(request, 'admin/bot/create_post.html', context)

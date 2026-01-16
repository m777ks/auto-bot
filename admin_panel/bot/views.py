import boto3
from botocore.client import Config
from django.http import JsonResponse, HttpResponseRedirect
from django.contrib.admin.views.decorators import staff_member_required

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

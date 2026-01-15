import logging

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError, NoCredentialsError
from typing import Optional, BinaryIO
from config_data.config import ConfigEnv, load_config

config: ConfigEnv = load_config()
logger = logging.getLogger(__name__)


# Конфигурация S3 клиента
s3_client = boto3.client(
    's3',
    config=Config(signature_version='s3v4'),
    endpoint_url=config.s3.url,
    aws_access_key_id=config.s3.key_id,
    aws_secret_access_key=config.s3.key_secret,
)


async def upload_to_s3(
        file_stream: BinaryIO,
        file_name: str,
        bucket_name: Optional[str] = None,
        expiration: int = 12600
) -> Optional[str]:
    """
    Загружает файл в S3 и возвращает КЛЮЧ файла (не presigned URL)

    Args:
        file_stream: Поток файла
        file_name: Ключ файла в S3 (например: "717150843/photo.jpg")
        bucket_name: Имя бакета
        expiration: Время для временной генерации URL (для отладки)

    Returns:
        Ключ файла в S3 (file_name) если успешно, None в случае ошибки
    """
    bucket_name = bucket_name or config.s3.name

    try:
        # Загружаем файл
        s3_client.upload_fileobj(file_stream, bucket_name, file_name)
        logger.info(f'✅ Файл {file_name} успешно загружен в S3')

        # Возвращаем КЛЮЧ файла, а не URL
        # URL будет генерироваться динамически при необходимости
        return file_name

    except ClientError as e:
        error_code = e.response.get('Error', {}).get('Code', 'Unknown')
        error_message = e.response.get('Error', {}).get('Message', str(e))
        logger.error(f"❌ Ошибка S3 ({error_code}): {error_message}")
        return None

    except Exception as e:
        logger.error(f"❌ Ошибка загрузки в S3: {type(e).__name__}: {e}")
        return None


async def get_presigned_url(key: str, expires_in: int = 3600) -> Optional[str]:
    """
    Генерирует presigned URL для файла в S3

    Args:
        key: Ключ файла в S3 (например: "717150843/photo.jpg")
        expires_in: Время жизни URL в секундах (по умолчанию 1 час)

    Returns:
        Presigned URL или None
    """
    try:
        url = s3_client.generate_presigned_url(
            ClientMethod='get_object',
            Params={
                'Bucket': config.s3.name,
                'Key': key
            },
            ExpiresIn=expires_in
        )
        return url

    except Exception as e:
        logger.error(f"❌ Ошибка генерации URL для {key}: {e}")
        return None


def extract_s3_key_from_url(url: str) -> Optional[str]:
    """
    Извлекает ключ файла из presigned URL (для обратной совместимости)

    Args:
        url: Presigned URL или ключ файла

    Returns:
        Ключ файла в S3

    Example:
        >>> extract_s3_key_from_url("https://s3.ru/bucket/717150843/photo.jpg?X-Amz...")
        "717150843/photo.jpg"
    """
    if not url:
        return None

    # Если это уже ключ (без протокола), возвращаем как есть
    if not url.startswith('http'):
        return url

    try:
        from urllib.parse import urlparse
        parsed = urlparse(url)
        # Извлекаем путь и убираем ведущий слеш
        key = parsed.path.lstrip('/')
        # Убираем имя бакета если оно в пути
        if '/' in key:
            parts = key.split('/', 1)
            # Если первая часть похожа на имя бакета, берем вторую
            if len(parts) > 1:
                return parts[1] if parts[0] == config.s3.name else key
        return key
    except Exception as e:
        logger.error(f"Ошибка извлечения ключа из URL {url}: {e}")
        return None
from app.service.redis_client import redis


# функция троттлинга
async def check_throttle(user_id: int, message_text: str, throttle_time: int = 2) -> bool:
    key = f"throttle:{user_id}:{message_text}"
    is_throttled = await redis.get(key)

    if is_throttled:
        return True

    await redis.set(key, '1', ex=throttle_time)
    return False






from django.http import JsonResponse
from django.db import connections
from django.db.utils import OperationalError
import redis
import os

def healthcheck(request):
    checks = {}

    # PostgreSQL check
    try:
        connections['default'].cursor()
        checks['db'] = 'ok'
    except OperationalError:
        checks['db'] = 'error'

    # Redis check
    try:
        r = redis.Redis(
            host=os.getenv("REDIS_HOST", "redis"),
            port=int(os.getenv("REDIS_PORT", 6379)),
            password=os.getenv("REDIS_PASSWORD", None),
            decode_responses=True
        )
        r.ping()
        checks['redis'] = 'ok'
    except Exception:
        checks['redis'] = 'error'

    # Bot check
    try:
        bot_status = r.get("bot:heartbeat")
        if bot_status == "alive":
            checks['bot'] = 'ok'
        else:
            checks['bot'] = 'error'
    except Exception:
        checks['bot'] = 'error'

    return JsonResponse({
        "status": "ok" if all(v == 'ok' for v in checks.values()) else "error",
        "services": checks,
    })

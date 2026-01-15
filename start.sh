#!/bin/sh

# First run alembic migrations
uv run alembic upgrade head
uv run python admin_panel/manage.py migrate


# Create superuser if not exists using env variables
uv run python admin_panel/manage.py shell -c "
import os
from django.contrib.auth import get_user_model

User = get_user_model()
username = os.getenv('DJANGO_SUPERUSER_USERNAME', 'admin')
password = os.getenv('DJANGO_SUPERUSER_PASSWORD', 'adminpass')

if not User.objects.filter(username=username).exists():
    User.objects.create_superuser(username, '', password)
"


# Get the service type from the first argument
SERVICE_TYPE=$1

case $SERVICE_TYPE in
    "admin_panel")
        echo "Starting API service..."
        uv run admin_panel/manage.py runserver 0.0.0.0:8000
        ;;
    "bot")
        echo "Starting bot service..."
        uv run bot.py
        ;;
    *)
        echo "Invalid service type. Please use 'bot', 'admin_panel'"
        exit 1
        ;;
esac

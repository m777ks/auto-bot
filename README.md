# 🚗 Auto Georgian Bot

Telegram-бот для автоматизации размещения объявлений о продаже автомобилей.

## 📋 Возможности

### Для пользователей
- 🌐 Выбор языка интерфейса (RU/EN/GE)
- 📝 Отправка объявлений с текстом и медиа (фото/видео)
- 📎 Поддержка медиа-групп (альбомов)
- 💬 Общение с администраторами через бота

### Для администраторов
- 📨 Получение обращений пользователей в топики группы
- 🤖 Генерация текста объявлений с помощью GPT-4o-mini
- ✏️ Ручной ввод или корректировка текста через GPT
- 📢 Публикация объявлений в канал
- 🛡️ Автоматическая модерация канала и группы

### Django Admin Panel
- 👥 Управление пользователями
- 📝 Просмотр опубликованных постов
- 💬 История топиков пользователей
- 📊 Логирование действий

## 🛠 Технологии

- **Python 3.11+**
- **Aiogram 3.x** — Telegram Bot API
- **PostgreSQL 15** — база данных
- **Redis 7** — кэширование и FSM storage
- **SQLAlchemy 2.0** — ORM
- **Alembic** — миграции БД
- **Django 5.x** — админ-панель
- **OpenAI API** — генерация текста
- **S3 (MinIO)** — хранение медиафайлов
- **Docker Compose** — контейнеризация

## 🚀 Установка и запуск

### 1. Клонирование репозитория

```bash
git clone <repository-url>
cd auto-bot-gpt
```

### 2. Настройка окружения

Создайте файл `.env` на основе примера:

```env
# Telegram Bot
BOT_TOKEN=your_bot_token
ADMIN_IDS=123456789,987654321
TG_CHANNEL_ID=-1001234567890
TG_CHANNEL_URL=https://t.me/your_channel
TG_MESSAGE_GROUP_ID=-1001234567890
NAME_CHAT=Your_Chat_Name

# PostgreSQL
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_password
POSTGRES_DB=auto_bot_gpt
POSTGRES_HOST=db
POSTGRES_PORT=5432

# Redis
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_PASSWORD=your_redis_password

# OpenAI
OPENAI_API_KEY=sk-your-openai-key

# S3 (MinIO)
S3_ENDPOINT=https://your-s3-endpoint
S3_ACCESS_KEY=your_access_key
S3_SECRET_KEY=your_secret_key
S3_BUCKET=your_bucket

# Django
SECRET_KEY=your_django_secret_key
```

### 3. Запуск через Docker Compose

```bash
# Сборка и запуск
docker compose up -d --build

# Просмотр логов
docker compose logs -f bot

# Остановка
docker compose down
```

### 4. Миграции базы данных

```bash
# Применение миграций Alembic (для бота)
docker compose exec bot alembic upgrade head

# Создание суперпользователя Django
docker compose exec admin-panel python admin_panel/manage.py createsuperuser
```

## 📁 Структура проекта

```
auto-bot-gpt/
├── app/
│   ├── handlers/           # Обработчики сообщений
│   │   ├── admin_handlers.py   # Логика для админов
│   │   └── user_handlers.py    # Логика для пользователей
│   ├── keybords/           # Клавиатуры
│   ├── lexicon/            # Тексты и переводы
│   ├── middlewares/        # Middleware (альбомы, логирование)
│   ├── sender/             # Рассылка
│   └── service/            # Сервисы (OpenAI, Redis)
├── admin_panel/            # Django админка
│   ├── admin_panel/        # Настройки Django
│   └── bot/                # Модели и админ-интерфейс
├── config_data/            # Конфигурация
├── db/
│   ├── alembic/            # Миграции Alembic
│   ├── database.py         # Подключение к БД
│   ├── models.py           # SQLAlchemy модели
│   └── ORM.py              # ORM классы
├── s3/                     # S3 клиент
├── bot.py                  # Точка входа бота
├── docker-compose.yml
├── Dockerfile
└── pyproject.toml
```

## 🔧 Локальная разработка

```bash
# Установка зависимостей через uv
uv sync

# Запуск бота
uv run python bot.py

# Запуск админки
uv run python admin_panel/manage.py runserver 0.0.0.0:8000
```

## 📡 Nginx (production)

Пример конфигурации для проксирования админ-панели:

```nginx
server {
    listen 8081;
    server_name _;
    client_max_body_size 50m;

    location / {
        proxy_pass http://localhost:8001/;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

## 📝 Формат объявления

Бот генерирует объявления в формате:

```
Audi Q7 Premium Plus 45+
Year: 2022
Mileage: 49000 km
VIN: WA1LJBF79ND017836
Engine: 2.0 turbo
Drive: AWD Quattro
City: Tbilisi

Машина не с аукционов, куплена в салоне США.
Состояние идеальное, работает как часы.

💵 54000$
📞 +995555555555 @username
```

## 📄 Лицензия

MIT License

FROM python:3.11-alpine

WORKDIR /app


# Install PostgreSQL client libraries and build dependencies
RUN apk add --no-cache postgresql-dev gcc python3-dev musl-dev


RUN pip install uv


COPY pyproject.toml .
COPY uv.lock .

RUN uv sync --frozen --no-install-project


COPY . .

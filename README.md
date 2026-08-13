# Ternopil Events Bot

Telegram-бот для агрегування культурних та розважальних подій Тернополя.

## MVP v0.1

- PostgreSQL-модель подій, майданчиків та джерел
- Telegram-бот з меню
- Collector architecture для різних джерел
- Перший адаптер KARABAS
- Дедуплікація подій
- Відстеження `first_seen_at` / `last_seen_at` для майбутнього моніторингу початку продажу
- Docker Compose для локального запуску

## Структура

```text
app/
  bot/          Telegram handlers
  collectors/   collectors/adapters for event sources
  db/           SQLAlchemy models and session
  services/     normalization and event upsert logic
  config.py
  main.py
tests/
docker-compose.yml
pyproject.toml
.env.example
```

## Запуск

1. Створити Telegram bot через BotFather і отримати token.
2. Скопіювати `.env.example` у `.env`.
3. Запустити:

```bash
docker compose up -d db
python -m venv .venv
source .venv/bin/activate
pip install -e "[dev]"
python -m app.main
```

Для Windows:

```powershell
.venv\Scripts\activate
pip install -e "[dev]"
```

## Важливо

Парсер навмисно ізольований від решти системи. Якщо структура KARABAS зміниться, достатньо оновити `app/collectors/karabas.py`.

Джерело KARABAS:
https://ternopil.karabas.com/

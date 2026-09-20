# Ternopil Events Bot

Telegram-бот для агрегування культурних та розважальних подій Тернополя.

## Production architecture

Система збирає події з реєстру наявних production collectors у PostgreSQL, нормалізує їх і використовує спільну canonical identity/dedup логіку для ingest, quality reporting та user-facing queries. Telegram delivery і daily digest працюють окремими workflow від collection, щоб збій окремого collector не змінював робочу доставку без необхідності.

### Source tiers

Tier — це operational policy на основі production evidence, а не факт існування adapter-а:

- `core` — production-здорові джерела, збій яких впливає на aggregate collection health;
- `secondary` — корисні production-джерела, які збираються та вимірюються, але їх деградація не робить увесь ingest непридатним;
- `quarantined` — підтверджено деградовані джерела; вони залишаються у collection/health reporting, щоб не втрачати корисні дані та бачити відновлення без speculative parser patches;
- `candidate` — adapter-и поза production registry; вони не додаються до production без окремого evidence-based рішення.

Поточна класифікація є єдиним джерелом істини в `app/collectors/registry.py`. Не дублюйте списки source tiers у документації.

### Production health і source value

Collection ізолює non-core failures: `secondary`/`quarantined` source може бути `down` або `degraded` і залишатися видимим у health report, не маскуючи стан справних core sources. Source value оцінюється не лише raw count: production reporting використовує canonical/unique events, overlap, recent failure rate/health signals та фактичне покриття. Окремо reporting показує field coverage для `start_at`, venue, address, price, ticket URL і description; ці показники є observability-сигналами, а не quality gates, бо частина полів може бути легітимно відсутня у джерелі.

Нові джерела не слід додавати лише для збільшення raw count. Спочатку мають бути стабільні collection/fault isolation, source tiers, canonicalization/dedup і quality gates.

## CI та workflows

- `Tests` є PR quality gate і також доступний через ручний `workflow_dispatch`; повний suite навмисно не повторюється автоматично після merge у `main`.
- production collection запускається окремим workflow і формує health/value/quality signals;
- Telegram notification delivery та daily digest є окремими production workflows;
- parser/collector fixes робляться лише за production evidence і з regression coverage.

Зміни merge-яться лише після green PR CI. Після merge production ефект вважається підтвердженим тільки після відповідного collection/Telegram signal; відсутність нового run не слід трактувати як success.

## Структура

```text
app/
  bot/          Telegram handlers and delivery logic
  collectors/   source adapters and production registry/tier policy
  db/           SQLAlchemy models and session
  services/     normalization, canonicalization and event upsert logic
  config.py
  main.py
scripts/         collection/quality/operational reporting commands
tests/           regression and policy coverage
.github/workflows/
docker-compose.yml
pyproject.toml
.env.example
```

## Локальний запуск

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

## Operational principles

- Не розширювати source portfolio, поки production pipeline не стабільний.
- Не видаляти корисні дані через деградацію source: змінювати tier/status за evidence.
- Не робити speculative parser patches.
- Canonicalization/dedup semantics мають бути спільними для ingest, reports і user-facing queries.
- Regression tests обов'язкові для змін production behavior або operational policy.

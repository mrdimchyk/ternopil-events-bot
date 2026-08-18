from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import settings

database_url = settings.database_url

if database_url.startswith("postgresql://"):
    database_url = database_url.replace("postgresql://", "postgresql+psycopg://", 1)

engine = create_engine(database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def _repair_telegram_id_columns() -> None:
    """Bring legacy Telegram ID columns to BIGINT after model type changes."""
    if engine.dialect.name != "postgresql":
        return

    inspector = inspect(engine)
    tables = {
        "favorites": "user_id",
        "notification_subscriptions": "user_id",
    }
    with engine.begin() as connection:
        for table, column in tables.items():
            if inspector.has_table(table):
                connection.execute(
                    text(f'ALTER TABLE "{table}" ALTER COLUMN "{column}" TYPE BIGINT')
                )


def init_db() -> None:
    from app.db import models  # noqa: F401
    from app.db import user_models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    _repair_telegram_id_columns()

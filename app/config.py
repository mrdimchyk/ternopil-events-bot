from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    telegram_bot_token: str = ""
    database_url: str = "postgresql+psycopg://events:events@localhost:5432/events"
    city_name: str = "Ternopil"
    timezone: str = "Europe/Kyiv"
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()

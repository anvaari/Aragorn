from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_ignore_empty= False,
        env_file=".env",
        env_file_encoding='utf-8'
    )

    telegram_bot_token: str = Field(..., alias="telegram_bot_tk")
    telegram_chat_id: str = Field(..., alias="telegram_chat")
    openai_api_key: str = Field(..., alias="openai_api_k")
    aragorn_token: str = Field(...,alias="aragorn_tk")
    telegram_proxy: str = Field(...,alias="telegram_proxy")
    log_level: str
    database_file_path: str

app_settings = Settings() # type: ignore


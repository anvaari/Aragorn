from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_ignore_empty=True,
        env_file=".env",
        env_file_encoding='utf-8'
    )

    telegram_bot_token: str = Field(..., alias="telegram_bot_tk")
    telegram_chat_id: str = Field(..., alias="telegram_chat")

    openai_api_key: str = Field(..., alias="openai_api_k")
    openai_model: str = Field(...,alias="openai_model")

    instaloader_login_file:str = Field(...,alias="instaloader_login_file")
    instagram_username:str = Field(...,alias="instagram_username")

    aragorn_token: str = Field(...,alias="aragorn_tk")

    tg_gpt_ig_proxy: str = Field(...,alias="tg_gpt_ig_proxy")

    log_level: str = Field(...,alias="log_level")
    database_file_path: str = Field(...,alias="database_file_path")

app_settings = Settings() # type: ignore


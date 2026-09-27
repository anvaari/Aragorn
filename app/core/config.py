from datetime import datetime

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import BaseModel, Field, field_validator


class DigestSchedule(BaseModel):
    time: str  # "HH:MM" 24h, interpreted in digest_timezone
    day_offset: int = 0  # 0 = today's events, 1 = tomorrow's, ...

    @field_validator("time")
    @classmethod
    def _valid_hhmm(cls, v: str) -> str:
        datetime.strptime(v, "%H:%M")  # raises ValueError -> fail fast at startup
        return v


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_ignore_empty= False,
        env_file=".env",
        env_file_encoding='utf-8'
    )

    telegram_bot_token: str = Field(..., alias="telegram_bot_tk")
    telegram_chat_id: str = Field(..., alias="telegram_chat")

    openai_api_key: str = Field(..., alias="openai_api_k")
    openai_text_model: str = Field(...,alias="openai_text_model")
    openai_image_model: str = Field(...,alias="openai_image_model")

    instagram_login_session_file: str = Field(...,alias="instagram_login_session_file")

    aragorn_token: str = Field(...,alias="aragorn_tk")

    tg_gpt_ig_proxy: str = Field(...,alias="tg_gpt_ig_proxy")

    log_level: str = Field(...,alias="log_level")
    database_file_path: str = Field(...,alias="database_file_path")

    digest_enabled: bool = Field(default=True, alias="digest_enabled")
    digest_timezone: str = Field(default="Asia/Tehran", alias="digest_timezone")
    digest_schedules: list[DigestSchedule] = Field(
        default_factory=lambda: [DigestSchedule(time="12:00", day_offset=0)],
        alias="digest_schedules",
    )

    # Public @username of the Aragorn Telegram channel, WITHOUT the leading @.
    # Empty -> digest titles render as plain text (no t.me links).
    telegram_channel_username: str = Field(default="", alias="telegram_channel_username")

app_settings = Settings() # type: ignore


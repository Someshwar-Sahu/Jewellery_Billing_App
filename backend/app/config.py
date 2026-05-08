from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    DATABASE_URL: str
    SECRET_KEY: str
    APP_NAME: str = "Jewellery Billing App"
    GOOGLE_API_KEY: Optional[str] = None

    class Config:
        env_file = ".env"

settings = Settings()
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL: str
    SECRET_KEY: str
    APP_NAME: str = "Jewellery Billing App"

    class Config:
        env_file = ".env"

settings = Settings()
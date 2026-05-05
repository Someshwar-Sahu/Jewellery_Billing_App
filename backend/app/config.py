from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL: str
    SECRET_KEY: str
    APP_NAME: str = "Jewellery Billing App"
    GOOGLE_API_KEY: str

    class Config:
        env_file = ".env"

settings = Settings()
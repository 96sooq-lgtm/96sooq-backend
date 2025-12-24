from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    # API Configuration
    api_port: int = 8000
    debug: bool = True
    
    # Supabase Configuration
    supabase_url: Optional[str] = None
    supabase_key: Optional[str] = None
    
    # JWT/Auth
    jwt_secret: Optional[str] = None
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    
    # Database
    database_url: Optional[str] = None
    
    class Config:
        env_file = ".env"
        case_sensitive = False

settings = Settings()

from pydantic_settings import BaseSettings
from typing import Optional
from pydantic import Field

class Settings(BaseSettings):
    # API Configuration
    api_port: int = 8000
    debug: bool = True
    
    # Supabase Configuration
    supabase_url: Optional[str] = None
    supabase_service_role_key: str
    
    # JWT/Auth
    secret_key: str = "your-secret-key-CHANGE-IN-PRODUCTION"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    
    # Database
    database_url: Optional[str] = None
    
    # S3 Storage Configuration
    aws_access_key_id: Optional[str] = None
    aws_secret_access_key: Optional[str] = None
    aws_region: str = "us-east-1"
    aws_bucket_name: Optional[str] = None
    aws_endpoint_url: Optional[str] = None # For Supabase/MinIO
    cloudfront_url: Optional[str] = None # For CloudFront CDN
    s3_signature_version: str = "s3v4"
    
    class Config:
        env_file = ".env"
        case_sensitive = False

settings = Settings()

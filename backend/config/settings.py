from pydantic_settings import BaseSettings
from typing import Optional
from pydantic import Field

class Settings(BaseSettings):
    # API Configuration
    api_port: int = 8000
    debug: bool = True
    
    # Supabase Configuration
    supabase_url: Optional[str] = None
    supabase_service_role_key: Optional[str] = None # Make optional if not always needed, or ensure it's in .env
    supabase_key: Optional[str] = None # Added matches .env SUPABASE_KEY

    # JWT/Auth — reads from JWT_SECRET env var (used in .env and Render)
    secret_key: str = Field(default="your-secret-key-CHANGE-IN-PRODUCTION", alias="JWT_SECRET")
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

    # Paymob Configuration
    paymob_api_key: str = "test_api_key"
    paymob_public_key: str = "test_public_key"  # omn_pk_test_... from Dashboard
    paymob_integration_id: str = "test_integration_id"
    paymob_iframe_id: str = "test_iframe_id"
    paymob_hmac_secret: str = "test_hmac_secret"
    paymob_secret_key: str = "test_secret_key"  # omn_sk_test_... for Intention API

    
    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "ignore"
        populate_by_name = True  # Allow both field name and alias

settings = Settings()

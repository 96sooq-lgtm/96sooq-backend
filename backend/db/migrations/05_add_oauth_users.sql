-- Migration to support OAuth login (Google, etc.)
-- Ensure app_users table has necessary columns

-- Add provider (google, apple, facebook)
ALTER TABLE public.app_users ADD COLUMN IF NOT EXISTS provider TEXT DEFAULT 'phone';

-- Add provider_id (unique ID from provider)
ALTER TABLE public.app_users ADD COLUMN IF NOT EXISTS provider_id TEXT;

-- Add email (optional for phone users but required for OAuth)
ALTER TABLE public.app_users ADD COLUMN IF NOT EXISTS email TEXT;

-- Add profile_picture
ALTER TABLE public.app_users ADD COLUMN IF NOT EXISTS profile_picture TEXT;

-- Add unique constraint for provider + provider_id to prevent duplicates
-- Note: A user might have multiple providers, but provider_id is unique per provider
-- We might want a composite unique index
CREATE UNIQUE INDEX IF NOT EXISTS idx_app_users_provider_id ON public.app_users(provider, provider_id);

-- Add unique index for email if not null (optional, depending on business logic)
-- CREATE UNIQUE INDEX IF NOT EXISTS idx_app_users_email ON public.app_users(email) WHERE email IS NOT NULL;

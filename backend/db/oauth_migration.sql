-- OAuth Support Migration
-- Add OAuth columns to app_users table

ALTER TABLE app_users ADD COLUMN IF NOT EXISTS provider TEXT DEFAULT 'phone';
ALTER TABLE app_users ADD COLUMN IF NOT EXISTS provider_id TEXT;
ALTER TABLE app_users ADD COLUMN IF NOT EXISTS email TEXT;
ALTER TABLE app_users ADD COLUMN IF NOT EXISTS profile_picture TEXT;

-- Make phone_number optional (for OAuth users)
ALTER TABLE app_users ALTER COLUMN phone_number DROP NOT NULL;

-- Add unique constraint on provider + provider_id
CREATE UNIQUE INDEX IF NOT EXISTS idx_app_users_provider ON app_users(provider, provider_id) WHERE provider_id IS NOT NULL;

-- Add index on email for quick lookups
CREATE INDEX IF NOT EXISTS idx_app_users_email ON app_users(email) WHERE email IS NOT NULL;

-- Comments for clarity
COMMENT ON COLUMN app_users.provider IS 'Authentication provider: phone, google, apple, facebook';
COMMENT ON COLUMN app_users.provider_id IS 'Unique ID from OAuth provider';

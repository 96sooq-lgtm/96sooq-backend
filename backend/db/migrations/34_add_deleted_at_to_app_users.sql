-- Migration: Add deleted_at column to app_users
-- Purpose: Distinguish user-initiated account deletion from admin blocks.
--   - deleted_at IS NOT NULL  →  user deleted their own account (can re-login)
--   - deleted_at IS NULL + is_active = false  →  admin-blocked (stays blocked)
--
-- This is a non-destructive, additive migration. No existing data is modified.

ALTER TABLE public.app_users ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMP WITH TIME ZONE;

-- Optional index for quick lookups on soft-deleted users
CREATE INDEX IF NOT EXISTS idx_app_users_deleted_at ON public.app_users(deleted_at) WHERE deleted_at IS NOT NULL;

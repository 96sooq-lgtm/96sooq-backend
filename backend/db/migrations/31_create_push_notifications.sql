-- =========================================================
-- Migration 31: Push Notification System (FCM)
-- =========================================================

-- 1. Device Tokens — stores FCM tokens per user (multi-device support)
CREATE TABLE IF NOT EXISTS device_tokens (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES app_users(id) ON DELETE CASCADE,
    fcm_token TEXT NOT NULL,
    device_type TEXT DEFAULT 'mobile',  -- 'mobile', 'web'
    device_name TEXT,                    -- e.g. 'iPhone 15', 'Samsung Galaxy S24'
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Unique constraint: one token per device per user
CREATE UNIQUE INDEX IF NOT EXISTS idx_device_tokens_unique 
    ON device_tokens(user_id, fcm_token);

-- Index for fast lookup by user
CREATE INDEX IF NOT EXISTS idx_device_tokens_user 
    ON device_tokens(user_id) WHERE is_active = TRUE;

-- 2. Notifications — stores notification history for the user
CREATE TABLE IF NOT EXISTS notifications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES app_users(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    body TEXT NOT NULL,
    type TEXT NOT NULL,                  -- 'payment_success', 'listing_approved', 'new_message'
    data JSONB DEFAULT '{}',             -- extra payload (listing_id, conversation_id, etc.)
    is_read BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index for user inbox (newest first, unread first)
CREATE INDEX IF NOT EXISTS idx_notifications_user 
    ON notifications(user_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_notifications_unread 
    ON notifications(user_id) WHERE is_read = FALSE;

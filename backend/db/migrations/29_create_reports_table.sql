-- Migration 29: Create user_reports table for reporting listings and users
-- Supports three report targets: listing, user, and conversation (already has conversation_reports)

CREATE TABLE IF NOT EXISTS user_reports (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    reported_by UUID NOT NULL REFERENCES app_users(id) ON DELETE CASCADE,
    target_type TEXT NOT NULL CHECK (target_type IN ('listing', 'user')),
    listing_id  UUID REFERENCES listings(id) ON DELETE CASCADE,
    target_user_id UUID REFERENCES app_users(id) ON DELETE CASCADE,
    reason      TEXT NOT NULL CHECK (char_length(reason) BETWEEN 5 AND 1000),
    status      TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'reviewed', 'dismissed')),
    admin_note  TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Enforce only one active report per reporter+target
    CONSTRAINT unique_listing_report  UNIQUE (reported_by, listing_id),
    CONSTRAINT unique_user_report     UNIQUE (reported_by, target_user_id),

    -- Ensure target is set correctly per type
    CONSTRAINT target_listing_set CHECK (
        target_type != 'listing' OR (listing_id IS NOT NULL AND target_user_id IS NULL)
    ),
    CONSTRAINT target_user_set CHECK (
        target_type != 'user' OR (target_user_id IS NOT NULL AND listing_id IS NULL)
    )
);

-- Enable RLS
ALTER TABLE user_reports ENABLE ROW LEVEL SECURITY;

-- Users can only see and insert their own reports
CREATE POLICY "users_own_reports" ON user_reports
    FOR ALL USING (reported_by = auth.uid());

-- Admins have full access via service role key (no policy needed for service role)

-- Index for admin listing
CREATE INDEX IF NOT EXISTS idx_user_reports_status   ON user_reports(status);
CREATE INDEX IF NOT EXISTS idx_user_reports_reporter ON user_reports(reported_by);
CREATE INDEX IF NOT EXISTS idx_user_reports_listing  ON user_reports(listing_id);
CREATE INDEX IF NOT EXISTS idx_user_reports_target   ON user_reports(target_user_id);

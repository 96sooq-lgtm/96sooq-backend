-- Migration: Create search_logs and add user language preference
-- 32_create_search_logs.sql

-- 1. Create Search Logs Table
CREATE TABLE IF NOT EXISTS search_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    query TEXT UNIQUE NOT NULL,
    count INTEGER DEFAULT 1,
    last_searched_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_search_logs_count ON search_logs(count DESC);
CREATE INDEX IF NOT EXISTS idx_search_logs_query ON search_logs(query);

-- 2. Add Language to app_users
-- Assuming app_users is the table for mobile application users
ALTER TABLE app_users ADD COLUMN IF NOT EXISTS language TEXT DEFAULT 'en';

-- 3. Add comment
COMMENT ON TABLE search_logs IS 'Tracks search query frequency for popular searches feature.';
COMMENT ON COLUMN app_users.language IS 'User preference for English (en) or Arabic (ar).';

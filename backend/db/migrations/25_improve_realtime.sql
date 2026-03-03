-- ================================================================
-- Migration 25: Correct Realtime Configuration (Robust Version)
-- Ensuring full payloads are sent during database change events.
-- ================================================================

-- 1. Safely add tables to publication if not already present
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_publication_tables 
        WHERE pubname = 'supabase_realtime' AND tablename = 'messages'
    ) THEN
        ALTER PUBLICATION supabase_realtime ADD TABLE messages;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_publication_tables 
        WHERE pubname = 'supabase_realtime' AND tablename = 'conversations'
    ) THEN
        ALTER PUBLICATION supabase_realtime ADD TABLE conversations;
    END IF;
END $$;

-- 2. CRITICAL: Ensure ALL data is sent in the Realtime payload
-- This is what allows the frontend to update instantly without a reload.
ALTER TABLE messages      REPLICA IDENTITY FULL;
ALTER TABLE conversations REPLICA IDENTITY FULL;

-- ================================================================
-- Migration 25: Correct Realtime Configuration
-- Ensures that all columns are sent in the Realtime message payload.
-- ================================================================

-- 1. Ensure tables are in the Realtime Publication
-- This enables the "Postgres Changes" feature for these tables.
DO $realtime$
BEGIN
    ALTER PUBLICATION supabase_realtime ADD TABLE messages;
EXCEPTION WHEN others THEN NULL;
END $realtime$;

DO $realtime2$
BEGIN
    ALTER PUBLICATION supabase_realtime ADD TABLE conversations;
EXCEPTION WHEN others THEN NULL;
END $realtime2$;

-- 2. Set REPLICA IDENTITY to FULL
-- By default, Postgres only sends the Primary Key for updates.
-- "FULL" forces Postgres to send the entire row, which is 
-- necessary for the frontend to update UI components immediately.
ALTER TABLE messages      REPLICA IDENTITY FULL;
ALTER TABLE conversations REPLICA IDENTITY FULL;

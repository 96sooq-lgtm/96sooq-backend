-- Migration 32: Add favorites_count to listings table
-- This allows for efficient display of favorite counts without counting rows every time.

ALTER TABLE listings ADD COLUMN IF NOT EXISTS favorites_count INTEGER DEFAULT 0;

-- Backfill existing counts
UPDATE listings l
SET favorites_count = (
    SELECT count(*)
    FROM favorites f
    WHERE f.listing_id = l.id
);

-- Index for sorting by popularity (optional but useful)
CREATE INDEX IF NOT EXISTS idx_listings_favorites_count ON listings(favorites_count DESC);

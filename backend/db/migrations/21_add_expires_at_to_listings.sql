-- Add expires_at to listings
ALTER TABLE listings ADD COLUMN IF NOT EXISTS expires_at TIMESTAMP WITH TIME ZONE;
CREATE INDEX IF NOT EXISTS idx_listings_expires_at ON listings(expires_at);

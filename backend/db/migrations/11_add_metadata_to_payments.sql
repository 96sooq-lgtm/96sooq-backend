-- Add metadata column to payments table for bundle details
ALTER TABLE payments ADD COLUMN IF NOT EXISTS metadata JSONB DEFAULT '{}';

-- Add index for metadata (optional, but good for searching by listing_id within payments)
CREATE INDEX IF NOT EXISTS idx_payments_metadata ON payments USING gin (metadata);

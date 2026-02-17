-- Add name_ar, location_id, and place to stores table
ALTER TABLE stores ADD COLUMN IF NOT EXISTS name_ar TEXT;
ALTER TABLE stores ADD COLUMN IF NOT EXISTS location_id UUID REFERENCES locations(id);
ALTER TABLE stores ADD COLUMN IF NOT EXISTS place TEXT;

-- Add condition and place to listings table
-- condition: new, used
ALTER TABLE listings ADD COLUMN IF NOT EXISTS condition TEXT CHECK (condition IN ('new', 'used'));
ALTER TABLE listings ADD COLUMN IF NOT EXISTS place TEXT;

-- Index for condition
CREATE INDEX IF NOT EXISTS idx_listings_condition ON listings(condition);

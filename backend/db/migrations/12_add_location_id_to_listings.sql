-- Add location_id to listings table to link with locations (governorates)
ALTER TABLE listings ADD COLUMN IF NOT EXISTS location_id UUID REFERENCES locations(id);

-- Create index for faster filtering by location
CREATE INDEX IF NOT EXISTS idx_listings_location_id ON listings(location_id);

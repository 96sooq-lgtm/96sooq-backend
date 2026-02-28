-- Add latitude and longitude to locations table for geo-resolution
ALTER TABLE public.locations ADD COLUMN IF NOT EXISTS latitude DECIMAL(10, 7);
ALTER TABLE public.locations ADD COLUMN IF NOT EXISTS longitude DECIMAL(10, 7);

-- Index for coordinate queries
CREATE INDEX IF NOT EXISTS idx_locations_coordinates ON public.locations(latitude, longitude)
WHERE latitude IS NOT NULL AND longitude IS NOT NULL;

COMMENT ON COLUMN public.locations.latitude IS 'Center-point latitude for the governorate/wilayat';
COMMENT ON COLUMN public.locations.longitude IS 'Center-point longitude for the governorate/wilayat';

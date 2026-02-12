-- Create locations table for Oman State/District/City hierarchy
CREATE TABLE IF NOT EXISTS public.locations (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    name_en TEXT NOT NULL,
    name_ar TEXT NOT NULL,
    parent_id UUID REFERENCES public.locations(id),
    type TEXT NOT NULL CHECK (type IN ('state', 'district', 'city')),
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_locations_parent_id ON public.locations(parent_id);
CREATE INDEX IF NOT EXISTS idx_locations_type ON public.locations(type);
CREATE INDEX IF NOT EXISTS idx_locations_is_active ON public.locations(is_active);

-- Comments
COMMENT ON COLUMN public.locations.type IS 'Hierarchy level: state -> district -> city';

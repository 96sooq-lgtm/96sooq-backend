-- Add impressions counter and update status constraint for listing_promotions
ALTER TABLE public.listing_promotions ADD COLUMN IF NOT EXISTS impressions INTEGER DEFAULT 0;

-- Update status constraint to support 'pending' and 'paused' states
ALTER TABLE public.listing_promotions DROP CONSTRAINT IF EXISTS listing_promotions_status_check;
ALTER TABLE public.listing_promotions ADD CONSTRAINT listing_promotions_status_check
    CHECK (status IN ('active', 'pending', 'paused', 'expired', 'cancelled'));

-- Index for efficient weighted random selection
CREATE INDEX IF NOT EXISTS idx_listing_proms_impressions ON listing_promotions(impressions);

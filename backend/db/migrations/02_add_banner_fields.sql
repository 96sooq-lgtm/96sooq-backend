-- Migration to update ad_banners table
-- 1. Add type if not exists
-- 2. Add description if not exists
-- 3. Add listing_id for Ad Boosting logic

ALTER TABLE public.ad_banners ADD COLUMN IF NOT EXISTS type TEXT;
ALTER TABLE public.ad_banners ADD COLUMN IF NOT EXISTS description TEXT;

-- Add listing_id FK to listings table
ALTER TABLE public.ad_banners ADD COLUMN IF NOT EXISTS listing_id UUID REFERENCES public.listings(id);

-- Index for performance
CREATE INDEX IF NOT EXISTS idx_ad_banners_listing_id ON public.ad_banners(listing_id);

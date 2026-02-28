-- Add location targeting fields to ad_banners
-- User-boosted ads will inherit location from their listing
-- Admin banners remain global (governorate_id = NULL)

ALTER TABLE public.ad_banners ADD COLUMN IF NOT EXISTS governorate_id UUID REFERENCES public.locations(id);
ALTER TABLE public.ad_banners ADD COLUMN IF NOT EXISTS wilayat TEXT;

-- Index for location-based banner queries
CREATE INDEX IF NOT EXISTS idx_ad_banners_governorate ON public.ad_banners(governorate_id);
CREATE INDEX IF NOT EXISTS idx_ad_banners_wilayat ON public.ad_banners(wilayat);
CREATE INDEX IF NOT EXISTS idx_ad_banners_status_type ON public.ad_banners(status, type);

-- Add impressions counter for tracking
ALTER TABLE public.ad_banners ADD COLUMN IF NOT EXISTS impressions INTEGER DEFAULT 0;

-- Add ad_sub_type to pricing_plans for distinguishing ad types
-- Values: 'product_listing', 'chat_screen', 'offers' (only when type='ad')
ALTER TABLE public.pricing_plans ADD COLUMN IF NOT EXISTS ad_sub_type TEXT;

COMMENT ON COLUMN public.pricing_plans.ad_sub_type IS 'Sub-type for ad plans: product_listing, chat_screen, offers';

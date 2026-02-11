-- Add type and description columns to ad_banners table

ALTER TABLE public.ad_banners 
ADD COLUMN IF NOT EXISTS type text,
ADD COLUMN IF NOT EXISTS description text;

-- Add check constraint for banner type
ALTER TABLE public.ad_banners 
DROP CONSTRAINT IF EXISTS ad_banners_type_check;

ALTER TABLE public.ad_banners 
ADD CONSTRAINT ad_banners_type_check 
CHECK (type IN ('carousel', 'product_listing', 'top_offers', 'chat_screen'));

-- Add whatsapp_number to ad_banners for admin-created offers
ALTER TABLE ad_banners ADD COLUMN IF NOT EXISTS whatsapp_number TEXT;

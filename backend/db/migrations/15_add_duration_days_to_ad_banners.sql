-- Migration: Add duration_days column to ad_banners table
-- Stores how many days an admin banner is active, so it can be returned in responses.

ALTER TABLE public.ad_banners
    ADD COLUMN IF NOT EXISTS duration_days INTEGER DEFAULT 30;

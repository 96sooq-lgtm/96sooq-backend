-- Migration to update pricing_plans table
-- 1. Add description column
-- 2. Update type constraint to include 'ad', 'listing', 'offer'
-- 3. Add quota and target_audience for new subscription logic

-- Remove old constraint if exists
ALTER TABLE public.pricing_plans DROP CONSTRAINT IF EXISTS pricing_plans_type_check;

-- Update constraint
ALTER TABLE public.pricing_plans ADD CONSTRAINT pricing_plans_type_check 
CHECK (type IN ('listing', 'ad', 'offer'));

-- Add description
ALTER TABLE public.pricing_plans ADD COLUMN IF NOT EXISTS description TEXT;

-- New columns for quota logic
ALTER TABLE public.pricing_plans ADD COLUMN IF NOT EXISTS quota INTEGER DEFAULT 0;
ALTER TABLE public.pricing_plans ADD COLUMN IF NOT EXISTS target_audience TEXT DEFAULT 'individual'; 
-- target_audience: 'individual', 'store'

-- Add check for target_audience
ALTER TABLE public.pricing_plans DROP CONSTRAINT IF EXISTS pricing_plans_target_audience_check;
ALTER TABLE public.pricing_plans ADD CONSTRAINT pricing_plans_target_audience_check
CHECK (target_audience IN ('individual', 'store'));

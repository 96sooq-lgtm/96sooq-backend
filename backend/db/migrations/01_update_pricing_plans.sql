-- Migration to update pricing_plans table
-- 1. Add description column
-- 2. Update type check constraint to include 'ad', 'listing', 'offer'

-- Remove old check constraint
ALTER TABLE pricing_plans DROP CONSTRAINT IF EXISTS pricing_plans_type_check;

-- Add new check constraint
ALTER TABLE pricing_plans ADD CONSTRAINT pricing_plans_type_check 
CHECK (type IN ('listing', 'ad', 'offer'));

-- Add description column
ALTER TABLE pricing_plans ADD COLUMN IF NOT EXISTS description TEXT;

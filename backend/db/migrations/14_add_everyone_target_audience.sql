-- Migration: Allow 'everyone' as a valid target_audience for pricing_plans
-- Plans with target_audience = 'everyone' will be shown to both store and individual users.

ALTER TABLE public.pricing_plans DROP CONSTRAINT IF EXISTS pricing_plans_target_audience_check;

ALTER TABLE public.pricing_plans ADD CONSTRAINT pricing_plans_target_audience_check
    CHECK (target_audience IN ('individual', 'store', 'everyone'));

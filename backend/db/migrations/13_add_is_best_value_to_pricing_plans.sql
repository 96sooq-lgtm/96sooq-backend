-- Migration: Add is_best_value column to pricing_plans table
-- This flag is set by admin to highlight a plan as "Best Value" in the frontend.

ALTER TABLE public.pricing_plans
    ADD COLUMN IF NOT EXISTS is_best_value BOOLEAN NOT NULL DEFAULT FALSE;

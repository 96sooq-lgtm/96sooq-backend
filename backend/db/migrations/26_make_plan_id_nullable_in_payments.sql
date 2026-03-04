-- Migration 26: Make plan_id nullable in payments table
-- This is required because a payment might be for a bundle (metadata) 
-- or use existing quota for one item while paying for another.

ALTER TABLE payments ALTER COLUMN plan_id DROP NOT NULL;

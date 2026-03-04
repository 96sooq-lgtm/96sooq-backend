-- Create the pg_trgm extension if it doesn't already exist
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Add a GIN index to the 'title' column on the 'listings' table
-- This allows PostgreSQL to perform rapid sub-string wildcard searches 
-- when we use ILIKE '%...%' in the API.
CREATE INDEX IF NOT EXISTS idx_listings_title_trgm ON listings USING GIN(title gin_trgm_ops);

-- Also add a GIN index to the 'description' column just in case we add full-text search later
-- CREATE INDEX IF NOT EXISTS idx_listings_description_trgm ON listings USING GIN(description gin_trgm_ops);

-- Update Listings Status to include 'draft'
-- Postgres checks can be altered by dropping and re-adding
ALTER TABLE listings DROP CONSTRAINT IF EXISTS listings_status_check;
ALTER TABLE listings ADD CONSTRAINT listings_status_check 
CHECK (status IN ('draft', 'pending_approval', 'active', 'rejected', 'sold', 'expired', 'soft_deleted'));

-- Set default status to 'draft' ??? 
-- Probably better to handle this in application logic, but defaults are good.
ALTER TABLE listings ALTER COLUMN status SET DEFAULT 'draft';

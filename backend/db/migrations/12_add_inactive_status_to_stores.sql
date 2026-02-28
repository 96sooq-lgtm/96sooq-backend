-- Add 'inactive' to allowed store statuses for admin lock/unlock feature
ALTER TABLE stores DROP CONSTRAINT IF EXISTS stores_status_check;
ALTER TABLE stores ADD CONSTRAINT stores_status_check 
CHECK (status IN ('pending_approval', 'active', 'rejected', 'expired', 'inactive'));

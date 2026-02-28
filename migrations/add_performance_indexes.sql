-- Performance indexes for frequently queried columns
-- Run this against your Supabase DB

-- Favorites: frequently queried by user_id + listing_id together
CREATE INDEX IF NOT EXISTS idx_favorites_user_listing ON favorites(user_id, listing_id);

-- Store reviews: frequently queried by store_id
CREATE INDEX IF NOT EXISTS idx_store_reviews_store ON store_reviews(store_id);

-- Stores: filtered by status frequently
CREATE INDEX IF NOT EXISTS idx_stores_status ON stores(status);

-- Listings: filtered by status + store_id together (store posts tab)
CREATE INDEX IF NOT EXISTS idx_listings_status_store ON listings(status, store_id);

-- Listings: filtered by status + category_id (browse by category)
CREATE INDEX IF NOT EXISTS idx_listings_status_category ON listings(status, category_id);

-- Listing images: frequently queried by listing_id
CREATE INDEX IF NOT EXISTS idx_listing_images_listing ON listing_images(listing_id);

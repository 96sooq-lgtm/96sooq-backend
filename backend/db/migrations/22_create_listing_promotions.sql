-- Create Listing Promotions table to track active ad campaigns for listings
CREATE TABLE IF NOT EXISTS listing_promotions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    listing_id UUID REFERENCES listings(id) NOT NULL,
    plan_id UUID REFERENCES pricing_plans(id) NOT NULL,
    start_date TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    end_date TIMESTAMP WITH TIME ZONE NOT NULL,
    status TEXT DEFAULT 'active' CHECK (status IN ('active', 'expired', 'cancelled')),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes for quick lookup during feed queries
CREATE INDEX IF NOT EXISTS idx_listing_proms_listing ON listing_promotions(listing_id);
CREATE INDEX IF NOT EXISTS idx_listing_proms_status ON listing_promotions(status);
CREATE INDEX IF NOT EXISTS idx_listing_proms_end_date ON listing_promotions(end_date);

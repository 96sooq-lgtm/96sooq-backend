-- Create payments table to track transactions via Paymob
CREATE TABLE IF NOT EXISTS payments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES app_users(id) NOT NULL,
    plan_id UUID REFERENCES pricing_plans(id) NOT NULL,
    amount DECIMAL(10, 3) NOT NULL, -- Supporting 3 decimal places (e.g., OMR 12.345)
    currency VARCHAR(3) DEFAULT 'OMR',
    status TEXT NOT NULL CHECK (status IN ('pending', 'processing', 'success', 'failed', 'refunded')),
    
    -- Paymob Fields
    paymob_order_id TEXT,       -- Order ID from Paymob
    paymob_transaction_id TEXT, -- Transaction ID from webhook
    payment_method TEXT,        -- card, wallet, etc.
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_payments_user_id ON payments(user_id);
CREATE INDEX idx_payments_status ON payments(status);
CREATE INDEX idx_payments_paymob_order_id ON payments(paymob_order_id);

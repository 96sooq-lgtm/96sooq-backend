
-- ================================================================
-- Migration 24: Fix missing foreign keys in chat system
-- Fixes PGRST200 "Could not find relationship" errors during joins.
-- ================================================================

-- 1. conversations -> listings
ALTER TABLE conversations
    ADD CONSTRAINT fk_conversations_listing
    FOREIGN KEY (listing_id) REFERENCES listings(id) ON DELETE CASCADE;

-- 2. conversations -> app_users (buyer)
ALTER TABLE conversations
    ADD CONSTRAINT fk_conversations_buyer
    FOREIGN KEY (buyer_id) REFERENCES app_users(id) ON DELETE CASCADE;

-- 3. conversations -> app_users (seller)
ALTER TABLE conversations
    ADD CONSTRAINT fk_conversations_seller
    FOREIGN KEY (seller_id) REFERENCES app_users(id) ON DELETE CASCADE;

-- 4. messages -> app_users (sender)
ALTER TABLE messages
    ADD CONSTRAINT fk_messages_sender
    FOREIGN KEY (sender_id) REFERENCES app_users(id) ON DELETE CASCADE;

-- 5. conversation_reports -> app_users (reported_by)
ALTER TABLE conversation_reports
    ADD CONSTRAINT fk_reports_reported_by
    FOREIGN KEY (reported_by) REFERENCES app_users(id) ON DELETE CASCADE;

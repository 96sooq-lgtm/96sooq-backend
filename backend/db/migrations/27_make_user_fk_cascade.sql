-- Fix foreign keys referencing app_users to ON DELETE CASCADE
-- This allows deleting a user from app_users and automatically deleting all their data

-- 1. stores
ALTER TABLE public.stores DROP CONSTRAINT IF EXISTS stores_user_id_fkey;
ALTER TABLE public.stores ADD CONSTRAINT stores_user_id_fkey 
    FOREIGN KEY (user_id) REFERENCES public.app_users(id) ON DELETE CASCADE;

-- 2. listings
ALTER TABLE public.listings DROP CONSTRAINT IF EXISTS listings_user_id_fkey;
ALTER TABLE public.listings ADD CONSTRAINT listings_user_id_fkey 
    FOREIGN KEY (user_id) REFERENCES public.app_users(id) ON DELETE CASCADE;

-- 3. store_reviews
ALTER TABLE public.store_reviews DROP CONSTRAINT IF EXISTS store_reviews_reviewer_id_fkey;
ALTER TABLE public.store_reviews ADD CONSTRAINT store_reviews_reviewer_id_fkey 
    FOREIGN KEY (reviewer_id) REFERENCES public.app_users(id) ON DELETE CASCADE;

-- 4. user_subscriptions
ALTER TABLE public.user_subscriptions DROP CONSTRAINT IF EXISTS user_subscriptions_user_id_fkey;
ALTER TABLE public.user_subscriptions ADD CONSTRAINT user_subscriptions_user_id_fkey 
    FOREIGN KEY (user_id) REFERENCES public.app_users(id) ON DELETE CASCADE;

-- 5. payments
ALTER TABLE public.payments DROP CONSTRAINT IF EXISTS payments_user_id_fkey;
ALTER TABLE public.payments ADD CONSTRAINT payments_user_id_fkey 
    FOREIGN KEY (user_id) REFERENCES public.app_users(id) ON DELETE CASCADE;

-- 6. favorites
ALTER TABLE public.favorites DROP CONSTRAINT IF EXISTS favorites_user_id_fkey;
ALTER TABLE public.favorites ADD CONSTRAINT favorites_user_id_fkey 
    FOREIGN KEY (user_id) REFERENCES public.app_users(id) ON DELETE CASCADE;

-- 7. conversations (buyer_id and seller_id)
ALTER TABLE public.conversations DROP CONSTRAINT IF EXISTS conversations_buyer_id_fkey;
ALTER TABLE public.conversations ADD CONSTRAINT conversations_buyer_id_fkey 
    FOREIGN KEY (buyer_id) REFERENCES public.app_users(id) ON DELETE CASCADE;

ALTER TABLE public.conversations DROP CONSTRAINT IF EXISTS conversations_seller_id_fkey;
ALTER TABLE public.conversations ADD CONSTRAINT conversations_seller_id_fkey 
    FOREIGN KEY (seller_id) REFERENCES public.app_users(id) ON DELETE CASCADE;

-- 8. messages (sender_id)
ALTER TABLE public.messages DROP CONSTRAINT IF EXISTS messages_sender_id_fkey;
ALTER TABLE public.messages ADD CONSTRAINT messages_sender_id_fkey 
    FOREIGN KEY (sender_id) REFERENCES public.app_users(id) ON DELETE CASCADE;


-- Example deletion query by email:
-- DELETE FROM auth.users WHERE email = 'user@example.com';
-- (Deleting from auth.users cascades to app_users if that FK is also ON DELETE CASCADE, 
-- or you can delete from app_users directly if auth.users is already gone)

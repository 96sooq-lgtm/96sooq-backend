-- Add is_deleted column to categories table for soft delete support
ALTER TABLE public.categories 
ADD COLUMN IF NOT EXISTS is_deleted boolean DEFAULT false;

-- Index for performance on filtering
CREATE INDEX IF NOT EXISTS idx_categories_is_deleted ON public.categories(is_deleted);

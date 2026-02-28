-- ================================================================
-- Migration 16: Chat System — Full Reset & Rebuild
-- SAFE TO RUN: Drops and recreates everything cleanly.
-- ================================================================


-- ──────────────────────────────────────────────────────────────────
-- STEP 1: Clean slate
-- Drops in reverse dependency order to avoid FK conflicts.
-- ──────────────────────────────────────────────────────────────────

DROP TABLE IF EXISTS conversation_reports CASCADE;
DROP TABLE IF EXISTS messages             CASCADE;
DROP TABLE IF EXISTS conversations        CASCADE;

DROP FUNCTION IF EXISTS update_conversation_on_message() CASCADE;
DROP FUNCTION IF EXISTS mark_conversation_read(UUID, UUID) CASCADE;


-- ──────────────────────────────────────────────────────────────────
-- STEP 2: Create tables with full column definitions
-- ──────────────────────────────────────────────────────────────────

CREATE TABLE conversations (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    listing_id      UUID        NOT NULL,
    buyer_id        UUID        NOT NULL,
    seller_id       UUID        NOT NULL,
    status          TEXT        NOT NULL DEFAULT 'active',
    last_message    TEXT,
    last_message_at TIMESTAMPTZ,
    buyer_unread    INT         NOT NULL DEFAULT 0,
    seller_unread   INT         NOT NULL DEFAULT 0,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (listing_id, buyer_id, seller_id)
);

CREATE TABLE messages (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID        NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    sender_id       UUID        NOT NULL,
    content         TEXT,
    message_type    TEXT        NOT NULL DEFAULT 'text',
    media_url       TEXT,
    offer_amount    NUMERIC(10, 2),
    offer_status    TEXT,
    is_read         BOOLEAN     NOT NULL DEFAULT FALSE,
    is_deleted      BOOLEAN     NOT NULL DEFAULT FALSE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE conversation_reports (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID        NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    reported_by     UUID        NOT NULL,
    reason          TEXT        NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);


-- ──────────────────────────────────────────────────────────────────
-- STEP 3: Indexes
-- ──────────────────────────────────────────────────────────────────

CREATE INDEX idx_conversations_buyer   ON conversations(buyer_id,        last_message_at DESC);
CREATE INDEX idx_conversations_seller  ON conversations(seller_id,       last_message_at DESC);
CREATE INDEX idx_conversations_listing ON conversations(listing_id);
CREATE INDEX idx_messages_conversation ON messages(conversation_id,      created_at ASC);
CREATE INDEX idx_messages_sender       ON messages(sender_id);


-- ──────────────────────────────────────────────────────────────────
-- STEP 4: Row-Level Security
-- Tables are created fresh above, so no DROP POLICY needed.
-- ──────────────────────────────────────────────────────────────────

ALTER TABLE conversations         ENABLE ROW LEVEL SECURITY;
ALTER TABLE messages              ENABLE ROW LEVEL SECURITY;
ALTER TABLE conversation_reports  ENABLE ROW LEVEL SECURITY;

-- conversations: SELECT
CREATE POLICY conv_select ON conversations
    FOR SELECT USING (
        auth.uid() = buyer_id
        OR auth.uid() = seller_id
    );

-- conversations: INSERT (buyer initiates only)
CREATE POLICY conv_insert ON conversations
    FOR INSERT WITH CHECK (
        auth.uid() = buyer_id
    );

-- conversations: UPDATE (either participant)
CREATE POLICY conv_update ON conversations
    FOR UPDATE USING (
        auth.uid() = buyer_id
        OR auth.uid() = seller_id
    );

-- messages: SELECT (participants only, via subquery)
CREATE POLICY msg_select ON messages
    FOR SELECT USING (
        EXISTS (
            SELECT 1
            FROM   conversations c
            WHERE  c.id = messages.conversation_id
            AND   (c.buyer_id = auth.uid() OR c.seller_id = auth.uid())
        )
    );

-- messages: INSERT (sender must be a participant in an active conversation)
CREATE POLICY msg_insert ON messages
    FOR INSERT WITH CHECK (
        auth.uid() = sender_id
        AND EXISTS (
            SELECT 1
            FROM   conversations c
            WHERE  c.id = messages.conversation_id
            AND   (c.buyer_id = auth.uid() OR c.seller_id = auth.uid())
            AND    c.status = 'active'
        )
    );

-- messages: UPDATE (sender can soft-delete their own messages)
CREATE POLICY msg_update ON messages
    FOR UPDATE USING (
        auth.uid() = sender_id
    );

-- conversation_reports: INSERT (participants can report)
CREATE POLICY report_insert ON conversation_reports
    FOR INSERT WITH CHECK (
        EXISTS (
            SELECT 1
            FROM   conversations c
            WHERE  c.id = conversation_reports.conversation_id
            AND   (c.buyer_id = auth.uid() OR c.seller_id = auth.uid())
        )
    );


-- ──────────────────────────────────────────────────────────────────
-- STEP 5: Trigger function — update unread counts on new message
--
-- Uses plain scalar variables to avoid any column-resolution
-- ambiguity inside the UPDATE SET clause.
-- ──────────────────────────────────────────────────────────────────

CREATE FUNCTION update_conversation_on_message()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    v_buyer_id      UUID;
    v_seller_id     UUID;
    v_buyer_unread  INT;
    v_seller_unread INT;
    v_preview       TEXT;
BEGIN
    -- Read relevant fields into scalar variables (unambiguous in UPDATE below)
    SELECT buyer_id,   seller_id,   buyer_unread,   seller_unread
    INTO   v_buyer_id, v_seller_id, v_buyer_unread, v_seller_unread
    FROM   conversations
    WHERE  id = NEW.conversation_id;

    -- Build a short preview for the inbox
    v_preview := CASE
        WHEN NEW.content IS NOT NULL    THEN NEW.content
        WHEN NEW.message_type = 'image' THEN '[Photo]'
        WHEN NEW.message_type = 'offer' THEN '[Offer]'
        ELSE                                 '[Message]'
    END;

    -- Update the conversation summary row
    UPDATE conversations
    SET
        last_message    = v_preview,
        last_message_at = NEW.created_at,
        buyer_unread    = CASE
                              WHEN NEW.sender_id != v_buyer_id  THEN v_buyer_unread  + 1
                              ELSE 0
                          END,
        seller_unread   = CASE
                              WHEN NEW.sender_id != v_seller_id THEN v_seller_unread + 1
                              ELSE 0
                          END
    WHERE id = NEW.conversation_id;

    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_message_inserted
    AFTER INSERT ON messages
    FOR EACH ROW
    EXECUTE FUNCTION update_conversation_on_message();


-- ──────────────────────────────────────────────────────────────────
-- STEP 6: Helper function — mark conversation as read
-- ──────────────────────────────────────────────────────────────────

CREATE FUNCTION mark_conversation_read(conv_id UUID, reader_id UUID)
RETURNS VOID
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    v_buyer_id  UUID;
    v_seller_id UUID;
BEGIN
    SELECT buyer_id,   seller_id
    INTO   v_buyer_id, v_seller_id
    FROM   conversations
    WHERE  id = conv_id;

    -- Only reset the counter for the real participant
    IF v_buyer_id = reader_id OR v_seller_id = reader_id THEN
        UPDATE conversations
        SET
            buyer_unread  = CASE WHEN v_buyer_id  = reader_id THEN 0 ELSE buyer_unread  END,
            seller_unread = CASE WHEN v_seller_id = reader_id THEN 0 ELSE seller_unread END
        WHERE id = conv_id;
    END IF;
END;
$$;


-- ──────────────────────────────────────────────────────────────────
-- STEP 7: Realtime
-- Errors are suppressed — if the table is already in the publication
-- it just means Realtime was previously enabled (that's fine).
-- ──────────────────────────────────────────────────────────────────

DO $realtime$
BEGIN
    ALTER PUBLICATION supabase_realtime ADD TABLE messages;
EXCEPTION WHEN others THEN NULL;
END $realtime$;

DO $realtime2$
BEGIN
    ALTER PUBLICATION supabase_realtime ADD TABLE conversations;
EXCEPTION WHEN others THEN NULL;
END $realtime2$;

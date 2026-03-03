"""
Chat Routes — 96sooq
Handles conversation initiation (Make Deal) and all REST chat operations.

Architecture:
  - FastAPI handles: initiate, inbox meta, history fetch, read-mark, block, report
  - Supabase Realtime handles: live message delivery (client subscribes directly)
  - DB trigger handles: unread counts + last_message updates automatically

Flow:
  Buyer → POST /api/chats/initiate → get conversation_id
  Client → subscribe supabase.channel('conversation:{id}')
  Client → INSERT into messages (direct Supabase, low-latency)
  Trigger → updates conversations.buyer_unread / seller_unread
"""
from fastapi import APIRouter, HTTPException, Depends, Query
from db.supabase_client import db
from utils.auth import get_current_customer, get_current_admin
from utils.logger import get_logger
from models.schemas import (
    ConversationInitiate, ConversationOut, ConversationListResponse,
    MessageCreate, MessageOut,
)
from utils.helpers import batch_listings, batch_conversations
from typing import List, Optional

logger = get_logger(__name__)

# ── Public (authenticated customer) router ──────────────────────────────────
router = APIRouter(
    prefix="/api/chats",
    tags=["chats"],
)

# ── Admin router ────────────────────────────────────────────────────────────
admin_router = APIRouter(
    prefix="/api/admin/chats",
    tags=["admin-chats"],
    dependencies=[Depends(get_current_admin)],
)


# ─────────────────────────────────────────────────────────────────────────────
# HELPER
# ─────────────────────────────────────────────────────────────────────────────

def _assert_participant(conv: dict, user_id: str) -> None:
    """Raise 403 if user is not buyer or seller in the conversation."""
    if conv["buyer_id"] != user_id and conv["seller_id"] != user_id:
        raise HTTPException(status_code=403, detail="Access denied")


def _get_conv_or_404(conversation_id: str) -> dict:
    """Fetch conversation or raise 404."""
    conv = db.select_one("conversations", conversation_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conv


# ─────────────────────────────────────────────────────────────────────────────
# CUSTOMER ENDPOINTS
# ─────────────────────────────────────────────────────────────────────────────

@router.post(
    "/initiate",
    response_model=ConversationOut,
    status_code=201,
    summary="Make Deal — initiate or resume a chat about a listing",
)
def initiate_chat(
    payload: ConversationInitiate,
    current_user: dict = Depends(get_current_customer),
):
    """
    Called when buyer taps 'Make Deal' on a listing.

    Idempotent: returns the existing conversation if one already exists
    for this buyer+listing combination. Safe to call multiple times.
    """
    buyer_id = current_user["id"]

    # 1. Verify listing is active
    listing = db.select_one("listings", payload.listing_id)
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")
    if listing["status"] != "active":
        raise HTTPException(status_code=400, detail="Listing is not available for chat")

    seller_id = listing["user_id"]

    # 2. Block self-chat
    if buyer_id == seller_id:
        raise HTTPException(status_code=400, detail="You cannot chat about your own listing")

    # 3. Return existing conversation (idempotent — one chat per buyer+listing)
    existing = db.select(
        "conversations",
        filters={
            "listing_id": payload.listing_id,
            "buyer_id": buyer_id,
            "seller_id": seller_id,
        },
    )
    if existing:
        logger.info(f"Returning existing chat: conv={existing[0]['id']}, buyer={buyer_id}")
        return existing[0]

    # 4. Create new conversation
    conversation = db.insert("conversations", {
        "listing_id": payload.listing_id,
        "buyer_id": buyer_id,
        "seller_id": seller_id,
        "status": "active",
    })
    if not conversation:
        raise HTTPException(status_code=500, detail="Failed to create conversation")

    logger.info(
        f"Chat initiated: conv={conversation['id']}, "
        f"buyer={buyer_id}, listing={payload.listing_id}"
    )
    return conversation


@router.get(
    "/inbox",
    response_model=ConversationListResponse,
    summary="Get all conversations for the current user (inbox)",
)
def get_inbox(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=50),
    current_user: dict = Depends(get_current_customer),
):
    """
    Returns active conversations for the current user (as buyer or seller).
    Sorted by most recent message. Includes unread count + role annotation.
    """
    user_id = current_user["id"]

    def query_func(table):
        return (
            table
            .select("*")
            .or_(f"buyer_id.eq.{user_id},seller_id.eq.{user_id}")
            .eq("status", "active")
            .order("last_message_at", desc=True)
            .range(skip, skip + limit - 1)
        )

    result = db.query("conversations", query_func)
    conversations = result.data if result.data else []

    # Batch fetch listing details (manual join to avoid PGRST200 if FK is missing)
    if conversations:
        listing_ids = [c["listing_id"] for c in conversations]
        listings_map = batch_listings(listing_ids, columns="id, title, price, currency, status")

        for conv in conversations:
            conv["listing"] = listings_map.get(conv["listing_id"])
            is_buyer = conv["buyer_id"] == user_id
            conv["my_role"] = "buyer" if is_buyer else "seller"
            conv["unread_count"] = conv["buyer_unread"] if is_buyer else conv["seller_unread"]

    logger.debug(f"Inbox fetched: user={user_id}, count={len(conversations)}")
    return {
        "conversations": conversations,
        "total": len(conversations),
        "page": (skip // limit) + 1,
        "limit": limit,
    }


@router.get(
    "/{conversation_id}/messages",
    response_model=List[MessageOut],
    summary="Fetch message history (cursor-paginated, oldest-first)",
)
def get_messages(
    conversation_id: str,
    before: Optional[str] = Query(None, description="ISO timestamp — load messages older than this (infinite scroll)"),
    limit: int = Query(30, ge=1, le=100),
    current_user: dict = Depends(get_current_customer),
):
    """
    Returns messages in chronological order.
    Use `before=<ISO timestamp>` for infinite-scroll (load older messages).
    """
    user_id = current_user["id"]
    conv = _get_conv_or_404(conversation_id)
    _assert_participant(conv, user_id)

    def query_func(table):
        q = (
            table
            .select("*")
            .eq("conversation_id", conversation_id)
            .eq("is_deleted", False)
            .order("created_at", desc=True)
            .limit(limit)
        )
        if before:
            q = q.lt("created_at", before)
        return q

    result = db.query("messages", query_func)
    messages = result.data if result.data else []

    # Reverse so client receives oldest-first (natural chat order)
    return list(reversed(messages))


@router.post(
    "/{conversation_id}/messages",
    response_model=MessageOut,
    status_code=201,
    summary="Send a message (REST fallback — prefer client-side Supabase insert)",
)
def send_message(
    conversation_id: str,
    payload: MessageCreate,
    current_user: dict = Depends(get_current_customer),
):
    """
    REST fallback for sending messages. Validates server-side before inserting.

    NOTE: For best performance, use the Supabase SDK client-side insert directly
    (RLS enforces the same security). This endpoint is useful for server-side
    validation flows or backends that don't have SDK access.
    """
    user_id = current_user["id"]
    conv = _get_conv_or_404(conversation_id)
    _assert_participant(conv, user_id)

    if conv["status"] != "active":
        raise HTTPException(status_code=400, detail="Conversation is not active")
    if not payload.content and not payload.media_url:
        raise HTTPException(status_code=400, detail="Message must have content or a media_url")

    message = db.insert("messages", {
        "conversation_id": conversation_id,
        "sender_id": user_id,
        "content": payload.content,
        "message_type": payload.message_type,
        "media_url": payload.media_url,
        "offer_amount": payload.offer_amount,
    })
    if not message:
        raise HTTPException(status_code=500, detail="Failed to send message")

    # ──────────────────────────────────────────────────────────────────
    # REALTIME BROADCAST — CRITICAL FIX
    # Manually push the message to the conversation channel.
    # This ensures it shows up instantly for the receiver.
    # ──────────────────────────────────────────────────────────────────
    try:
        # Note: Frontend listens on channel f"conversation:{conversation_id}"
        # We broadcast the specific message payload directly.
        db.broadcast(
            channel=f"conversation:{conversation_id}", 
            event="new_message", 
            payload=message
        )
    except Exception as e:
        logger.warning(f"Realtime broadcast failed: {e} (DB insert still succeeded)")

    logger.info(f"Message sent via REST: conv={conversation_id}, sender={user_id}")
    return message


@router.post(
    "/{conversation_id}/read",
    summary="Mark a conversation as fully read for the current user",
)
def mark_as_read(
    conversation_id: str,
    current_user: dict = Depends(get_current_customer),
):
    """
    Resets the unread counter for the requesting user.
    Call this every time the user opens a conversation.
    """
    user_id = current_user["id"]
    conv = _get_conv_or_404(conversation_id)
    _assert_participant(conv, user_id)

    try:
        db.get_client().rpc(
            "mark_conversation_read",
            {"conv_id": conversation_id, "reader_id": user_id},
        ).execute()
    except Exception as e:
        logger.error(f"mark_conversation_read RPC failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to mark as read")

    return {"success": True}


@router.post(
    "/{conversation_id}/block",
    summary="Block (archive) a conversation",
)
def block_conversation(
    conversation_id: str,
    current_user: dict = Depends(get_current_customer),
):
    """Either participant can block/archive the conversation."""
    user_id = current_user["id"]
    conv = _get_conv_or_404(conversation_id)
    _assert_participant(conv, user_id)

    db.update("conversations", conversation_id, {"status": "blocked"})
    logger.info(f"Conversation blocked: conv={conversation_id}, by={user_id}")
    return {"success": True}


@router.post(
    "/{conversation_id}/report",
    status_code=201,
    summary="Report a conversation for abuse or spam",
)
def report_conversation(
    conversation_id: str,
    reason: str = Query(..., min_length=5, max_length=500),
    current_user: dict = Depends(get_current_customer),
):
    """
    Flags a conversation for admin review.
    The conversation remains active until an admin blocks it.
    """
    user_id = current_user["id"]
    conv = _get_conv_or_404(conversation_id)
    _assert_participant(conv, user_id)

    db.insert("conversation_reports", {
        "conversation_id": conversation_id,
        "reported_by": user_id,
        "reason": reason,
    })
    logger.warning(f"Conversation reported: conv={conversation_id}, by={user_id}, reason={reason}")
    return {"success": True, "message": "Report submitted. Our team will review it."}


# ─────────────────────────────────────────────────────────────────────────────
# ADMIN ENDPOINTS
# ─────────────────────────────────────────────────────────────────────────────

@admin_router.get(
    "/reports",
    summary="Admin: List all reported conversations",
)
def list_reports(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
):
    """Returns all conversation reports, newest first."""
    def query_func(table):
        return (
            table
            .select("*")
            .order("created_at", desc=True)
            .range(skip, skip + limit - 1)
        )

    result = db.query("conversation_reports", query_func)
    reports = result.data if result.data else []

    if reports:
        conv_ids = [r["conversation_id"] for r in reports]
        convs_map = batch_conversations(conv_ids, columns="id, listing_id, buyer_id, seller_id, status")
        for r in reports:
            r["conversation"] = convs_map.get(r["conversation_id"])

    return {"reports": reports, "total": len(reports)}


@admin_router.post(
    "/{conversation_id}/block",
    summary="Admin: Force-block a conversation (fraud, abuse, etc.)",
)
def admin_block_conversation(conversation_id: str):
    """Admin override to block any conversation regardless of participant action."""
    conv = _get_conv_or_404(conversation_id)
    db.update("conversations", conversation_id, {"status": "blocked"})
    logger.warning(f"Admin blocked conversation: conv={conversation_id}")
    return {"success": True}


@admin_router.get(
    "/",
    summary="Admin: List all conversations with optional status filter",
)
def admin_list_conversations(
    status: Optional[str] = Query(None, description="Filter by status: active | blocked | archived"),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
):
    """Admin overview of all conversations across the platform."""
    def query_func(table):
        q = table.select("*").order("created_at", desc=True).range(skip, skip + limit - 1)
        if status:
            q = q.eq("status", status)
        return q

    result = db.query("conversations", query_func)
    conversations = result.data if result.data else []
    return {"conversations": conversations, "total": len(conversations)}

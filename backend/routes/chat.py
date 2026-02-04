from fastapi import APIRouter, HTTPException, status, Depends
from models import schemas
from db.supabase_client import db
from utils.auth import get_current_customer
from typing import List

router = APIRouter(
    prefix="/api/chat",
    tags=["chat"]
)

@router.post("/conversations", response_model=schemas.ConversationOut)
async def start_conversation(
    payload: schemas.ConversationCreate,
    current_user: dict = Depends(get_current_customer)
):
    # Check if conversation already exists
    # Assuming user1 is always the initiator or we check both combinations
    # For MVP we just insert. A real app needs unique constraint check.
    
    data = {
        "user1_id": current_user["id"],
        "user2_id": payload.target_user_id,
        "listing_id": payload.listing_id
    }
    
    conv = db.insert("conversations", data)
    if not conv:
        raise HTTPException(status_code=500, detail="Failed to start conversation")
        
    return conv

@router.get("/conversations", response_model=List[schemas.ConversationOut])
async def list_conversations(current_user: dict = Depends(get_current_customer)):
    # Need to fetch conversations where user is user1 OR user2
    # Supabase simple client might need raw query or two select calls
    # For this simplified implementation, we just mock the fetch or use a custom query if `db` supports it.
    
    # Placeholder implementation using 'select' which might only support simple AND filters
    # Real implementation needs OR logic: (user1_id=me OR user2_id=me)
    
    # We will try to fetch both and merge
    c1 = db.select("conversations", filters={"user1_id": current_user["id"]})
    c2 = db.select("conversations", filters={"user2_id": current_user["id"]})
    
    return c1 + c2

@router.post("/messages", response_model=schemas.MessageOut)
async def send_message(
    payload: schemas.MessageCreate,
    current_user: dict = Depends(get_current_customer)
):
    # Verify participating in conversation
    conv = db.select_one("conversations", payload.conversation_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
        
    if current_user["id"] not in [conv["user1_id"], conv["user2_id"]]:
        raise HTTPException(status_code=403, detail="Not a participant")
        
    data = {
        "conversation_id": payload.conversation_id,
        "sender_id": current_user["id"],
        "content": payload.content
    }
    
    msg = db.insert("messages", data)
    if not msg:
        raise HTTPException(status_code=500, detail="Failed to send message")
        
    return msg

@router.get("/conversations/{conversation_id}/messages", response_model=List[schemas.MessageOut])
async def get_messages(
    conversation_id: str,
    current_user: dict = Depends(get_current_customer)
):
    # Retrieve messages
    return db.select("messages", filters={"conversation_id": conversation_id})

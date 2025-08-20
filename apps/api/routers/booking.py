from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, HTTPException
from packages.agents.intent_detection import detect_booking_intent
from packages.agents.booking_agent import booking_agent
from packages.agents.state import booking_state_manager
from packages.rag.chains.qa_chains import generate_answer, rewrite_question
from packages.shared.message_store import message_store

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("")
def chat(payload: Dict[str, Any]) -> Dict[str, Any]:
    query = str(payload.get("query", "")).strip()
    # Ensure we always have a stable chat_id for this request
    chat_id = payload.get("chat_id") or message_store.new_chat_id()
    
    if not query:
        raise HTTPException(status_code=400, detail="Query is required")
    
    # Get messages from backend store
    messages = message_store.get_recent(chat_id) if chat_id else []
    
    # Check if we're already in a booking conversation
    booking_state = booking_state_manager.get_state(chat_id)
    
    if booking_state:
        # We're in a booking conversation, use the booking agent
        response = booking_agent.process_booking_message(chat_id, query)
    else:
        # Detect booking intent for new conversations
        intent_result = detect_booking_intent(query)
        
        # If booking intent detected with high confidence, start booking flow
        if intent_result.get("is_booking_intent", False) and intent_result.get("confidence", 0) > 0.7:
            response = booking_agent.process_booking_message(chat_id, query)
        else:
            # Standard RAG QA flow
            # Rewrite query if history exists
            if messages:
                rewritten_query = rewrite_question(messages, query)
            else:
                rewritten_query = query
            
            # Generate answer
            response = generate_answer(rewritten_query, top_k=int(payload.get("top_k", 6)))
            response["intent"] = "qa"
    
    # Append messages to store
    message_store.append(chat_id, "user", query)
    message_store.append(chat_id, "assistant", response["answer"])
    
    response["chat_id"] = chat_id
    return response

 
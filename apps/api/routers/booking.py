from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter

from packages.rag.chains.qa_chains import generate_answer, rewrite_question
from packages.shared.message_store import store as message_store


router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("")
def chat(payload: Dict[str, Any]) -> Dict[str, Any]:
	query = str(payload.get("query", "")).strip()
	if not query:
		return {"answer": "Query required.", "citations": [], "confidence": 0.0}

	# Resolve chat_id or create a new one
	chat_id = str(payload.get("chat_id") or "").strip()
	if not chat_id:
		chat_id = message_store.new_chat_id()

	# Append incoming user message and get recent history from store
	message_store.append(chat_id, "user", query)
	recent = message_store.get_recent(chat_id)

	# Rewrite follow-up into standalone question
	query_rewritten = rewrite_question(recent, query)
	result = generate_answer(query_rewritten, top_k=int(payload.get("top_k", 6)))

	# Append assistant reply
	message_store.append(chat_id, "assistant", result.get("answer") or "")

	# Return result with chat_id so client can persist it
	result_with_id = dict(result)
	result_with_id["chat_id"] = chat_id
	return result_with_id


from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter

from packages.rag.chains.qa_chains import generate_answer


router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("")
def chat(payload: Dict[str, Any]) -> Dict[str, Any]:
	query = str(payload.get("query", "")).strip()
	if not query:
		return {"answer": "Query required.", "citations": [], "confidence": 0.0}
	return generate_answer(query, top_k=int(payload.get("top_k", 6)))


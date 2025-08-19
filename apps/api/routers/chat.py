from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter, Query

from packages.rag.retrieval.retriever import semantic_search


router = APIRouter(prefix="/search", tags=["search"])


@router.get("")
def search(q: str = Query(..., alias="query"), top_k: int = 5) -> Dict[str, Any]:
	results = semantic_search(q, top_k=top_k)
	formatted: List[Dict[str, Any]] = []
	for r in results:
		payload = r.get("payload", {})
		formatted.append(
			{
				"score": r.get("score"),
				"metadata": payload.get("metadata", {}),
				"content": payload.get("content", ""),
			}
		)
	return {"query": q, "top_k": top_k, "results": formatted}



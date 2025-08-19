from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from qdrant_client.http import models as qmodels

from packages.rag.ingestion.embeddings import embed_texts
from packages.rag.retrieval.vector_store import (
	DEFAULT_COLLECTION,
	ensure_collection,
	get_qdrant_client,
	search as qdrant_search,
)


def ensure_ready(vector_size: int) -> None:
	client = get_qdrant_client()
	ensure_collection(client, os.getenv("QDRANT_COLLECTION", DEFAULT_COLLECTION), vector_size)


def semantic_search(query: str, *, top_k: int = 8, filter_: Optional[qmodels.Filter] = None) -> List[Dict[str, Any]]:
	client = get_qdrant_client()
	query_vec = embed_texts([query])[0]
	collection = os.getenv("QDRANT_COLLECTION", DEFAULT_COLLECTION)
	results = qdrant_search(
		client=client,
		collection_name=collection,
		query_vector=query_vec,
		top_k=top_k,
		filter_=filter_,
	)
	out: List[Dict[str, Any]] = []
	for r in results:
		payload = r.payload or {}
		out.append(
			{
				"score": r.score,
				"payload": payload,
			}
		)
	return out


__all__ = ["ensure_ready", "semantic_search"]



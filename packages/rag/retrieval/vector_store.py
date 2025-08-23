from __future__ import annotations

import os
from typing import Any, Dict, List, Optional, Sequence, Tuple

from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels


DEFAULT_COLLECTION = os.getenv("QDRANT_COLLECTION", "smartdocs_chunks")


def get_qdrant_client() -> QdrantClient:
	url = os.getenv("QDRANT_URL")
	api_key = os.getenv("QDRANT_API_KEY")
	if url:
		return QdrantClient(url=url, api_key=api_key)
	# Fall back to local Qdrant
	return QdrantClient(host=os.getenv("QDRANT_HOST", "localhost"), port=int(os.getenv("QDRANT_PORT", "6333")))


def ensure_collection(client: QdrantClient, collection_name: str, vector_size: int) -> None:
	try:
		client.get_collection(collection_name)
		return
	except Exception:
		pass
	client.recreate_collection(
		collection_name=collection_name,
		vectors_config=qmodels.VectorParams(size=vector_size, distance=qmodels.Distance.COSINE),
	)


def upsert_chunks(
	*,
	client: QdrantClient,
	collection_name: str,
	vectors: List[List[float]],
	payloads: List[Dict[str, Any]],
	ids: Optional[Sequence[str]] = None,
) -> int:
	points = []
	for i, vec in enumerate(vectors):
		payload = payloads[i]
		point_id = (ids[i] if ids is not None else payload.get("metadata", {}).get("chunk_id")) or None
		points.append(
			qmodels.PointStruct(
				id=point_id,
				vector=vec,
				payload=payload,
			)
		)
	resp = client.upsert(collection_name=collection_name, points=points)
	return len(points)


def search(
	*,
	client: QdrantClient,
	collection_name: str,
	query_vector: List[float],
	top_k: int = 8,
	filter_: Optional[qmodels.Filter] = None,
) -> List[qmodels.ScoredPoint]:
	return client.search(
		collection_name=collection_name,
		query_vector=query_vector,
		limit=top_k,
		query_filter=filter_,
	)


def clear_collection(client: QdrantClient, collection_name: str) -> None:
	"""Clear all data from a collection."""
	try:
		client.delete_collection(collection_name)
		client.recreate_collection(
			collection_name=collection_name,
			vectors_config=qmodels.VectorParams(size=768, distance=qmodels.Distance.COSINE),
		)
	except Exception as e:
		print(f"Error clearing collection: {e}")


__all__ = [
	"get_qdrant_client",
	"ensure_collection",
	"upsert_chunks",
	"search",
	"clear_collection",
]



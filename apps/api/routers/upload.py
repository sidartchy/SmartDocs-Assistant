from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict

from fastapi import APIRouter, File, HTTPException, UploadFile

from packages.rag.ingestion.parsers import parse_path
from packages.rag.ingestion.chunkers import chunk_pages
from packages.rag.ingestion.embeddings import embed_texts
from packages.rag.retrieval.vector_store import (
	DEFAULT_COLLECTION,
	ensure_collection,
	get_qdrant_client,
	upsert_chunks,
)


router = APIRouter(prefix="/upload", tags=["upload"])


@router.post("")
def upload_and_ingest(file: UploadFile = File(...)) -> Dict[str, Any]:
	if not file.filename:
		raise HTTPException(status_code=400, detail="Missing filename")

	upload_dir = Path("data/uploads")
	upload_dir.mkdir(parents=True, exist_ok=True)
	file_path = upload_dir / file.filename

	# Save uploaded file
	with open(file_path, "wb") as f:
		f.write(file.file.read())

	# Ingest: Parse -> Chunk -> Embed -> Upsert
	pages = parse_path(str(file_path))
	chunks = chunk_pages(pages)
	texts = [c["content"] for c in chunks]
	if not texts:
		return {"ingested": 0, "collection": DEFAULT_COLLECTION, "sample": None}

	vectors = embed_texts(texts)
	vector_size = len(vectors[0])

	client = get_qdrant_client()
	collection = os.getenv("QDRANT_COLLECTION", DEFAULT_COLLECTION)
	ensure_collection(client, collection, vector_size)

	ids = [c["metadata"]["chunk_id"] for c in chunks]
	count = upsert_chunks(client=client, collection_name=collection, vectors=vectors, payloads=chunks, ids=ids)

	return {"ingested": count, "collection": collection, "sample": chunks[0]["metadata"]}



from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import List

from dotenv import load_dotenv

# Ensure project root is on sys.path for `packages.*` imports
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
	sys.path.insert(0, str(PROJECT_ROOT))

from packages.rag.ingestion.chunkers import chunk_pages
from packages.rag.ingestion.embeddings import embed_texts
from packages.rag.ingestion.parsers import parse_path
from packages.rag.retrieval.vector_store import (
	DEFAULT_COLLECTION,
	ensure_collection,
	get_qdrant_client,
	upsert_chunks,
)


def main() -> None:
	# Load environment from .env if present
	load_dotenv()
	parser = argparse.ArgumentParser(description="Ingest documents into Qdrant")
	parser.add_argument("--path", required=True, help="Path to a file or directory to ingest")
	parser.add_argument("--collection", default=DEFAULT_COLLECTION, help="Qdrant collection name")
	parser.add_argument("--chunk_size", type=int, default=1000)
	parser.add_argument("--chunk_overlap", type=int, default=150)
	args = parser.parse_args()

	pages = parse_path(args.path)
	chunks = chunk_pages(pages, chunk_size=args.chunk_size, chunk_overlap=args.chunk_overlap)
	texts = [c["content"] for c in chunks]
	if not texts:
		print(json.dumps({"ingested": 0, "message": "No content found"}))
		return

	vectors = embed_texts(texts)
	vector_size = len(vectors[0])

	client = get_qdrant_client()
	ensure_collection(client, args.collection, vector_size)

	# Prepare payloads: we store {'content': str, 'metadata': {...}}
	payloads = chunks
	ids = [c["metadata"]["chunk_id"] for c in chunks]
	count = upsert_chunks(client=client, collection_name=args.collection, vectors=vectors, payloads=payloads, ids=ids)

	print(
		json.dumps(
			{
				"ingested": count,
				"collection": args.collection,
				"sample": payloads[0]["metadata"],
			}
		)
	)


if __name__ == "__main__":
	main()



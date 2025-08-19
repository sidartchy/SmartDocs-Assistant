from __future__ import annotations

import hashlib
import uuid
from typing import Any, Dict, List, Optional

from langchain.text_splitter import RecursiveCharacterTextSplitter


def _sha256_of_text(text: str) -> str:
	return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _build_chunk_id(doc_id: str, page: Optional[int], chunk_index: int) -> str:
	base = f"{doc_id}|{page if page is not None else 'NA'}|{chunk_index}"
	# Use stable UUID5 to satisfy Qdrant's point ID requirement (UUID or unsigned int)
	return str(uuid.uuid5(uuid.NAMESPACE_URL, base))


def chunk_pages(
	pages: List[Dict[str, Any]],
	*,
	chunk_size: int = 1000,
	chunk_overlap: int = 150,
) -> List[Dict[str, Any]]:
	"""Split page records into overlapping chunks while preserving metadata.

	Each output item has shape:
	{"content": str, "metadata": {"doc_id": str, "chunk_id": str, "page": int | None, "filename": str, "source_path": str, "headings": list[str], "content_hash": str}}
	"""
	text_splitter = RecursiveCharacterTextSplitter(
		chunk_size=chunk_size,
		chunk_overlap=chunk_overlap,
		separators=["\n\n", "\n", " ", ""],
	)

	chunks: List[Dict[str, Any]] = []
	for page_record in pages:
		content = str(page_record.get("content", ""))
		metadata = dict(page_record.get("metadata", {}))
		if not content:
			continue

		splits = text_splitter.split_text(content)
		for idx, split in enumerate(splits):
			doc_id = str(metadata.get("doc_id", ""))
			page_num = metadata.get("page")
			chunk_id = _build_chunk_id(doc_id, page_num, idx)
			content_hash = _sha256_of_text(split)

			chunk_metadata: Dict[str, Any] = {
				"doc_id": doc_id,
				"chunk_id": chunk_id,
				"page": page_num,
				"filename": metadata.get("filename"),
				"source_path": metadata.get("source_path"),
				"headings": metadata.get("headings", []) or [],
				"content_hash": content_hash,
			}

			chunks.append({"content": split, "metadata": chunk_metadata})

	return chunks


__all__ = ["chunk_pages"]



from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from pypdf import PdfReader


def _sha256_of_text(text: str) -> str:
	"""Return hex sha256 of given text."""
	return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _stable_doc_id_from_path(source_path: str) -> str:
	"""Create a stable document id from an absolute source path.

	The path is lowercased and normalized to ensure stability across platforms.
	"""
	abspath = os.path.abspath(source_path)
	normalized = abspath.replace("\\", "/").lower()
	return _sha256_of_text(normalized)


def _build_page_record(
	*,
	content: str,
	source_path: str,
	filename: str,
	page_number: Optional[int],
) -> Dict[str, Any]:
	metadata: Dict[str, Any] = {
		"doc_id": _stable_doc_id_from_path(source_path),
		"filename": filename,
		"source_path": os.path.abspath(source_path),
		"page": page_number,
		"headings": [],
	}
	return {"content": content, "metadata": metadata}


def _parse_pdf(file_path: str) -> List[Dict[str, Any]]:
	pages: List[Dict[str, Any]] = []
	reader = PdfReader(file_path)
	for index, page in enumerate(reader.pages):
		text = page.extract_text() or ""
		clean_text = text.strip()
		if not clean_text:
			continue
		pages.append(
			_build_page_record(
				content=clean_text,
				source_path=file_path,
				filename=Path(file_path).name,
				page_number=index + 1,
			)
		)
	return pages


def _parse_txt(file_path: str) -> List[Dict[str, Any]]:
	with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
		text = f.read()
	clean_text = text.strip()
	if not clean_text:
		return []
	return [
		_build_page_record(
			content=clean_text,
			source_path=file_path,
			filename=Path(file_path).name,
			page_number=None,
		)
	]


def parse_path(input_path: str) -> List[Dict[str, Any]]:
	"""Parse a file or directory into page-level records.

	Currently supports .pdf and .txt. Each record has the shape:
	{"content": str, "metadata": {"doc_id": str, "filename": str, "source_path": str, "page": int | None, "headings": list[str]}}
	"""
	path = Path(input_path)
	if not path.exists():
		raise FileNotFoundError(f"Input path not found: {input_path}")

	all_pages: List[Dict[str, Any]] = []

	def handle_file(file_path: Path) -> None:
		lower = file_path.suffix.lower()
		if lower == ".pdf":
			all_pages.extend(_parse_pdf(str(file_path)))
		elif lower == ".txt":
			all_pages.extend(_parse_txt(str(file_path)))
		else:
			return

	if path.is_file():
		handle_file(path)
	else:
		for child in path.rglob("*"):
			if child.is_file():
				handle_file(child)

	return all_pages


__all__ = ["parse_path"]



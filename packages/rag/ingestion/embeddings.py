from __future__ import annotations

import os
from typing import List


def embed_texts(texts: List[str]) -> List[List[float]]:
	"""Embed an array of texts and return vectors.

	Provider is selected by env var EMBEDDINGS_PROVIDER: "google" (default) or "openai".
	- Google: requires GOOGLE_API_KEY, uses model "text-embedding-004" via langchain-google-genai
	- OpenAI: requires OPENAI_API_KEY, uses model from OPENAI_EMBEDDING_MODEL (default: text-embedding-3-small)
	"""
	provider = os.getenv("EMBEDDINGS_PROVIDER", "google").lower()
	if provider == "google":
		from langchain_google_genai import GoogleGenerativeAIEmbeddings

		model = os.getenv("GOOGLE_EMBEDDING_MODEL", "text-embedding-004")
		emb = GoogleGenerativeAIEmbeddings(model=model)
		return emb.embed_documents(texts)
	elif provider == "openai":
		from openai import OpenAI

		model = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
		client = OpenAI()
		result = client.embeddings.create(model=model, input=texts)
		return [d.embedding for d in result.data]
	else:
		raise ValueError(f"Unsupported EMBEDDINGS_PROVIDER: {provider}")


__all__ = ["embed_texts"]



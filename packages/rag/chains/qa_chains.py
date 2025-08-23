from __future__ import annotations

import os
from typing import Any, Dict, List

from packages.rag.retrieval.retriever import semantic_search
from langchain.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI


SYSTEM_PROMPT = (
	"You are a helpful and friendly assistant. You can handle both basic conversations and document-based questions.\n\n"
	"For basic conversational queries (greetings, gratitude, farewells, etc.), respond naturally and warmly without needing document sources.\n\n"
	"For questions about documents or specific information, answer strictly using the provided sources. "
	"If the answer is not supported by the sources, reply: 'I couldn't find any relevant information in the documents.' "
	"Include citations inline like [filename p=page] when using document sources. Be concise and helpful."
)


def _format_sources_block(contexts: List[Dict[str, Any]]) -> str:
	lines: List[str] = []
	for i, ctx in enumerate(contexts, start=1):
		m = ctx["payload"]["metadata"]
		filename = m.get("filename", "document")
		page = m.get("page")
		snippet = (ctx["payload"].get("content", "") or "").strip().replace("\n", " ")
		if len(snippet) > 600:
			snippet = snippet[:600] + "…"
		lines.append(f"[{i}] {filename}{f' p={page}' if page else ''}: {snippet}")
	return "\n".join(lines)


def _call_llm(query: str, contexts: List[Dict[str, Any]]) -> str:
	provider = os.getenv("LLM_PROVIDER", "google").lower()
	if provider == "google":
		sources_block = _format_sources_block(contexts)

		prompt = ChatPromptTemplate.from_messages([
			("system", SYSTEM_PROMPT),
			("human", "Question:\n{query}\n\nSources:\n{sources}\n\nAnswer:"),
		])

		model_name = os.getenv("GOOGLE_LLM_MODEL", "gemini-1.5-flash")
		model = ChatGoogleGenerativeAI(model=model_name, temperature=0.2)
		messages = prompt.format_messages(query=query, sources=sources_block)
		resp = model.invoke(messages)
		return getattr(resp, "content", "") or ""
	elif provider == "openai":
		from openai import OpenAI

		client = OpenAI()
		model_name = os.getenv("OPENAI_LLM_MODEL", "gpt-4o-mini")
		sources_block = _format_sources_block(contexts)
		user_text = f"Question:\n{query}\n\nSources:\n{sources_block}\n\nAnswer:"
		resp = client.chat.completions.create(
			model=model_name,
			messages=[
				{"role": "system", "content": SYSTEM_PROMPT},
				{"role": "user", "content": user_text},
			],
			temperature=0.2,
		)
		return resp.choices[0].message.content or ""
	else:
		raise ValueError(f"Unsupported LLM_PROVIDER: {provider}")


def _format_history_for_rewrite(messages: List[Dict[str, str]], window: int = 6) -> str:
	"""Format last N messages for query rewriting."""
	recent = messages[-window:]
	lines: List[str] = []
	for m in recent:
		role = m.get("role", "user")
		prefix = "User" if role == "user" else "Assistant"
		content = (m.get("content") or "").strip().replace("\n", " ")
		if content:
			lines.append(f"{prefix}: {content}")
	return "\n".join(lines)


def rewrite_question(messages: List[Dict[str, str]], query: str) -> str:
	"""Rewrite a follow-up into a standalone question using recent chat history."""
	provider = os.getenv("LLM_PROVIDER", "google").lower()
	history = _format_history_for_rewrite(messages)
	if not history:
		return query
	if provider == "google":
		prompt = ChatPromptTemplate.from_messages([
			("system", "Rewrite the user's follow-up into a standalone question using the conversation context. Do not answer, only rewrite."),
			("human", "Conversation:\n{history}\n\nFollow-up:\n{query}\n\nStandalone question:"),
		])
		model_name = os.getenv("GOOGLE_LLM_MODEL", "gemini-1.5-flash")
		model = ChatGoogleGenerativeAI(model=model_name, temperature=0.0)
		messages_formatted = prompt.format_messages(history=history, query=query)
		resp = model.invoke(messages_formatted)
		return (getattr(resp, "content", "") or query).strip()
	elif provider == "openai":
		from openai import OpenAI

		client = OpenAI()
		model_name = os.getenv("OPENAI_LLM_MODEL", "gpt-4o-mini")
		system = "Rewrite the user's follow-up into a standalone question using the conversation context. Do not answer, only rewrite."
		user = f"Conversation:\n{history}\n\nFollow-up:\n{query}\n\nStandalone question:"
		resp = client.chat.completions.create(
			model=model_name,
			messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
			temperature=0.0,
		)
		return (resp.choices[0].message.content or query).strip()
	else:
		return query


def _build_citations(contexts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
	citations: List[Dict[str, Any]] = []
	for ctx in contexts[:6]:
		m = ctx["payload"]["metadata"]
		citations.append(
			{
				"doc_id": m.get("doc_id"),
				"page": m.get("page"),
				"snippet": (ctx["payload"].get("content", "") or "")[:200],
			}
		)
	return citations





def generate_answer(query: str, *, top_k: int = 6) -> Dict[str, Any]:
	results = semantic_search(query, top_k=top_k)
	
	# Always call LLM - it will handle basic conversations naturally
	answer_text = _call_llm(query, results).strip()
	if not answer_text:
		answer_text = "I couldn't find any relevant information in the documents."

	# If no documents found, it's likely a basic conversation or question not in docs
	if not results:
		return {
			"answer": answer_text,
			"citations": [],
			"confidence": 1.0,  # High confidence for basic conversations
		}

	# For document queries, include citations
	citations = _build_citations(results)
	scores = [r.get("score", 0.0) for r in results]
	mean_score = sum(scores) / max(len(scores), 1)
	confidence = max(0.0, min(1.0, float(mean_score)))
	
	return {"answer": answer_text, "citations": citations, "confidence": confidence}


__all__ = ["generate_answer", "rewrite_question"]



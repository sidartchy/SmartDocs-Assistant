from __future__ import annotations

import io
import os
from typing import Any, Dict, List

import streamlit as st
import requests


st.set_page_config(page_title="SmartDocs Assistant", layout="wide")


def get_api_base_url() -> str:
	default_url = os.getenv("API_URL", "http://localhost:8000")
	return st.sidebar.text_input("API Base URL", value=default_url, help="Your FastAPI server base URL")


def section_uploader(api_base: str) -> None:
	st.header("Upload Documents")
	uploaded_file = st.file_uploader("Choose a .pdf or .txt file", type=["pdf", "txt"])
	if st.button("Upload", use_container_width=True, disabled=uploaded_file is None):
		if not uploaded_file:
			st.warning("Please choose a file to upload.")
			return
		try:
			files = {
				"file": (
					uploaded_file.name,
					uploaded_file.getvalue(),
					uploaded_file.type or "application/octet-stream",
				),
			}
			resp = requests.post(f"{api_base}/upload", files=files, timeout=120)
			resp.raise_for_status()
			data = resp.json()
			st.success(f"Ingested {data.get('ingested', 0)} chunks into collection '{data.get('collection')}'.")
			if sample := data.get("sample"):
				with st.expander("Sample Metadata"):
					st.json(sample)
		except Exception as exc:
			st.error(f"Upload failed: {exc}")


def render_citations(citations: List[Dict[str, Any]]) -> None:
	if not citations:
		return
	st.subheader("Citations")
	for idx, c in enumerate(citations, start=1):
		page = c.get("page")
		snippet = (c.get("snippet") or "").replace("\n", " ")
		st.markdown(f"- [{idx}] page={page or '-'} — {snippet[:200]}{'…' if len(snippet) > 200 else ''}")


def section_chat(api_base: str) -> None:
	st.header("Ask Questions")
	col1, col2 = st.columns([0.75, 0.25])
	with col1:
		query = st.text_input("Your question", placeholder="e.g., What is the leave policy?", label_visibility="collapsed")
	with col2:
		top_k = st.slider("Top K", min_value=2, max_value=10, value=6)

	# Maintain chat_id in session (backend stores messages)
	if "chat_id" not in st.session_state:
		st.session_state["chat_id"] = ""

	ask = st.button("Ask", type="primary", use_container_width=True, disabled=not query)
	if ask and query:
		try:
			resp = requests.post(
				f"{api_base}/chat",
				json={"query": query, "top_k": top_k, "chat_id": st.session_state["chat_id"]},
				timeout=120,
			)
			resp.raise_for_status()
			data = resp.json()
			if not st.session_state["chat_id"]:
				st.session_state["chat_id"] = data.get("chat_id", "")

			answer = (data.get("answer") or "").strip()
			confidence = data.get("confidence")
			st.markdown("### Answer")
			if confidence is not None:
				st.caption(f"Confidence: {confidence:.2f}")
			st.write(answer or "No answer.")


			citations = data.get("citations") or []
			render_citations(citations)
		except Exception as exc:
			st.error(f"Chat failed: {exc}")

	with st.expander("Debug: Search Results"):
		if st.button("Preview Top Results", use_container_width=True, disabled=not query):
			try:
				resp = requests.get(f"{api_base}/search", params={"query": query, "top_k": top_k}, timeout=60)
				resp.raise_for_status()
				results = resp.json().get("results", [])
				for r in results:
					meta = r.get("metadata", {})
					score = r.get("score")
					filename = meta.get("filename")
					page = meta.get("page")
					st.markdown(f"- score={score:.3f} — {filename} p={page}")
					with st.expander("Snippet"):
						st.write((r.get("content") or "").strip()[:500])
			except Exception as exc:
				st.error(f"Search failed: {exc}")


def main() -> None:
	st.title("SmartDocs Assistant")
	api_base = get_api_base_url()
	section_uploader(api_base)
	st.divider()
	section_chat(api_base)


if __name__ == "__main__":
	main()
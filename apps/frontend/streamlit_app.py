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
	st.header("💬 Chat with SmartDocs Assistant")
	
	# Initialize chat history in session state
	if "messages" not in st.session_state:
		st.session_state["messages"] = []
	
	if "chat_id" not in st.session_state:
		st.session_state["chat_id"] = ""
	

	
	# Controls above chat
	with st.container():
		col1, col2 = st.columns([0.8, 0.2])
		with col1:
			st.empty()  # Placeholder for alignment
		with col2:
			top_k = st.slider("Top K", min_value=2, max_value=10, value=6, help="Number of documents to retrieve")
	
	# Display chat history
	chat_container = st.container()
	with chat_container:
		for message in st.session_state["messages"]:
			with st.chat_message(message["role"]):
				st.markdown(message["content"])
				if "confidence" in message and message["confidence"] is not None:
					st.caption(f"Confidence: {message['confidence']:.2f}")
				if "citations" in message and message["citations"]:
					with st.expander("📚 Sources"):
						for idx, citation in enumerate(message["citations"], 1):
							page = citation.get("page")
							snippet = (citation.get("snippet") or "").replace("\n", " ")
							st.markdown(f"**[{idx}]** page={page or '-'} — {snippet[:200]}{'…' if len(snippet) > 200 else ''}")
	
	# Chat input at the bottom
	query = st.chat_input(placeholder="Ask me anything... e.g., What is the leave policy? or just say 'Hey!'")
	
	# Handle new message
	if query:
		# Add user message to chat
		st.session_state["messages"].append({"role": "user", "content": query})
		
		# Display user message
		with st.chat_message("user"):
			st.markdown(query)
		
		# Get assistant response
		with st.chat_message("assistant"):
			with st.spinner("Thinking..."):
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
					citations = data.get("citations") or []
					
					# Display answer
					st.markdown(answer or "No answer.")
					
					# Display confidence
					if confidence is not None:
						st.caption(f"Confidence: {confidence:.2f}")
					
					# Display citations if any
					if citations:
						with st.expander("📚 Sources"):
							for idx, citation in enumerate(citations, 1):
								page = citation.get("page")
								snippet = (citation.get("snippet") or "").replace("\n", " ")
								st.markdown(f"**[{idx}]** page={page or '-'} — {snippet[:200]}{'…' if len(snippet) > 200 else ''}")
					
					# Add assistant message to chat history
					st.session_state["messages"].append({
						"role": "assistant", 
						"content": answer,
						"confidence": confidence,
						"citations": citations
					})
					
				except Exception as exc:
					error_msg = f"Sorry, I encountered an error: {exc}"
					st.error(error_msg)
					st.session_state["messages"].append({
						"role": "assistant", 
						"content": error_msg,
						"confidence": 0.0,
						"citations": []
					})
	
	# Chat Controls Sidebar
	with st.sidebar:
		st.subheader("Chat Controls")
		
		# Document status indicator
		try:
			status_response = requests.get(f"{api_base}/upload/status")
			if status_response.status_code == 200:
				status_data = status_response.json()
				doc_count = status_data.get("document_count", 0)
				if doc_count > 0:
					st.info(f"📚 {doc_count} document(s) loaded")
				else:
					st.info("📚 No documents loaded")
			else:
				st.info("📚 Document status unknown")
		except Exception:
			st.info("📚 Document status unknown")
		
		# Clear current chat button
		if st.button("🗑️ Clear Current Chat", use_container_width=True):
			st.session_state["messages"] = []
			st.session_state["chat_id"] = ""
			st.rerun()
		
		# Clear documents button
		if st.button("📄 Clear Documents", use_container_width=True):
			try:
				response = requests.delete(f"{api_base}/upload/clear")
				if response.status_code == 200:
					data = response.json()
					if data.get("success", False):
						st.success(f"✅ Documents cleared successfully! ({data.get('points_cleared', 0)} documents removed)")
					else:
						st.warning(f"⚠️ Documents cleared but verification failed. {data.get('points_remaining', 0)} documents may still remain.")
				else:
					st.error("Failed to clear documents")
			except Exception as e:
				st.error(f"Error clearing documents: {e}")
			st.rerun()
		
		# Debug section
		with st.expander("🔧 Debug Tools"):
			if st.button("Preview Search Results", use_container_width=True, disabled=not query):
				try:
					resp = requests.get(f"{api_base}/search", params={"query": query, "top_k": top_k}, timeout=60)
					resp.raise_for_status()
					results = resp.json().get("results", [])
					st.write("**Search Results:**")
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
			
			# Check bookings
			if st.button("📅 Check Bookings", use_container_width=True):
				try:
					resp = requests.get(f"{api_base}/chat/bookings", timeout=60)
					resp.raise_for_status()
					data = resp.json()
					st.write(f"**Bookings Found: {data.get('count', 0)}**")
					for booking in data.get("bookings", []):
						with st.expander(f"Booking: {booking.get('name', 'Unknown')}"):
							st.json(booking)
				except Exception as exc:
					st.error(f"Failed to get bookings: {exc}")
			
			# Show current chat_id
			if st.session_state["chat_id"]:
				st.text(f"Chat ID: {st.session_state['chat_id']}")
			
			# Show message count
			st.text(f"Messages: {len(st.session_state['messages'])}")


def main() -> None:
	st.title("SmartDocs Assistant")
	api_base = get_api_base_url()
	section_uploader(api_base)
	st.divider()
	section_chat(api_base)


if __name__ == "__main__":
	main()
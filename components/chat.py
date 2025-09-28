"""Chat component encapsulating chat UI & file upload for Streamlit."""

from __future__ import annotations

from typing import List, Dict, Any
import streamlit as st
from services.mcp_client import MCPClient


class ChatComponent:
	"""Stateful chat interface with full-height layout support.

	This version avoids st.chat_input (which pins to bottom of page) so the
	input can live inside the left column and remain fixed while the history
	scrolls.
	"""

	SESSION_KEY = "chat_history"

	def __init__(self, client: MCPClient):
		self.client = client
		if self.SESSION_KEY not in st.session_state:
			st.session_state[self.SESSION_KEY] = []  # list[dict]

	@property
	def history(self) -> List[Dict[str, str]]:
		return st.session_state[self.SESSION_KEY]

	def append(self, role: str, content: str) -> None:
		self.history.append({"role": role, "content": content})

	def _inject_css(self):
		if st.session_state.get("_chat_css_loaded"):
			return
		st.markdown(
			"""
<style>
.full-height-col {display:flex; flex-direction:column; height:calc(100vh - 120px);} /* adjust offset for header */
.chat-pane {display:flex; flex-direction:column; height:100%;}
.chat-history {flex:1; overflow-y:auto; padding:0.5rem; border:1px solid #ddd; border-radius:4px; background:#fafafa;}
.chat-msg-user {background:#e3f2fd; padding:0.4rem 0.6rem; margin:0 0 0.5rem 0; border-radius:4px;}
.chat-msg-assistant {background:#f1f8e9; padding:0.4rem 0.6rem; margin:0 0 0.5rem 0; border-radius:4px;}
.chat-input-container {margin-top:0.5rem; border-top:1px solid #ddd; padding-top:0.5rem; background:#fff;}
.chat-input-container form {display:flex; gap:0.5rem;}
.chat-input-container form div[data-baseweb="input"] {flex:1;}
</style>
""",
			unsafe_allow_html=True,
		)
		st.session_state["_chat_css_loaded"] = True

	def render(self) -> bytes | None:
		self._inject_css()
		uploaded_bytes: bytes | None = None

		st.markdown("<div class='chat-pane'>", unsafe_allow_html=True)

		with st.expander("Upload Mesh JSON", expanded=True):
			file = st.file_uploader("Select JSON file", type=["json"], accept_multiple_files=False)
			if file is not None:
				uploaded_bytes = file.read()
				st.success("File uploaded. Parsed on right column when valid.")

		# History scroll area
		st.markdown("<div class='chat-history'>", unsafe_allow_html=True)
		for msg in self.history:
			css_class = "chat-msg-user" if msg["role"] == "user" else "chat-msg-assistant"
			st.markdown(f"<div class='{css_class}'><strong>{msg['role'].title()}:</strong> {msg['content']}</div>", unsafe_allow_html=True)
		st.markdown("</div>", unsafe_allow_html=True)

		# Input form stuck to bottom of column
		st.markdown("<div class='chat-input-container'>", unsafe_allow_html=True)
		with st.form(key="chat_form", clear_on_submit=True):
			prompt = st.text_input("Message", placeholder="Ask GPT to analyze structures or compute with Grasshopper...")
			submitted = st.form_submit_button("Send", use_container_width=True)
		st.markdown("</div>", unsafe_allow_html=True)

		if submitted and prompt.strip():
			self.append("user", prompt.strip())
			# Pass conversation history for better context
			response = self.client.send_message(prompt.strip(), conversation_history=self.history[:-1])  # Exclude the just-added user message
			self.append("assistant", response)
			st.rerun()

		st.markdown("</div>", unsafe_allow_html=True)  # close chat-pane
		return uploaded_bytes


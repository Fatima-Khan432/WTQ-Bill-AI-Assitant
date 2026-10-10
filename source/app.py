"""Streamlit UI for the Utility Bill Decoder.

    streamlit run app.py

Contains no business logic: it calls the same pipeline functions as the CLI.
"""

from __future__ import annotations

import hashlib
import json
import tempfile
from pathlib import Path

import streamlit as st

from bill_decoder.config import load_config
from bill_decoder.guard import MAX_QUESTION_CHARS
from bill_decoder.level1 import process_bill
from bill_decoder.level2 import answer_free_text, answer_questions, ensure_context
from bill_decoder.llm import GeminiClient, LLMError

WORK_ROOT = Path(tempfile.gettempdir()) / "wtq_bill_ui"
SUGGESTED = [
    "What is the total amount I need to pay?",
    "How many units did I consume this month?",
    "What is the tax share of my bill?",
    "What is the late payment penalty?",
]

st.set_page_config(page_title="Utility Bill Decoder", page_icon="⚡", layout="wide")
st.title("⚡ Utility Bill Decoder")
st.caption("Upload a K-Electric, LESCO or IESCO electricity bill image to decode it and ask questions.")


@st.cache_resource
def get_client():
    cfg = load_config()
    try:
        return cfg, GeminiClient(cfg)
    except LLMError as exc:
        return cfg, str(exc)


cfg, client = get_client()
if isinstance(client, str):
    st.error(f"Model is not configured: {client}. Set API_KEY in .env (see .env.example).")
    st.stop()

upload = st.file_uploader("Bill image", type=["png", "jpg", "jpeg", "webp"])
if upload is None:
    st.info("Upload a bill image to begin.")
    st.stop()

data = upload.getvalue()
digest = hashlib.sha256(data).hexdigest()[:16]
suffix = Path(upload.name).suffix.lower() or ".jpg"
work_dir = WORK_ROOT / digest
work_dir.mkdir(parents=True, exist_ok=True)
image_path = work_dir / f"upload{suffix}"
image_path.write_bytes(data)

left, right = st.columns([1, 1])
with left:
    st.image(data, caption="Uploaded bill", use_container_width=True)

if st.session_state.get("ctx_digest") != digest:
    with st.spinner("Reading the bill..."):
        try:
            ctx = ensure_context(digest, image_path, WORK_ROOT, client, cfg)
            st.session_state.update(ctx=ctx, ctx_digest=digest)
        except Exception as exc:  # noqa: BLE001 - show a friendly error
            st.error(f"Could not read this bill: {exc}")
            st.stop()
ctx = st.session_state["ctx"]

with right:
    st.subheader("Extracted details")
    st.json(ctx.final, expanded=False)
    if ctx.level1_warnings:
        with st.expander("Extraction warnings"):
            st.write("\n".join(f"- {w}" for w in ctx.level1_warnings))
    with st.expander("Fact sheet (computed by code)"):
        st.json(ctx.factsheet, expanded=False)

st.subheader("Ask about this bill")
choice = st.selectbox("Suggested questions", [""] + SUGGESTED)
typed = st.text_input("...or type your own question", max_chars=MAX_QUESTION_CHARS)
question = typed.strip() or choice
if st.button("Ask", type="primary", disabled=not question):
    with st.spinner("Thinking..."):
        answer, warns = answer_free_text(ctx, question, client, cfg)
    st.markdown(f"**Answer:** {answer}")
    if warns:
        with st.expander("Checks"):
            st.write("\n".join(f"- {w}" for w in warns))

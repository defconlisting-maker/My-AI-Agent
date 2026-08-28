"""
My Agent -- Streamlit version, deployable free forever on Streamlit
Community Cloud (no Docker, no card, no expiry).

Local test:  streamlit run streamlit_app.py
Deploy:      see README.md
"""

import json
import streamlit as st

import providers
import tools
import key_store
import documents

st.set_page_config(page_title="My Agent", page_icon="🤖", layout="centered")

MAX_ITERATIONS = 15

SYSTEM_PROMPT = """You are an autonomous coding agent with real tools: run shell \
commands, read/write/edit files, list directories. Work inside the given \
working directory only.

Rules:
1. Plan briefly before acting on non-trivial tasks.
2. Work incrementally and run/test what you write before moving on.
3. Never call task_complete until you've actually run and verified the result.
4. If a document's contents were provided in the conversation, treat that as \
ground truth context for the task.
5. Be concise in your text -- the tool calls are the actual work.
6. Call task_complete with a summary once genuinely done and verified.
"""

if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "system", "content": SYSTEM_PROMPT}]
if "display_log" not in st.session_state:
    st.session_state.display_log = []  # what actually gets shown in the chat


# --------------------------------------------------------------------------
# Sidebar: API keys + status
# --------------------------------------------------------------------------
with st.sidebar:
    st.header("⚙ Settings")

    with st.form("gemini_form", clear_on_submit=True):
        gk = st.text_input("Gemini API key", type="password")
        if st.form_submit_button("Save Gemini key") and gk.strip():
            key_store.add_key("gemini", gk.strip())
            st.success("Gemini key saved.")

    with st.form("groq_form", clear_on_submit=True):
        grk = st.text_input("Groq API key", type="password")
        if st.form_submit_button("Save Groq key") and grk.strip():
            key_store.add_key("groq", grk.strip())
            st.success("Groq key saved.")

    with st.form("deepseek_form", clear_on_submit=True):
        dk = st.text_input(
            "DeepSeek API key (add a new one whenever the old runs out)",
            type="password",
        )
        if st.form_submit_button("Save DeepSeek key") and dk.strip():
            key_store.add_key("deepseek", dk.strip())
            st.success("DeepSeek key saved.")

    st.divider()
    s = key_store.status()
    st.caption(
        f"Gemini keys: {s['gemini']['total']} · "
        f"Groq keys: {s['groq']['total']} · "
        f"DeepSeek keys: {s['deepseek']['total']} "
        f"({s['deepseek']['exhausted']} exhausted)"
    )

    st.divider()
    st.subheader("📎 Upload a document")
    uploaded = st.file_uploader(
        "PDF, Word, or text file", type=["pdf", "docx", "txt", "md", "csv", "json", "py"]
    )
    if uploaded is not None:
        save_path = f"{tools.WORKDIR}/{uploaded.name}"
        with open(save_path, "wb") as f:
            f.write(uploaded.getbuffer())
        text = documents.extract_text(save_path)
        st.session_state.messages.append({
            "role": "user",
            "content": f"[Uploaded document: {uploaded.name}]\n\n{text}",
        })
        st.success(f"Loaded {uploaded.name} ({len(text)} chars) into context.")


# --------------------------------------------------------------------------
# Main chat area
# --------------------------------------------------------------------------
st.title("🤖 My Agent")
st.caption("Give it a coding task. It plans, writes, runs, and verifies before it stops.")

for entry in st.session_state.display_log:
    with st.chat_message(entry["role"]):
        st.markdown(entry["content"])

task = st.chat_input("Describe the coding task...")

if task:
    st.session_state.display_log.append({"role": "user", "content": task})
    st.session_state.messages.append({"role": "user", "content": task})
    with st.chat_message("user"):
        st.markdown(task)

    notifications = []

    def notify(event):
        notifications.append(event)

    with st.chat_message("assistant"):
        status_box = st.status("Working...", expanded=True)
        final_reply = None

        for step in range(MAX_ITERATIONS):
            try:
                provider_used, msg = providers.call_with_fallback(
                    st.session_state.messages, tools=tools.TOOL_SCHEMAS, notify=notify
                )
            except providers.NoProviderAvailable as e:
                final_reply = (
                    f"No AI provider is currently available: {e}. "
                    f"Add an API key in Settings."
                )
                break

            assistant_entry = {"role": "assistant", "content": msg.content or ""}
            tool_calls = getattr(msg, "tool_calls", None)
            if tool_calls:
                assistant_entry["tool_calls"] = [tc.model_dump() for tc in tool_calls]
            st.session_state.messages.append(assistant_entry)

            if msg.content:
                status_box.write(f"💭 [{provider_used}] {msg.content[:300]}")

            if not tool_calls:
                final_reply = msg.content or ""
                break

            task_done = False
            summary = ""

            for call in tool_calls:
                name = call.function.name
                try:
                    args = json.loads(call.function.arguments or "{}")
                except json.JSONDecodeError:
                    args = {}

                result = tools.execute_tool(name, args)
                arg_preview = str(args)[:120]
                status_box.write(f"🔧 {name}({arg_preview})")

                if name == "task_complete":
                    task_done = True
                    summary = result.get("summary", "")

                st.session_state.messages.append({
                    "role": "tool",
                    "tool_call_id": call.id,
                    "content": json.dumps(result),
                })

            if task_done:
                final_reply = summary
                break
        else:
            final_reply = (
                "Hit the step limit for this turn without finishing. "
                "Send another message to keep going."
            )

        status_box.update(label="Done", state="complete", expanded=False)

        for n in notifications:
            st.warning(n["message"])

        st.markdown(final_reply)
        st.session_state.display_log.append({"role": "assistant", "content": final_reply})

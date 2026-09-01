"""
My Agent -- Streamlit version, deployable free forever on Streamlit
Community Cloud (no Docker, no card, no expiry).

Local test:  streamlit run streamlit_app.py
Deploy:      see README.md
"""

import io
import json
import os
import zipfile

import streamlit as st

import providers
import tools
import key_store
import documents
import projects_store

st.set_page_config(page_title="My Agent", page_icon="🤖", layout="centered")

MAX_ITERATIONS = 15

SYSTEM_PROMPT = """You are a helpful assistant with real tools: live web search, \
running shell commands, and reading/writing/editing files. Work inside the \
given working directory only for any files you create.

Rules:
1. For coding tasks: plan briefly, work incrementally, and run/test what you \
write before moving on. Never call task_complete until you've actually run \
and verified the result.
2. For research or homework-help questions (including requests for past exam \
papers, study material, or tutorials): use web_search to find real, current \
sources, and share the actual links/titles you found rather than inventing \
answers from memory. Never reproduce copyrighted material (exam papers, \
textbook pages, articles) verbatim -- summarize briefly and point to the \
source link instead. Prefer official or well-known educational sites.
3. When helping with homework, favor explaining concepts and pointing to \
practice resources over just handing over a final answer to copy -- the goal \
is the person understanding the material.
4. If a document's contents were provided in the conversation, treat that as \
ground truth context for the task.
5. Be concise in your text -- the tool calls are the actual work.
6. Call task_complete with a summary once genuinely done (for coding tasks) \
or once the question is fully answered (for research questions).
"""

if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "system", "content": SYSTEM_PROMPT}]
if "display_log" not in st.session_state:
    st.session_state.display_log = []  # what actually gets shown in the chat


def switch_project(pid: str):
    state = projects_store.load_state(pid)
    st.session_state.current_project_id = pid
    st.session_state.messages = state["messages"] or [{"role": "system", "content": SYSTEM_PROMPT}]
    st.session_state.display_log = state["display_log"] or []
    tools.WORKDIR = projects_store.get_workspace(pid)
    os.makedirs(tools.WORKDIR, exist_ok=True)


def persist_current_project():
    pid = st.session_state.get("current_project_id")
    if pid:
        projects_store.save_state(pid, st.session_state.messages, st.session_state.display_log)


if "current_project_id" not in st.session_state:
    existing = projects_store.list_projects()
    if existing:
        switch_project(existing[0]["id"])
    else:
        first_id = projects_store.create_project("My First Project")
        switch_project(first_id)


# --------------------------------------------------------------------------
# Sidebar: Projects
# --------------------------------------------------------------------------
with st.sidebar:
    st.header("📁 Projects")

    if st.button("＋ New Project", use_container_width=True):
        new_id = projects_store.create_project()
        switch_project(new_id)
        st.rerun()

    for p in projects_store.list_projects():
        is_current = p["id"] == st.session_state.current_project_id
        pin_icon = "📌" if p.get("pinned") else "📍"
        cols = st.columns([5, 1, 1, 1])

        label = ("**" + p["name"] + "**") if is_current else p["name"]
        if cols[0].button(label, key=f"select_{p['id']}", use_container_width=True):
            persist_current_project()
            switch_project(p["id"])
            st.rerun()
        if cols[1].button(pin_icon, key=f"pin_{p['id']}", help="Pin to top"):
            projects_store.toggle_pin(p["id"])
            st.rerun()
        if cols[2].button("✏️", key=f"edit_{p['id']}", help="Rename"):
            st.session_state[f"renaming_{p['id']}"] = not st.session_state.get(f"renaming_{p['id']}", False)
        if cols[3].button("🗑️", key=f"del_{p['id']}", help="Delete"):
            st.session_state[f"confirm_del_{p['id']}"] = True

        if st.session_state.get(f"renaming_{p['id']}"):
            new_name = st.text_input("Rename to:", value=p["name"], key=f"rename_input_{p['id']}")
            rc1, rc2 = st.columns(2)
            if rc1.button("Save", key=f"save_rename_{p['id']}", use_container_width=True):
                projects_store.rename_project(p["id"], new_name)
                st.session_state[f"renaming_{p['id']}"] = False
                st.rerun()
            if rc2.button("Cancel", key=f"cancel_rename_{p['id']}", use_container_width=True):
                st.session_state[f"renaming_{p['id']}"] = False
                st.rerun()

        if st.session_state.get(f"confirm_del_{p['id']}"):
            st.warning(f"Delete '{p['name']}' and all its files/history? This can't be undone.")
            dc1, dc2 = st.columns(2)
            if dc1.button("Yes, delete", key=f"confirm_yes_{p['id']}", use_container_width=True):
                projects_store.delete_project(p["id"])
                st.session_state[f"confirm_del_{p['id']}"] = False
                remaining = projects_store.list_projects()
                if remaining:
                    switch_project(remaining[0]["id"])
                else:
                    new_id = projects_store.create_project("My First Project")
                    switch_project(new_id)
                st.rerun()
            if dc2.button("Cancel", key=f"confirm_no_{p['id']}", use_container_width=True):
                st.session_state[f"confirm_del_{p['id']}"] = False
                st.rerun()


# --------------------------------------------------------------------------
# Sidebar: API keys + status
# --------------------------------------------------------------------------
with st.sidebar:
    st.divider()
    st.subheader("⚙ Settings")

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

    with st.form("tavily_form", clear_on_submit=True):
        tk = st.text_input(
            "Tavily API key (enables live web search & research)", type="password"
        )
        if st.form_submit_button("Save Tavily key") and tk.strip():
            key_store.add_key("tavily", tk.strip())
            st.success("Tavily key saved. Web search is now enabled.")

    st.divider()
    s = key_store.status()
    st.caption(
        f"Gemini: {s['gemini']['total']} · Groq: {s['groq']['total']} · "
        f"DeepSeek: {s['deepseek']['total']} ({s['deepseek']['exhausted']} exhausted) · "
        f"Tavily: {s['tavily']['total']}"
    )

    st.divider()
    st.subheader("📦 Download your project")
    if st.button("Prepare download"):
        zip_buf = io.BytesIO()
        with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for root, _dirs, files in os.walk(tools.WORKDIR):
                for fname in files:
                    filepath = os.path.join(root, fname)
                    arcname = os.path.relpath(filepath, tools.WORKDIR)
                    zf.write(filepath, arcname)
        st.session_state.zip_data = zip_buf.getvalue()
        st.success("Ready — click Download below.")
    if st.session_state.get("zip_data"):
        st.download_button(
            "⬇ Download ZIP",
            data=st.session_state.zip_data,
            file_name="my_project.zip",
            mime="application/zip",
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
        persist_current_project()


# --------------------------------------------------------------------------
# Main chat area
# --------------------------------------------------------------------------
st.title(f"🤖 My Agent — {projects_store.get_name(st.session_state.current_project_id)}")
st.caption(
    "Ask it to build/fix code, or ask it to research something and find real "
    "sources. It plans, works, and verifies before it stops."
)

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
        persist_current_project()

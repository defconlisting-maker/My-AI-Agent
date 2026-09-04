"""
My Agent -- Streamlit version, deployable free forever on Streamlit
Community Cloud (no Docker, no card, no expiry).

Local test:  streamlit run streamlit_app.py
Deploy:      see README.md
"""

import base64
import datetime
import io
import json
import mimetypes
import os
import random
import zipfile

import streamlit as st
import streamlit.components.v1 as components

import providers
import tools
import key_store
import documents
import projects_store

st.set_page_config(page_title="My Agent", page_icon="🤖", layout="centered")

MAX_ITERATIONS = 15
MAX_HISTORY_MESSAGES = 20  # keep API requests small enough for free-tier token limits


def trim_for_api(messages: list) -> list:
    """Return a size-capped copy of the conversation for the actual API call,
    without touching the full history kept in session_state/storage. Trims at
    user-message boundaries only, so a tool call is never separated from its
    result (which would make the request invalid)."""
    if len(messages) <= MAX_HISTORY_MESSAGES + 1:
        return messages

    system = messages[0]
    rest = messages[1:]
    user_indices = [i for i, m in enumerate(rest) if m.get("role") == "user"]
    if not user_indices:
        return messages

    keep_from = user_indices[-1]
    for idx in reversed(user_indices):
        if len(rest) - idx <= MAX_HISTORY_MESSAGES:
            keep_from = idx
        else:
            break

    return [system] + rest[keep_from:]

SYSTEM_PROMPT_BASE = """You are a helpful assistant with real tools: live web search, \
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
ground truth context for the task. If an image was uploaded, describe/analyze \
what you actually see in it.
5. Be concise in your text -- the tool calls are the actual work.
6. Call task_complete with a summary once genuinely done (for coding tasks) \
or once the question is fully answered (for research questions).
"""

LANGUAGE_INSTRUCTIONS = {
    "auto": "\n7. Reply in whichever language the person writes in -- English "
            "or Afrikaans -- matching them naturally. If they mix both in one "
            "message, you may too.",
    "english": "\n7. Always reply in English, even if the person writes in Afrikaans.",
    "afrikaans": "\n7. Always reply in Afrikaans (Suid-Afrikaanse Afrikaans), "
                 "even if the person writes in English.",
}

SYSTEM_PROMPT = SYSTEM_PROMPT_BASE  # kept for first-project initialization below

GREETINGS = {
    "morning": [
        "Good morning ☀️ What are we building today?",
        "Môre môre! Wat gaan ons vandag aanpak? 🌅",
        "Morning! Coffee's optional, curiosity isn't. What's the plan?",
    ],
    "afternoon": [
        "Good afternoon 👋 What can I help you tackle?",
        "Middag! Waarmee kan ek help?",
        "Afternoon! Ready when you are.",
    ],
    "evening": [
        "Good evening 🌆 Still going strong — what's next?",
        "Naand! Nog aan die gang? Wat is die plan?",
        "Evening! Let's get something done.",
    ],
    "night": [
        "Burning the midnight oil? 🌙 I'm here.",
        "Laataand werk, ek sien. Wat kan ek doen?",
        "Late one, huh? Let's make it count.",
    ],
}


def get_greeting() -> str:
    """A friendly, time-of-day line -- picked once per browser session, not
    re-randomized on every rerun (so it doesn't flicker as you interact)."""
    if "greeting" not in st.session_state:
        hour = datetime.datetime.now().hour
        if 5 <= hour < 12:
            bucket = "morning"
        elif 12 <= hour < 17:
            bucket = "afternoon"
        elif 17 <= hour < 22:
            bucket = "evening"
        else:
            bucket = "night"
        st.session_state.greeting = random.choice(GREETINGS[bucket])
    return st.session_state.greeting


def speak(text: str, lang: str = "en-US"):
    """Read text aloud using the browser's own built-in speech synthesis --
    free, no API, no server round-trip. Runs once per call (each rerun that
    calls this re-triggers speech, so only call it right after a fresh reply)."""
    safe_text = json.dumps(text[:2000])  # browsers choke on very long utterances
    components.html(
        f"""
        <script>
        (function() {{
            try {{
                window.speechSynthesis.cancel();
                const utter = new SpeechSynthesisUtterance({safe_text});
                utter.lang = {json.dumps(lang)};
                utter.rate = 1.0;
                window.speechSynthesis.speak(utter);
            }} catch (e) {{ console.log('Speech synthesis not available:', e); }}
        }})();
        </script>
        """,
        height=0,
    )

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

        label = ("📌 " if p.get("pinned") else "") + p["name"]
        label = ("**" + label + "**") if is_current else label
        if st.button(label, key=f"select_{p['id']}", use_container_width=True):
            persist_current_project()
            switch_project(p["id"])
            st.rerun()

        act1, act2, act3 = st.columns(3)
        pin_btn_text = "Unpin" if p.get("pinned") else "Pin"
        if act1.button(pin_btn_text, key=f"pin_{p['id']}", help="Pin to top", use_container_width=True):
            projects_store.toggle_pin(p["id"])
            st.rerun()
        if act2.button("Rename", key=f"edit_{p['id']}", help="Rename this project", use_container_width=True):
            st.session_state[f"renaming_{p['id']}"] = not st.session_state.get(f"renaming_{p['id']}", False)
        if act3.button("Delete", key=f"del_{p['id']}", help="Delete this project", use_container_width=True):
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

    lang_label = st.selectbox(
        "Reply language / Antwoordtaal",
        ["Auto-detect / Outo-bepaal", "English", "Afrikaans"],
        key="language_select",
    )
    st.session_state.language_pref = {
        "Auto-detect / Outo-bepaal": "auto",
        "English": "english",
        "Afrikaans": "afrikaans",
    }[lang_label]

    st.session_state.voice_reply_enabled = st.toggle(
        "🔊 Read replies aloud / Lees antwoorde hardop",
        value=st.session_state.get("voice_reply_enabled", False),
    )

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
    st.subheader("📄 Files in this project")
    file_list = []
    for root, _dirs, files in os.walk(tools.WORKDIR):
        for fname in files:
            full_path = os.path.join(root, fname)
            file_list.append(os.path.relpath(full_path, tools.WORKDIR))

    if not file_list:
        st.caption("No files yet — ask the agent to build something.")
    else:
        for rel_path in sorted(file_list):
            full_path = os.path.join(tools.WORKDIR, rel_path)
            try:
                with open(full_path, "rb") as f:
                    file_bytes = f.read()
                mime_type, _ = mimetypes.guess_type(rel_path)
                st.download_button(
                    f"⬇ {rel_path}",
                    data=file_bytes,
                    file_name=os.path.basename(rel_path),
                    mime=mime_type or "application/octet-stream",
                    key=f"dl_{rel_path}",
                    use_container_width=True,
                )
            except Exception:
                st.caption(f"⚠ Could not read {rel_path}")

    st.divider()
    st.subheader("📦 Download everything as a ZIP")
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


# --------------------------------------------------------------------------
# Main chat area
# --------------------------------------------------------------------------
st.title(f"🤖 My Agent — {projects_store.get_name(st.session_state.current_project_id)}")

if not st.session_state.display_log:
    st.caption(get_greeting())
else:
    st.caption(
        "Ask it to build/fix code, or ask it to research something. / "
        "Vra dit om kode te bou/regmaak, of iets na te vors."
    )

for entry in st.session_state.display_log:
    with st.chat_message(entry["role"]):
        st.markdown(entry["content"])


IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp"}
AUDIO_EXTENSIONS = {".mp3", ".wav", ".m4a", ".ogg", ".flac"}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".webm", ".avi", ".mkv"}


def run_turn(task: str, uploaded_files=None):
    """Process one user turn (typed or spoken) through the agent loop."""
    uploaded_files = uploaded_files or []

    upload_notes = []
    for uploaded in uploaded_files:
        save_path = os.path.join(tools.WORKDIR, uploaded.name)
        with open(save_path, "wb") as f:
            f.write(uploaded.getbuffer())

        ext = os.path.splitext(uploaded.name)[1].lower()
        if ext in IMAGE_EXTENSIONS:
            # Send as real image content the model can see (vision), not just text.
            mime_type = mimetypes.guess_type(uploaded.name)[0] or "image/png"
            b64 = base64.b64encode(uploaded.getbuffer()).decode("utf-8")
            st.session_state.messages.append({
                "role": "user",
                "content": [
                    {"type": "text", "text": f"[Uploaded image: {uploaded.name}]"},
                    {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{b64}"}},
                ],
            })
            upload_notes.append(f"🖼️ {uploaded.name}")
        elif ext in AUDIO_EXTENSIONS or ext in VIDEO_EXTENSIONS:
            # Transcribe the spoken audio (video: audio track only, no visual
            # understanding of what's shown) and feed the transcript as text.
            try:
                transcript = providers.transcribe_audio(save_path)
                kind = "audio" if ext in AUDIO_EXTENSIONS else "video (audio only, not visuals)"
                st.session_state.messages.append({
                    "role": "user",
                    "content": f"[Transcribed {kind}: {uploaded.name}]\n\n{transcript}",
                })
                upload_notes.append(f"🎙️ {uploaded.name}")
            except Exception as e:
                st.warning(f"Couldn't transcribe {uploaded.name}: {e}")
                upload_notes.append(f"⚠️ {uploaded.name} (transcription failed)")
        else:
            text = documents.extract_text(save_path)
            st.session_state.messages.append({
                "role": "user",
                "content": f"[Uploaded document: {uploaded.name}]\n\n{text}",
            })
            upload_notes.append(f"📎 {uploaded.name}")

    display_text = task
    if upload_notes:
        display_text = (task + "\n\n" if task else "") + "\n".join(upload_notes)

    if not task and upload_notes:
        task = ("I've attached a file — please read it and let me know what's "
                 "in it, or wait for my next message telling you what to do with it.")

    st.session_state.display_log.append({"role": "user", "content": display_text})
    st.session_state.messages.append({"role": "user", "content": task})
    with st.chat_message("user"):
        st.markdown(display_text)

    notifications = []

    def notify(event):
        notifications.append(event)

    lang_pref = st.session_state.get("language_pref", "auto")
    st.session_state.messages[0] = {
        "role": "system",
        "content": SYSTEM_PROMPT_BASE + LANGUAGE_INSTRUCTIONS[lang_pref],
    }

    with st.chat_message("assistant"):
        status_box = st.status("Working...", expanded=True)
        final_reply = None

        for step in range(MAX_ITERATIONS):
            try:
                provider_used, msg = providers.call_with_fallback(
                    trim_for_api(st.session_state.messages), tools=tools.TOOL_SCHEMAS, notify=notify
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

        if st.session_state.get("voice_reply_enabled"):
            speak_lang = "af-ZA" if lang_pref == "afrikaans" else "en-US"
            speak(final_reply, lang=speak_lang)


# --------------------------------------------------------------------------
# Voice input is temporarily removed -- three attempts at it each caused a
# real problem (overlap, then an unrelated third-party bundle failing, then
# an invisible component) that I could not verify before shipping. Rather
# than keep guessing at your expense, it's paused here until it can be
# properly tested. Typing and file attachment are unaffected.
# --------------------------------------------------------------------------
submission = st.chat_input(
    "Describe the task, or ask a question... / Beskryf die taak, of vra 'n vraag...",
    accept_file="multiple",
    file_type=["pdf", "docx", "txt", "md", "csv", "json", "py", "html", "htm", "js", "css",
               "png", "jpg", "jpeg", "gif", "webp",
               "mp3", "wav", "m4a", "ogg", "flac", "mp4", "mov", "webm", "avi", "mkv"],
)

if submission:
    run_turn(submission.text or "", submission["files"] or [])

# My Agent — free web-based coding agent (Streamlit version)

Hugging Face locked its free Docker tier behind a paywall recently, so this
version uses **Streamlit Community Cloud** instead — genuinely free forever,
no credit card, no Docker, deploys straight from GitHub. Same brain underneath:
Gemini and Groq (free forever) with DeepSeek as bonus capacity that quietly
retires itself once its free tokens run out.

## Step 1 — Get your free API keys (5 minutes, no card needed for any of them)

- **Gemini**: [aistudio.google.com/apikey](https://aistudio.google.com/apikey) → sign in with Google → "Create API key"
- **Groq**: [console.groq.com/keys](https://console.groq.com/keys) → sign up → "Create API Key"
- **DeepSeek** (optional bonus): [platform.deepseek.com](https://platform.deepseek.com) → sign up → create a key

Copy each one into a notes app. You'll paste them into the app itself later —
never into any file.

## Step 2 — Put the code on GitHub (no Git software needed, all in browser)

1. Go to [github.com](https://github.com) and click **Sign up** (free, no card).
2. Once logged in, click the **+** icon top-right → **New repository**.
3. Name it `my-agent`. Leave it **Public**. Do NOT check "Add a README" (we
   already have one). Click **Create repository**.
4. On the new repo's page, click **uploading an existing file** (a link in
   the middle of the page).
5. Drag in all five files: `streamlit_app.py`, `providers.py`, `tools.py`,
   `key_store.py`, `documents.py`, `requirements.txt`, `README.md`.
6. Scroll down, click **Commit changes**. Your code is now on GitHub.

## Step 3 — Deploy on Streamlit Community Cloud (2 minutes)

1. Go to [share.streamlit.io](https://share.streamlit.io) and click **Sign up**
   — choose "Continue with GitHub" so the two are linked automatically. Free,
   no card.
2. Click **Create app** (or "New app").
3. Choose your `my-agent` repository, branch `main`, and for "Main file path"
   type: `streamlit_app.py`
4. Click **Deploy**. It builds for 1–2 minutes, then your app is live at a
   URL like `https://my-agent-yourname.streamlit.app` — bookmark it. This
   link doesn't expire and isn't on a countdown.

## Step 4 — Add your keys and use it

1. Open your app's URL. In the left sidebar, paste your Gemini key and click
   **Save Gemini key**. Same for Groq. DeepSeek is optional.
2. Type a task in the chat box at the bottom, e.g.:
   *"Build a Python script that renames all files in a folder to lowercase"*
3. Watch it plan, write, and test the code live in the chat.

## Honest limitations

- **The app sleeps after long inactivity** and takes ~30 seconds to wake up
  on your next visit — not a cost, just a small delay.
- **1 GB memory limit** on the free tier — fine for coding tasks, would
  struggle with huge datasets or heavy ML workloads.
- **Your repo is public**, meaning the *code* is visible to anyone — but your
  API keys are never in the code, only pasted live into the running app, so
  they stay private. Don't paste keys into any file you upload to GitHub.
- **Anyone with your app's URL can use it** once it's live (it's a public
  link). If that matters to you, a simple password-gate can be added later —
  just ask.
- **DeepSeek's free grant is one-time per key**, not renewing — that's why
  the app rotates in a new key when you paste one rather than pretending
  it's unlimited.
- **Rate limits, not payment walls**, still apply on Gemini/Groq — normal
  one-person use rarely hits them.

## What's genuinely yours

The name, the interface, all the code in this repo — yours to rename, restyle,
extend. The AI models underneath are borrowed (training one from scratch costs
tens of millions of dollars, no way around that), but everything wrapped
around them is yours to change.

## Next features worth adding

1. A simple password so random visitors with the link can't use your app
2. Persistent chat history (currently resets if the app restarts)
3. A "download this project as a zip" button for finished work
4. Auto-push finished work to a GitHub repo so nothing is lost on restart

Tell me which one you want next.

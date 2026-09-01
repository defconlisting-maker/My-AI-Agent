My Agent — free web-based coding + research agent (Streamlit version)
Hugging Face locked its free Docker tier behind a paywall recently, so this
version uses Streamlit Community Cloud instead — genuinely free forever,
no credit card, no Docker, deploys straight from GitHub. Brain underneath:
Gemini and Groq (free forever) with DeepSeek as bonus capacity that quietly
retires itself once its free tokens run out, plus Tavily for live web search.
What it does
Chat interface in your browser, works from phone or laptop
Give it a coding task → it plans, writes files, runs commands, checks its own
work, and tells you when it's actually done (verified, not just "should work")
Give it a research question → it searches the live web and shares real
sources/links (great for finding tutorials, study material, official past
paper repositories) rather than answering from memory alone
Upload a PDF/Word/text document → it reads it and uses it as context for the task
Prepare and download a ZIP of anything it built, right from the sidebar
Automatically falls back Gemini → Groq → DeepSeek if one is rate-limited
If a DeepSeek key runs out, you get a small non-blocking banner — current work
keeps going on Gemini/Groq. Paste a new DeepSeek key in Settings anytime.
A note if your kids will use this
This app has none of the safety layers that claude.ai, ChatGPT, or Gemini's own
consumer apps have — no content filtering, no age-appropriate guardrails. It's
built to point to real sources for research (past papers, tutorials, study
sites) rather than fabricate answers, and the system prompt nudges it toward
explaining concepts rather than just handing over answers to copy — but there's
no safety net catching a wrong or inappropriate response the way there is in
a proper consumer product. Worth supervising early use and treating its answers
the way you'd treat a search engine result: generally useful, not infallible.
Step 1 — Get your free API keys (5 minutes, no card needed for any of them)
Gemini: aistudio.google.com/apikey → sign in with Google → "Create API key"
Groq: console.groq.com/keys → sign up → "Create API Key"
Tavily (enables live web search & research): tavily.com → sign up → copy the key from your dashboard. 1,000 free searches/month, resets automatically every month, no card required.
DeepSeek (optional bonus AI engine): platform.deepseek.com → sign up → create a key
Copy each one into a notes app. You'll paste them into the app itself later —
never into any file.
Step 2 — Put the code on GitHub (no Git software needed, all in browser)
Go to github.com and click Sign up (free, no card).
Once logged in, click the + icon top-right → New repository.
Name it `my-agent`. Leave it Public. Do NOT check "Add a README" (we
already have one). Click Create repository.
On the new repo's page, click uploading an existing file (a link in
the middle of the page).
Drag in all five files: `streamlit_app.py`, `providers.py`, `tools.py`,
`key_store.py`, `documents.py`, `requirements.txt`, `README.md`.
Scroll down, click Commit changes. Your code is now on GitHub.
Step 3 — Deploy on Streamlit Community Cloud (2 minutes)
Go to share.streamlit.io and click Sign up
— choose "Continue with GitHub" so the two are linked automatically. Free,
no card.
Click Create app (or "New app").
Choose your `my-agent` repository, branch `main`, and for "Main file path"
type: `streamlit_app.py`
Click Deploy. It builds for 1–2 minutes, then your app is live at a
URL like `https://my-agent-yourname.streamlit.app` — bookmark it. This
link doesn't expire and isn't on a countdown.
Step 4 — Add your keys and use it
Open your app's URL. In the left sidebar, paste your Gemini key and click
Save Gemini key. Same for Groq. DeepSeek is optional.
Type a task in the chat box at the bottom, e.g.:
"Build a Python script that renames all files in a folder to lowercase"
Watch it plan, write, and test the code live in the chat.
Honest limitations
The app sleeps after long inactivity and takes ~30 seconds to wake up
on your next visit — not a cost, just a small delay.
1 GB memory limit on the free tier — fine for coding tasks, would
struggle with huge datasets or heavy ML workloads.
Your repo is public, meaning the code is visible to anyone — but your
API keys are never in the code, only pasted live into the running app, so
they stay private. Don't paste keys into any file you upload to GitHub.
Anyone with your app's URL can use it once it's live (it's a public
link). If that matters to you, a simple password-gate can be added later —
just ask.
DeepSeek's free grant is one-time per key, not renewing — that's why
the app rotates in a new key when you paste one rather than pretending
it's unlimited.
Rate limits, not payment walls, still apply on Gemini/Groq — normal
one-person use rarely hits them.
What's genuinely yours
The name, the interface, all the code in this repo — yours to rename, restyle,
extend. The AI models underneath are borrowed (training one from scratch costs
tens of millions of dollars, no way around that), but everything wrapped
around them is yours to change.
Next features worth adding
A simple password so random visitors with the link can't use your app
Persistent chat history (currently resets if the app restarts)
A "download this project as a zip" button for finished work
Auto-push finished work to a GitHub repo so nothing is lost on restart
Tell me which one you want next.

"""Extract plain text from uploaded documents so the agent can read them."""

import os


def extract_text(filepath: str) -> str:
    ext = os.path.splitext(filepath)[1].lower()

    if ext == ".pdf":
        from pypdf import PdfReader
        reader = PdfReader(filepath)
        text = "\n".join(page.extract_text() or "" for page in reader.pages)

    elif ext == ".docx":
        from docx import Document
        doc = Document(filepath)
        text = "\n".join(p.text for p in doc.paragraphs)

    elif ext in (".txt", ".md", ".csv", ".json", ".py", ".js", ".html", ".htm", ".css"):
        with open(filepath, "r", errors="replace") as f:
            text = f.read()

    else:
        return f"[Unsupported file type: {ext}. Supported: pdf, docx, txt, md, csv, json, py, js, html]"

    if len(text) > 20000:
        text = text[:20000] + "\n...[truncated, document is longer]..."
    return text

"""
Same tool set as the CLI agent (bash, file read/write/edit, list, finish),
but schemas are in OpenAI "function calling" format since Gemini/Groq/DeepSeek
are all called through OpenAI-compatible endpoints.
"""

import os
import subprocess

import requests

import key_store

WORKDIR = os.environ.get("AGENT_WORKDIR", os.path.join(os.getcwd(), "workspace"))
os.makedirs(WORKDIR, exist_ok=True)


def _resolve(path: str) -> str:
    full = os.path.normpath(os.path.join(WORKDIR, path))
    if not full.startswith(os.path.normpath(WORKDIR)):
        raise ValueError(f"Path '{path}' resolves outside the working directory.")
    return full


def bash_execute(command: str, timeout: int = 60) -> dict:
    try:
        result = subprocess.run(
            command, shell=True, cwd=WORKDIR,
            capture_output=True, text=True, timeout=timeout,
        )
        output = result.stdout + result.stderr
        if len(output) > 8000:
            output = output[:4000] + "\n...[truncated]...\n" + output[-4000:]
        return {"exit_code": result.returncode, "output": output or "(no output)"}
    except subprocess.TimeoutExpired:
        return {"exit_code": -1, "output": f"Command timed out after {timeout}s."}
    except Exception as e:
        return {"exit_code": -1, "output": f"Error: {e}"}


def read_file(path: str) -> dict:
    try:
        with open(_resolve(path), "r", errors="replace") as f:
            content = f.read()
        if len(content) > 12000:
            content = content[:12000] + "\n...[truncated]..."
        return {"content": content}
    except FileNotFoundError:
        return {"error": f"File not found: {path}"}
    except Exception as e:
        return {"error": str(e)}


def write_file(path: str, content: str) -> dict:
    try:
        full = _resolve(path)
        os.makedirs(os.path.dirname(full) or ".", exist_ok=True)
        with open(full, "w") as f:
            f.write(content)
        return {"status": f"Wrote {len(content)} chars to {path}"}
    except Exception as e:
        return {"error": str(e)}


def edit_file(path: str, old_str: str, new_str: str) -> dict:
    try:
        full = _resolve(path)
        with open(full, "r") as f:
            content = f.read()
        count = content.count(old_str)
        if count == 0:
            return {"error": "old_str not found. Nothing changed."}
        if count > 1:
            return {"error": f"old_str appears {count} times; must be unique."}
        with open(full, "w") as f:
            f.write(content.replace(old_str, new_str))
        return {"status": f"Edited {path}."}
    except FileNotFoundError:
        return {"error": f"File not found: {path}"}
    except Exception as e:
        return {"error": str(e)}


def list_directory(path: str = ".") -> dict:
    try:
        full = _resolve(path)
        entries = []
        for name in sorted(os.listdir(full)):
            if name.startswith(".git"):
                continue
            tag = "/" if os.path.isdir(os.path.join(full, name)) else ""
            entries.append(name + tag)
        return {"entries": entries}
    except Exception as e:
        return {"error": str(e)}


def web_search(query: str, max_results: int = 5) -> dict:
    """Live web search via Tavily's free tier. Returns a short answer plus
    titles/URLs/snippets so the agent can point people to real sources
    (tutorials, official resource sites, documentation, etc.) instead of
    guessing from memory."""
    key = key_store.get_active_key("tavily")
    if not key:
        return {"error": "No Tavily API key configured. Add one in Settings "
                          "to enable web search (free, no card, at tavily.com)."}
    try:
        resp = requests.post(
            "https://api.tavily.com/search",
            json={
                "api_key": key,
                "query": query,
                "max_results": max_results,
                "include_answer": True,
            },
            timeout=20,
        )
        data = resp.json()
        if resp.status_code != 200:
            return {"error": data.get("error", f"Tavily error {resp.status_code}")}
        results = [
            {
                "title": r.get("title"),
                "url": r.get("url"),
                "snippet": (r.get("content") or "")[:400],
            }
            for r in data.get("results", [])
        ]
        return {"quick_answer": data.get("answer"), "sources": results}
    except Exception as e:
        return {"error": f"Search failed: {e}"}


TOOL_SCHEMAS = [
    {"type": "function", "function": {
        "name": "web_search",
        "description": "Search the live web for current information: news, tutorials, "
                        "documentation, official resource sites, study material, past "
                        "exam paper repositories, etc. Returns a short answer plus a "
                        "list of source titles/URLs/snippets -- always point the person "
                        "to real sources rather than fabricating content.",
        "parameters": {"type": "object", "properties": {
            "query": {"type": "string"},
            "max_results": {"type": "integer", "description": "Default 5, max 10."},
        }, "required": ["query"]},
    }},
    {"type": "function", "function": {
        "name": "bash_execute",
        "description": "Run a shell command in the working directory (tests, builds, installs, etc).",
        "parameters": {"type": "object", "properties": {
            "command": {"type": "string"},
            "timeout": {"type": "integer"},
        }, "required": ["command"]},
    }},
    {"type": "function", "function": {
        "name": "read_file",
        "description": "Read a file's contents, relative to the working directory.",
        "parameters": {"type": "object", "properties": {
            "path": {"type": "string"},
        }, "required": ["path"]},
    }},
    {"type": "function", "function": {
        "name": "write_file",
        "description": "Create a new file or overwrite an existing one entirely.",
        "parameters": {"type": "object", "properties": {
            "path": {"type": "string"}, "content": {"type": "string"},
        }, "required": ["path", "content"]},
    }},
    {"type": "function", "function": {
        "name": "edit_file",
        "description": "Replace a unique snippet (old_str) with new text (new_str) in an existing file.",
        "parameters": {"type": "object", "properties": {
            "path": {"type": "string"},
            "old_str": {"type": "string"},
            "new_str": {"type": "string"},
        }, "required": ["path", "old_str", "new_str"]},
    }},
    {"type": "function", "function": {
        "name": "list_directory",
        "description": "List files/folders at a path (default: working directory root).",
        "parameters": {"type": "object", "properties": {
            "path": {"type": "string"},
        }},
    }},
    {"type": "function", "function": {
        "name": "task_complete",
        "description": "Call when the task is fully done AND verified by actually running it.",
        "parameters": {"type": "object", "properties": {
            "summary": {"type": "string"},
        }, "required": ["summary"]},
    }},
]


def execute_tool(name: str, args: dict) -> dict:
    if name == "web_search":
        return web_search(**args)
    if name == "bash_execute":
        return bash_execute(**args)
    if name == "read_file":
        return read_file(**args)
    if name == "write_file":
        return write_file(**args)
    if name == "edit_file":
        return edit_file(**args)
    if name == "list_directory":
        return list_directory(**args)
    if name == "task_complete":
        return {"status": "done", "summary": args.get("summary", "")}
    return {"error": f"Unknown tool: {name}"}

"""
Projects: each one is an isolated chat history + file workspace. Lets the
person keep several things going (a coding project, a research thread, a
kid's homework helper) without them bleeding into each other, and switch
back to any of them later.

Stored on disk under PROJECTS_ROOT:
  projects/index.json              <- list of {id, name, pinned, created_at, updated_at}
  projects/<id>/state.json         <- {"messages": [...], "display_log": [...]}
  projects/<id>/workspace/         <- files the agent reads/writes for that project
"""

import json
import os
import shutil
import threading
import time
import uuid

PROJECTS_ROOT = os.environ.get("AGENT_PROJECTS_ROOT", os.path.join(os.getcwd(), "projects"))
INDEX_FILE = os.path.join(PROJECTS_ROOT, "index.json")
_lock = threading.Lock()

os.makedirs(PROJECTS_ROOT, exist_ok=True)


def _load_index() -> list:
    if not os.path.exists(INDEX_FILE):
        return []
    with open(INDEX_FILE, "r") as f:
        return json.load(f)


def _save_index(data: list):
    with open(INDEX_FILE, "w") as f:
        json.dump(data, f, indent=2)


def _project_dir(pid: str) -> str:
    return os.path.join(PROJECTS_ROOT, pid)


def get_workspace(pid: str) -> str:
    d = os.path.join(_project_dir(pid), "workspace")
    os.makedirs(d, exist_ok=True)
    return d


def list_projects() -> list:
    """Pinned first, then most recently updated."""
    with _lock:
        data = _load_index()
    return sorted(data, key=lambda p: (not p.get("pinned", False), -p.get("updated_at", 0)))


def create_project(name: str = None) -> str:
    pid = uuid.uuid4().hex[:8]
    now = time.time()
    name = name or f"New Project"
    with _lock:
        data = _load_index()
        data.append({
            "id": pid, "name": name, "pinned": False,
            "created_at": now, "updated_at": now,
        })
        _save_index(data)
    os.makedirs(_project_dir(pid), exist_ok=True)
    get_workspace(pid)
    save_state(pid, messages=[], display_log=[])
    return pid


def load_state(pid: str) -> dict:
    state_file = os.path.join(_project_dir(pid), "state.json")
    if not os.path.exists(state_file):
        return {"messages": [], "display_log": []}
    with open(state_file, "r") as f:
        return json.load(f)


def save_state(pid: str, messages: list, display_log: list):
    state_file = os.path.join(_project_dir(pid), "state.json")
    with open(state_file, "w") as f:
        json.dump({"messages": messages, "display_log": display_log}, f)
    with _lock:
        data = _load_index()
        for p in data:
            if p["id"] == pid:
                p["updated_at"] = time.time()
        _save_index(data)


def rename_project(pid: str, new_name: str):
    new_name = new_name.strip() or "Untitled Project"
    with _lock:
        data = _load_index()
        for p in data:
            if p["id"] == pid:
                p["name"] = new_name
        _save_index(data)


def toggle_pin(pid: str):
    with _lock:
        data = _load_index()
        for p in data:
            if p["id"] == pid:
                p["pinned"] = not p.get("pinned", False)
        _save_index(data)


def delete_project(pid: str):
    with _lock:
        data = _load_index()
        data = [p for p in data if p["id"] != pid]
        _save_index(data)
    shutil.rmtree(_project_dir(pid), ignore_errors=True)


def get_name(pid: str) -> str:
    for p in list_projects():
        if p["id"] == pid:
            return p["name"]
    return "Untitled Project"

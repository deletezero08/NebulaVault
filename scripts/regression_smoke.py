#!/usr/bin/env python3
import asyncio
import io
import json
import shutil
import sys
import tempfile
import urllib.parse
import uuid
from pathlib import Path
from typing import Any, Dict, Iterator, List

from fastapi.testclient import TestClient
from sse_starlette.sse import AppStatus

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import main
import src.config as config


class FakeRAG:
    def __init__(self) -> None:
        self.db = object()
        self.retriever = object()

    def index_docs(self, progress_callback=None) -> Dict[str, Any]:
        if progress_callback:
            progress_callback({"type": "progress", "message": "fake indexing..."})
        return {"ok": True, "chunk_count": 3, "message": "fake index done"}

    def stream_query(self, question: str, category: str = None, history: List[Dict[str, Any]] = None) -> Iterator[Dict[str, Any]]:
        yield {"type": "status", "data": "mock intent analyzed"}
        yield {"type": "token", "data": f"answer for: {question}"}
        yield {"type": "sources", "data": ["sample.md"]}

    def distill_insights(self, history: List[Dict[str, Any]]) -> str:
        return "mock insight summary"


def assert_true(cond: bool, message: str) -> None:
    if not cond:
        raise AssertionError(message)


def parse_sse_events(raw: str) -> List[Dict[str, str]]:
    events: List[Dict[str, str]] = []
    chunks = [c for c in raw.replace("\r\n", "\n").split("\n\n") if c.strip()]
    for chunk in chunks:
        evt: Dict[str, str] = {"event": "message", "data": ""}
        for line in chunk.split("\n"):
            if line.startswith("event:"):
                evt["event"] = line.split(":", 1)[1].strip()
            elif line.startswith("data:"):
                evt["data"] += line.split(":", 1)[1].lstrip()
        events.append(evt)
    return events


def run() -> None:
    tmp_root = Path(tempfile.mkdtemp(prefix="rag_smoke_"))
    docs_dir = tmp_root / "docs"
    chroma_dir = tmp_root / "chroma_db"
    sessions_dir = tmp_root / "sessions"
    memory_dir = tmp_root / "memory"
    skills_dir = tmp_root / "skills"
    for d in [docs_dir, chroma_dir, sessions_dir, memory_dir, skills_dir]:
        d.mkdir(parents=True, exist_ok=True)

    old = {
        "DOCS_DIR": config.DOCS_DIR,
        "CHROMA_DIR": config.CHROMA_DIR,
        "MANIFEST_FILE": config.MANIFEST_FILE,
        "SESSIONS_DIR": config.SESSIONS_DIR,
        "MEMORY_DIR": config.MEMORY_DIR,
        "SKILLS_DIR": config.SKILLS_DIR,
        "USAGE_FILE": config.USAGE_FILE,
    }

    config.DOCS_DIR = docs_dir
    config.CHROMA_DIR = chroma_dir
    config.MANIFEST_FILE = chroma_dir / "index_manifest.json"
    config.SESSIONS_DIR = sessions_dir
    config.MEMORY_DIR = memory_dir
    config.SKILLS_DIR = skills_dir
    config.USAGE_FILE = tmp_root / "file_usage.json"

    main.DOCS_DIR = docs_dir
    main.SKILLS_DIR = skills_dir
    main.rag_instance = FakeRAG()
    main.API_KEY = "smoke-token"

    client = TestClient(main.app)
    client.cookies.set("rag_token", "smoke-token")

    try:
        files = [
            ("files", ("sample.md", io.BytesIO(b"# title\nhello world"), "text/markdown")),
            ("files", ("table.csv", io.BytesIO(b"a,b\n1,2"), "text/csv")),
            ("relative_paths", (None, "sample.md")),
            ("relative_paths", (None, "table.csv")),
            ("analyze", (None, "false")),
        ]
        r = client.post("/api/upload", files=files)
        assert_true(r.status_code == 200, "upload status not 200")
        payload = r.json()
        assert_true(payload.get("ok") is True, "upload not ok")
        assert_true(payload.get("archive_path"), "archive_path should exist for analyze=false")

        archive = payload["archive_path"]
        archived_md = docs_dir / archive / "sample.md"
        assert_true(archived_md.exists(), "archived file not found")

        r = client.get("/api/files")
        assert_true(r.status_code == 200, "files tree status not 200")
        tree = r.json()
        docs_node = [c for c in tree["children"] if c["name"] == "docs"][0]
        file_paths: List[str] = []

        def walk(node: Dict[str, Any]) -> None:
            if node.get("type") == "file":
                file_paths.append(node.get("path"))
            for child in node.get("children", []) or []:
                walk(child)

        for child in docs_node.get("children", []):
            walk(child)
        assert_true(any(p and not p.startswith("docs/") for p in file_paths), "docs file paths should not be prefixed with docs/")

        target_preview = [p for p in file_paths if p and p.endswith("sample.md")][0]
        r = client.get("/api/files/content", params={"path": target_preview})
        assert_true(r.status_code == 200, "preview status not 200")
        p = r.json()
        assert_true(p.get("ok") is True and "hello world" in p.get("content", ""), "preview content mismatch")

        AppStatus.should_exit_event = asyncio.Event()
        r = client.post("/api/index")
        assert_true(r.status_code == 200, "index status not 200")
        events = parse_sse_events(r.text)
        assert_true(any(e["event"] == "success" for e in events), "index should emit success event")

        q = {"query": "请总结 sample.md", "category": "all", "history": [{"role": "user", "content": "你好"}]}
        AppStatus.should_exit_event = asyncio.Event()
        r = client.post("/api/query", json=q)
        assert_true(r.status_code == 200, "query status not 200")
        events = parse_sse_events(r.text)
        event_types = {e["event"] for e in events}
        assert_true("token" in event_types and "sources" in event_types, "query missing token/sources events")

        sid = str(uuid.uuid4())
        session_data = {"id": sid, "title": "Smoke Session", "history": [{"user": "分析 sample.md", "assistant": "done"}]}
        ok = config.save_session(sid, session_data)
        assert_true(ok, "save_session failed")

        r = client.post(f"/api/sessions/{sid}/summarize")
        assert_true(r.status_code == 200, "summarize status not 200")
        s = r.json()
        assert_true(s.get("ok") is True, "summarize not ok")
        key = urllib.parse.quote(f"{archive}/sample.md", safe="")
        assert_true((memory_dir / f"{key}.json").exists(), "memory file not created with encoded key")

        print("SMOKE PASS")
    finally:
        config.DOCS_DIR = old["DOCS_DIR"]
        config.CHROMA_DIR = old["CHROMA_DIR"]
        config.MANIFEST_FILE = old["MANIFEST_FILE"]
        config.SESSIONS_DIR = old["SESSIONS_DIR"]
        config.MEMORY_DIR = old["MEMORY_DIR"]
        config.SKILLS_DIR = old["SKILLS_DIR"]
        config.USAGE_FILE = old["USAGE_FILE"]
        shutil.rmtree(tmp_root, ignore_errors=True)


if __name__ == "__main__":
    run()

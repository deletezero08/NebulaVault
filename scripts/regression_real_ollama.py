#!/usr/bin/env python3
import asyncio
import io
import shutil
import sys
import tempfile
import uuid
from pathlib import Path
from typing import Any, Dict, List

from fastapi.testclient import TestClient
from sse_starlette.sse import AppStatus

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import main
import src.config as config
import src.indexer as indexer


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
    tmp_root = Path(tempfile.mkdtemp(prefix="rag_real_"))
    docs_dir = tmp_root / "docs"
    chroma_dir = tmp_root / "chroma_db"
    sessions_dir = tmp_root / "sessions"
    memory_dir = tmp_root / "memory"
    skills_dir = tmp_root / "skills"
    for d in [docs_dir, chroma_dir, sessions_dir, memory_dir, skills_dir]:
        d.mkdir(parents=True, exist_ok=True)

    sample = docs_dir / "sample.md"
    sample.write_text(
        "# 集成回归测试文档\n\n"
        "项目代号：Aurora。\n"
        "上线日期：2026-03-01。\n"
        "核心结论：系统在高并发下需要启用队列限流。\n",
        encoding="utf-8",
    )

    old = {
        "DOCS_DIR": config.DOCS_DIR,
        "CHROMA_DIR": config.CHROMA_DIR,
        "MANIFEST_FILE": config.MANIFEST_FILE,
        "SESSIONS_DIR": config.SESSIONS_DIR,
        "MEMORY_DIR": config.MEMORY_DIR,
        "SKILLS_DIR": config.SKILLS_DIR,
        "USAGE_FILE": config.USAGE_FILE,
        "MAIN_DOCS_DIR": main.DOCS_DIR,
        "MAIN_SKILLS_DIR": main.SKILLS_DIR,
        "INDEXER_CHROMA_DIR": indexer.CHROMA_DIR,
        "INDEXER_DOCS_DIR": indexer.DOCS_DIR,
        "INDEXER_SKILLS_DIR": indexer.SKILLS_DIR,
        "INDEXER_MANIFEST_FILE": indexer.MANIFEST_FILE,
        "INDEXER_CLIENT": getattr(indexer, "_chroma_client", None),
        "MAIN_RAG_INSTANCE": main.rag_instance,
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
    main.rag_instance = None

    indexer.DOCS_DIR = docs_dir
    indexer.SKILLS_DIR = skills_dir
    indexer.CHROMA_DIR = chroma_dir
    indexer.MANIFEST_FILE = chroma_dir / "index_manifest.json"
    indexer._chroma_client = None

    client = TestClient(main.app)
    client.cookies.set("rag_token", main.API_KEY)

    try:
        r = client.get("/api/health")
        assert_true(r.status_code == 200, "health status not 200")
        health = r.json()
        assert_true(health.get("ollama", {}).get("reachable") is True, "ollama not reachable")
        assert_true(health.get("ollama", {}).get("model_available") is True, "llm model unavailable")

        AppStatus.should_exit_event = asyncio.Event()
        r = client.post("/api/index")
        assert_true(r.status_code == 200, "index status not 200")
        events = parse_sse_events(r.text)
        assert_true(any(e["event"] == "success" for e in events), "index should emit success")

        q = {
            "query": "这个文档提到的项目代号和上线日期是什么？",
            "category": "all",
            "history": [{"role": "user", "content": "请根据文档回答"}],
        }
        AppStatus.should_exit_event = asyncio.Event()
        r = client.post("/api/query", json=q)
        assert_true(r.status_code == 200, "query status not 200")
        events = parse_sse_events(r.text)
        token_data = "".join(e["data"] for e in events if e["event"] == "token")
        assert_true(bool(token_data.strip()), "query token stream empty")
        assert_true(any(e["event"] == "sources" for e in events), "query missing sources event")

        sid = str(uuid.uuid4())
        ok = config.save_session(
            sid,
            {
                "id": sid,
                "title": "Real Regression Session",
                "history": [{"user": "分析 sample.md", "assistant": token_data[:300]}],
            },
        )
        assert_true(ok, "save_session failed")
        r = client.post(f"/api/sessions/{sid}/summarize")
        assert_true(r.status_code == 200 and r.json().get("ok") is True, "summarize failed")

        print("REAL OLLAMA REGRESSION PASS")
    finally:
        config.DOCS_DIR = old["DOCS_DIR"]
        config.CHROMA_DIR = old["CHROMA_DIR"]
        config.MANIFEST_FILE = old["MANIFEST_FILE"]
        config.SESSIONS_DIR = old["SESSIONS_DIR"]
        config.MEMORY_DIR = old["MEMORY_DIR"]
        config.SKILLS_DIR = old["SKILLS_DIR"]
        config.USAGE_FILE = old["USAGE_FILE"]

        main.DOCS_DIR = old["MAIN_DOCS_DIR"]
        main.SKILLS_DIR = old["MAIN_SKILLS_DIR"]
        main.rag_instance = old["MAIN_RAG_INSTANCE"]

        indexer.DOCS_DIR = old["INDEXER_DOCS_DIR"]
        indexer.SKILLS_DIR = old["INDEXER_SKILLS_DIR"]
        indexer.CHROMA_DIR = old["INDEXER_CHROMA_DIR"]
        indexer.MANIFEST_FILE = old["INDEXER_MANIFEST_FILE"]
        indexer._chroma_client = old["INDEXER_CLIENT"]

        shutil.rmtree(tmp_root, ignore_errors=True)


if __name__ == "__main__":
    run()

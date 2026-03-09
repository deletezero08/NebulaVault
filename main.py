#!/usr/bin/env python3
import asyncio
import json
import logging
import os
import queue
import secrets
import time
from pathlib import Path

import shutil
from datetime import datetime
from typing import List, Optional, Dict, Any, AsyncGenerator, Union
from pathlib import Path
import threading

from fastapi import FastAPI, UploadFile, File, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse
import httpx
import uvicorn
from logging.handlers import RotatingFileHandler
from urllib.parse import quote

from src.engine import LocalRAG
from src.config import get_runtime_status, list_doc_files, list_skill_files, DOCS_DIR, SKILLS_DIR

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
SERVER_LOG = BASE_DIR / "server.log"
INDEX_TIMEOUT_SECONDS = int(os.getenv("RAG_INDEX_TIMEOUT_SECONDS", "180"))
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434").rstrip("/")

app = FastAPI(title="星澜知库 NebulaVault API")

STATIC_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

logger = logging.getLogger("rag_api")
core_logger = logging.getLogger("rag_core")

for l in [logger, core_logger]:
    if not l.handlers:
        l.setLevel(logging.INFO)
        # Use RotatingFileHandler to cap log size at 5MB, keeping 3 backups
        handler = RotatingFileHandler(SERVER_LOG, maxBytes=5*1024*1024, backupCount=3, encoding="utf-8")
        formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
        handler.setFormatter(formatter)
        l.addHandler(handler)
        l.propagate = False

raw_api_key = os.getenv("RAG_API_KEY", "").strip()
API_KEY = raw_api_key or secrets.token_urlsafe(32)
if not raw_api_key:
    logger.warning("RAG_API_KEY not set; using an ephemeral runtime token")
RATE_LIMIT_DICT: Dict[str, List[float]] = {}  # {ip: [timestamps]}

@app.middleware("http")
async def security_middleware(request: Request, call_next: Any) -> Any:
    # 1. API Authentication
    if request.url.path.startswith("/api/") and request.url.path not in ["/api/health", "/api/status"]:
        token = None
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]
        elif request.url.path in ["/api/query/stream", "/api/index", "/api/files/raw"] or "stream" in request.url.path:
            # Fallback to query param for EventSource (SSE) and iframes which cannot send custom headers
            token = request.query_params.get("token")
        if not token:
            token = request.cookies.get("rag_token")
        
        if not token:
            return JSONResponse(status_code=401, content={"error": "Missing Authorization token"})
            
        if token != API_KEY:
            return JSONResponse(status_code=403, content={"error": "Invalid API Key"})

    # 2. Rate Limiting (60 requests per minute)
    # Ignore high-frequency polling endpoints
    if request.url.path.startswith("/api/") and request.url.path not in ["/api/status", "/api/files"]:
        client_ip = request.client.host if request.client else "unknown"
        now = time.time()
        
        if client_ip not in RATE_LIMIT_DICT:
            RATE_LIMIT_DICT[client_ip] = []
            
        # Clean up old timestamps
        RATE_LIMIT_DICT[client_ip] = [ts for ts in RATE_LIMIT_DICT[client_ip] if now - ts < 60]
        
        if len(RATE_LIMIT_DICT[client_ip]) >= 60:
            logger.warning(f"Rate limit exceeded for IP: {client_ip}")
            return JSONResponse(status_code=429, content={"error": "Too many requests. Please try again later."})
            
        RATE_LIMIT_DICT[client_ip].append(now)

    response = await call_next(request)
    return response

import threading
rag_instance: Optional[LocalRAG] = None
rag_lock = threading.Lock()

def get_rag() -> LocalRAG:
    global rag_instance
    if rag_instance is None:
        with rag_lock:
            if rag_instance is None:
                rag_instance = LocalRAG()
    return rag_instance


@app.get("/", response_class=HTMLResponse)
async def read_root() -> HTMLResponse:
    response = HTMLResponse(content=(STATIC_DIR / "index.html").read_text(encoding="utf-8"))
    response.set_cookie(
        key="rag_token",
        value=API_KEY,
        httponly=True,
        samesite="lax",
    )
    return response


@app.get("/api/status")
async def get_status() -> Dict[str, Any]:
    from src.config import list_memories
    return {
        "status": {**get_runtime_status(), "memories": list_memories()},
        "doc_files": list_doc_files(),
        "skill_files": list_skill_files(),
    }


async def check_ollama_health(model_name: str) -> Dict[str, Any]:
    url = f"{OLLAMA_HOST}/api/tags"
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get(url)
        resp.raise_for_status()
        payload = resp.json()
        models = payload.get("models", [])
        names = {item.get("name") for item in models if item.get("name")}
        return {
            "reachable": True,
            "model_available": model_name in names,
            "error": None,
            "models_count": len(models),
        }
    except httpx.RequestError as exc:
        return {
            "reachable": False,
            "model_available": False,
            "error": str(exc),
            "models_count": 0,
        }


@app.get("/api/health")
async def get_health() -> Dict[str, Any]:
    status = get_runtime_status()
    ollama = await check_ollama_health(status["llm_model"])

    loaded_index = False
    if rag_instance is not None:
        loaded_index = rag_instance.db is not None and rag_instance.retriever is not None

    return {
        "ollama": {
            "host": OLLAMA_HOST,
            "reachable": ollama["reachable"],
            "model": status["llm_model"],
            "model_available": ollama["model_available"],
            "error": ollama["error"],
            "models_count": ollama["models_count"],
        },
        "index": {
            "persisted": status["has_index"],
            "loaded": loaded_index,
        },
        "ready": ollama["reachable"] and ollama["model_available"] and status["has_index"],
    }


@app.post("/api/index")
async def build_index() -> EventSourceResponse:
    async def sse_generator() -> AsyncGenerator[Dict[str, Any], None]:
        yield {"data": "收到索引构建请求...", "event": "progress"}
        rag = get_rag()
        logger.info("index_start")
        q: queue.Queue = queue.Queue()

        def push_progress(msg: Dict[str, Any]) -> None:
            q.put(msg)

        loop = asyncio.get_running_loop()

        def worker() -> None:
            try:
                res = rag.index_docs(progress_callback=push_progress)
                q.put({"type": "done", "result": res})
            except Exception as exc:
                logger.exception("index_worker_exception")
                q.put({"type": "error", "message": f"内部错误: {exc}"})

        task = loop.run_in_executor(None, worker)
        start_time = time.time()
        last_yield_time = start_time

        try:
            while True:
                yielded = False
                while not q.empty():
                    msg = q.get_nowait()
                    msg_type = msg.get("type", "progress")
                    if msg_type == "error":
                        yield {"data": f"失败: {msg.get('message')}", "event": "error"}
                        return
                    elif msg_type == "done":
                        result = msg.get("result", {})
                        if result and result.get("ok"):
                            yield {"data": f"索引成功！处理了 {result.get('chunk_count', 0)} 个片段。", "event": "success"}
                        else:
                            yield {"data": f"失败: {result.get('message', '未知错误')}", "event": "error"}
                        return
                    elif msg_type == "success":
                        yield {"data": msg.get("message", "执行成功"), "event": "success"}
                        yielded = True
                    else:
                        yield {"data": msg.get("message", "执行中..."), "event": "progress"}
                        yielded = True
                        last_yield_time = time.time()
                
                if task.done():
                    if task.exception():
                        logger.error("index_task_exception", exc_info=task.exception())
                        yield {"data": "系统异常，索引任务中断", "event": "error"}
                    return
                
                now = time.time()
                if not yielded and now - last_yield_time > 2:
                    yield {"data": f"正在后台处理，已持续 {int(now - start_time)} 秒...", "event": "progress"}
                    last_yield_time = now
                elif now - last_yield_time > 15: # Heartbeat
                    yield {"data": "", "event": "heartbeat"}
                    last_yield_time = now
                
                # Extended timeout limit to 600s for large files
                if now - start_time >= 600:
                    logger.error("index_timeout seconds=%s", 600)
                    yield {"data": f"索引超时（>600s）。请检查控制台后台进度。", "event": "error"}
                    return
                
                await asyncio.sleep(0.5)
        except Exception as exc:
            logger.exception("index_sse_exception")
            yield {"data": f"SSE 异常: {exc}", "event": "error"}

    return EventSourceResponse(sse_generator())


@app.post("/api/upload", response_model=None)
async def upload_files(
    files: List[UploadFile] = File(...),
    relative_paths: List[str] = Form(...),
    analyze: bool = Form(False)
) -> Union[Dict[str, Any], JSONResponse]:
    """
    处理文件上传。支持单个/多个文件以及文件夹结构。
    relative_paths: 每一个文件对应的相对路径（由前端提供，例如 "folder/sub/file.pdf"）
    """
    try:
        # 如果不立即分析，默认归档到 docs/YYYY-MM-DD/
        archive_prefix = ""
        if not analyze:
            archive_prefix = datetime.now().strftime("%Y-%m-%d")
        
        uploaded_count = 0
        for file, rel_path in zip(files, relative_paths):
            # 强化路径清理，防止目录穿越
            # 1. 规范化路径，移除 .. 等
            safe_rel_path = os.path.normpath(rel_path).lstrip(os.sep + "./")
            
            # 安全检查：白名单后缀
            allowed_exts = {".pdf", ".docx", ".doc", ".txt", ".md", ".csv", ".html", ".htm", ".png", ".jpg", ".jpeg", ".webp", ".yml", ".yaml"}
            if not any(safe_rel_path.lower().endswith(ext) for ext in allowed_exts):
                 logger.warning(f"上传被拒：不支持的后缀 - {rel_path}")
                 continue

            if archive_prefix:
                target_path = DOCS_DIR / archive_prefix / safe_rel_path
            else:
                target_path = DOCS_DIR / safe_rel_path
            
            # 2. 二次校验：确保生成的绝对路径依然在 DOCS_DIR 范围内
            resolved_docs_dir = DOCS_DIR.resolve()
            try:
                if not target_path.resolve().is_relative_to(resolved_docs_dir):
                    logger.warning(f"检测到潜在的目录穿越攻击: {rel_path}")
                    continue
            except Exception:
                logger.warning(f"路径解析异常: {rel_path}")
                continue

            # 创建父目录
            target_path.parent.mkdir(parents=True, exist_ok=True)
            
            # 保存文件
            with target_path.open("wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
            uploaded_count += 1
            
        return {
            "ok": True, 
            "message": f"成功上传 {uploaded_count} 个项目",
            "analyze": analyze,
            "archive_path": archive_prefix if not analyze else None
        }
    except (OSError, ValueError) as e:
        logger.error(f"Upload failed: {e}")
        return JSONResponse(status_code=500, content={"ok": False, "error": str(e)})


@app.get("/api/files")
def get_files_tree() -> Dict[str, Any]:
    """返回 docs 和 skills 文件夹下的嵌套树状结构"""
    import os

    def build_tree(dir_path: Path, rel_prefix: str = "") -> List[Dict[str, Any]]:
        tree = []
        if not dir_path.exists():
            return tree
        try:
            entries = sorted(os.listdir(dir_path))
        except OSError:
            return tree
            
        for entry in entries:
            if entry.startswith("."): # 忽略隐藏文件
                continue
            full_path = dir_path / entry
            rel_path = f"{rel_prefix}/{entry}" if rel_prefix else entry
            if full_path.is_dir():
                tree.append({
                    "name": entry,
                    "type": "directory",
                    "path": rel_path,
                    "children": build_tree(full_path, rel_path)
                })
            else:
                # 使用 src.config 中定义的 SUPPORTED_EXTENSIONS 进行过滤
                from src.config import SUPPORTED_EXTENSIONS
                if entry.lower().endswith(tuple(SUPPORTED_EXTENSIONS)):
                    tree.append({
                        "name": entry,
                        "type": "file",
                        "path": rel_path
                    })
        # 排序：文件夹在前，文件在后
        tree.sort(key=lambda x: (x["type"] != "directory", x["name"].lower()))
        return tree

    return {
        "name": "NebulaVault Workspace",
        "type": "directory",
        "path": "",
        "children": [
            {
                "name": "docs",
                "type": "directory",
                "path": "docs",
                "children": build_tree(DOCS_DIR)
            },
            {
                "name": "skills",
                "type": "directory",
                "children": build_tree(SKILLS_DIR)
            }
        ]
    }


@app.get("/api/top_files")
async def get_top_files_api() -> Dict[str, Any]:
    try:
        from src.config import get_top_files
        files = get_top_files(n=4)
        return {"ok": True, "files": files}
    except OSError as e:
        logger.exception("api_top_files_error")
        return {"ok": False, "files": [], "error": str(e)}


@app.post("/api/config/switch_lang")
async def switch_lang_api(payload: Dict[str, Any]) -> Dict[str, Any]:
    lang = payload.get("lang", "zh")
    try:
        from src.config import switch_embedding_model
        changed, model = switch_embedding_model(lang)
        logger.info(f"model_switch_triggered lang={lang} changed={changed} new_model={model}")
        return {
            "ok": True, 
            "changed": changed, 
            "model": model,
            "message": "模型切换指令已发出，服务器正在重启以应用更改..." if changed else "模型已是目标语言版本，无需切换。"
        }
    except (OSError, RuntimeError) as e:
        logger.exception("api_switch_lang_error")
        return {"ok": False, "error": str(e)}


@app.get("/api/sessions")
async def get_sessions_api() -> Dict[str, Any]:
    from src.config import list_sessions
    return {"ok": True, "sessions": list_sessions()}


@app.get("/api/files/content")
async def get_file_content(path: str) -> Dict[str, Any]:
    """获取文件内容，仅限 docs 和 skills 目录"""
    from src.config import DOCS_DIR, SKILLS_DIR
    try:
        # 安全检查：防止路径穿越
        # 1. 规范化路径，移除冗余的分隔符和 ..
        clean_path = os.path.normpath(path).lstrip(os.sep + "./")
        
        # 2. 尝试解析目标文件（仅在 docs 或 skills 目录下）
        target_file_docs = (DOCS_DIR / clean_path).resolve()
        target_file_skills = (SKILLS_DIR / clean_path).resolve()
        
        resolved_docs_dir = DOCS_DIR.resolve()
        resolved_skills_dir = SKILLS_DIR.resolve()
        
        if target_file_docs.is_file() and target_file_docs.is_relative_to(resolved_docs_dir):
            target_file = target_file_docs
        elif target_file_skills.is_file() and target_file_skills.is_relative_to(resolved_skills_dir):
            target_file = target_file_skills
        else:
            return {"ok": False, "error": "非法访问或文件不存在"}

        if not target_file.exists():
            return {"ok": False, "error": "文件不存在"}

        # 读取内容
        suffix = target_file.suffix.lower()
        if suffix in ['.docx']:
            return {"ok": False, "error": "暂不支持预览该格式文件，请直接在对话中分析。"}
        
        # 如果是 PDF，返回标记让前端用 iframe 加载
        if suffix == '.pdf':
            return {"ok": True, "is_pdf": True, "filename": target_file.name, "raw_url": f"/api/files/raw?path={quote(path)}&token={API_KEY}"}

        # 如果是图片，返回 base64
        if suffix in ['.png', '.jpg', '.jpeg', '.webp']:
            import base64
            with open(target_file, "rb") as image_file:
                encoded_string = base64.b64encode(image_file.read()).decode("utf-8")
                mime_type = f"image/{suffix[1:]}"
                if suffix == '.jpg': mime_type = "image/jpeg"
                return {"ok": True, "content": f"data:{mime_type};base64,{encoded_string}", "filename": target_file.name, "is_image": True}

        content = target_file.read_text("utf-8", errors="replace")
        return {"ok": True, "content": content, "filename": target_file.name}
    except OSError as e:
        logger.exception("api_get_file_content_error")
        return {"ok": False, "error": str(e)}


@app.get("/api/files/raw", response_model=None)
async def get_raw_file(path: str) -> Union[FileResponse, JSONResponse]:
    """直接返回原始文件流 (Binary Stream)，支持 PDF, Image 预览"""
    from src.config import DOCS_DIR, SKILLS_DIR
    import mimetypes
    try:
        clean_path = os.path.normpath(path).lstrip(os.sep + "./")
        
        target_file_docs = (DOCS_DIR / clean_path).resolve()
        target_file_skills = (SKILLS_DIR / clean_path).resolve()
        
        resolved_docs_dir = DOCS_DIR.resolve()
        resolved_skills_dir = SKILLS_DIR.resolve()
        
        if target_file_docs.is_file() and target_file_docs.is_relative_to(resolved_docs_dir):
            target_file = target_file_docs
        elif target_file_skills.is_file() and target_file_skills.is_relative_to(resolved_skills_dir):
            target_file = target_file_skills
        else:
            return JSONResponse(status_code=403, content={"error": "Access denied or file not found"})

        if not target_file.exists():
            return JSONResponse(status_code=404, content={"error": "File not found"})

        mime_type, _ = mimetypes.guess_type(target_file)
        media = mime_type or "application/octet-stream"

        # Use inline disposition so PDFs/images render in iframes instead of downloading
        from starlette.responses import Response
        content_bytes = target_file.read_bytes()
        return Response(
            content=content_bytes,
            media_type=media,
            headers={
                "Content-Disposition": f'inline; filename="{target_file.name}"',
            },
        )
    except Exception as e:
        logger.exception("api_get_raw_file_error")
        return JSONResponse(status_code=500, content={"error": str(e)})


class SessionCreate(BaseModel):
    title: Optional[str] = None

@app.post("/api/sessions")
async def create_session_api(req: Optional[SessionCreate] = None) -> Dict[str, Any]:
    import uuid
    session_id = str(uuid.uuid4())
    from src.config import save_session
    title = req.title if req and req.title else "New Chat"
    data = {"id": session_id, "title": title, "history": []}
    save_session(session_id, data)
    return {"ok": True, "session_id": session_id}


def is_valid_uuid(val: str) -> bool:
    try:
        import uuid
        uuid_obj = uuid.UUID(val, version=4)
        return str(uuid_obj) == val
    except ValueError:
        return False

@app.get("/api/sessions/{session_id}")
async def get_session_detail_api(session_id: str) -> Dict[str, Any]:
    if not is_valid_uuid(session_id):
        return {"ok": False, "error": "Invalid session ID format"}
    from src.config import load_session
    data = load_session(session_id)
    if not data:
        return {"ok": False, "error": "Session not found"}
    return {"ok": True, "session": data}


@app.post("/api/sessions/{session_id}/message")
async def save_message_api(session_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    if not is_valid_uuid(session_id):
        return {"ok": False, "error": "Invalid session ID format"}
    from src.config import load_session, save_session
    data = load_session(session_id)
    if not data:
        return {"ok": False, "error": "Session not found"}
    
    msg_pair = payload.get("message_pair")
    if msg_pair:
        data["history"].append(msg_pair)
        # 自动重命名 (Auto-rename logic)
        if len(data["history"]) == 1 and data.get("title") == "New Chat":
            user_msg = msg_pair.get("user", "")
            data["title"] = (user_msg[:20] + "...") if len(user_msg) > 20 else user_msg
            
        save_session(session_id, data)
    return {"ok": True}


@app.delete("/api/sessions/{session_id}")
async def delete_session_api(session_id: str) -> Dict[str, Any]:
    if not is_valid_uuid(session_id):
        return {"ok": False, "error": "Invalid session ID format"}
    from src.config import delete_session
    ok = delete_session(session_id)
    return {"ok": ok}


@app.post("/api/sessions/{session_id}/summarize")
async def summarize_session_api(session_id: str) -> Dict[str, Any]:
    if not is_valid_uuid(session_id):
        return {"ok": False, "error": "Invalid session ID format"}
    from src.config import load_session, save_memory
    data = load_session(session_id)
    if not data or not data.get("history"):
        print(f"⚠️ [Debug] Summarize failed: No history found for session {session_id}")
        return {"ok": False, "error": "No history to summarize"}
    
    print(f"🧠 [Debug] Summarizing session {session_id}, history_len={len(data['history'])}")
    
    rag = get_rag()
    # 提炼见解
    loop = asyncio.get_running_loop()
    insight = await loop.run_in_executor(None, rag.distill_insights, data["history"])
    
    if insight:
        # 尝试找出本次会话涉及的所有文件 (Find all files mentioned)
        found_files = set()
        from src.config import list_doc_files, list_skill_files
        # 获取所有相对路径列表
        all_doc_paths = list_doc_files()
        all_skill_paths = list_skill_files()
        
        for pair in data["history"]:
            content_to_check = (pair.get("user", "") + " " + pair.get("assistant", "")).lower()
            
            # 检查文档
            for rel_path in all_doc_paths:
                filename = Path(rel_path).name
                if rel_path.lower() in content_to_check or filename.lower() in content_to_check:
                    found_files.add(rel_path)
            
            # 检查技能
            for rel_path in all_skill_paths:
                filename = Path(rel_path).name
                if rel_path.lower() in content_to_check or filename.lower() in content_to_check:
                    found_files.add(rel_path)
        
        if not found_files:
            print(f"⚠️ [Debug] Summarize failed: Could not identify files in history.")
            return {"ok": False, "error": "Could not identify target files in this session history."}

        print(f"✅ [Debug] Summarize identified files: {found_files}")

        saved_count = 0
        for rel_path in found_files:
            save_memory(rel_path, insight)
            logger.info("memory_saved rel_path=%s", rel_path)
            saved_count += 1
            
        return {"ok": True, "insight": insight, "files": list(found_files)}
    
    return {"ok": False, "error": "Summarization failed"}


@app.get("/api/logs/stream")
async def stream_logs() -> EventSourceResponse:
    async def log_generator() -> AsyncGenerator[Dict[str, Any], None]:
        # Start by sending the last 50 lines
        if SERVER_LOG.exists():
            with open(SERVER_LOG, "r", encoding="utf-8") as f:
                lines = f.readlines()
                for line in lines[-50:]:
                    yield {"data": line.strip()}
        
        # Then tail the file
        last_pos = SERVER_LOG.stat().st_size if SERVER_LOG.exists() else 0
        while True:
            if not SERVER_LOG.exists():
                await asyncio.sleep(1)
                continue
            
            curr_size = SERVER_LOG.stat().st_size
            if curr_size < last_pos: # Log rotated or cleared
                last_pos = 0
            
            if curr_size > last_pos:
                with open(SERVER_LOG, "r", encoding="utf-8") as f:
                    f.seek(last_pos)
                    new_lines = f.readlines()
                    last_pos = f.tell()
                    for line in new_lines:
                        yield {"data": line.strip()}
            else:
                # SSE Heartbeat
                yield {"data": "", "comment": "heartbeat"}
            
            await asyncio.sleep(1)

    return EventSourceResponse(log_generator())


class QueryRequest(BaseModel):
    query: str
    category: Optional[str] = None
    history: List[Dict[str, Any]] = Field(default_factory=list)


@app.post("/api/query")
async def query_rag(req: QueryRequest) -> EventSourceResponse:
    async def sse_generator() -> AsyncGenerator[Dict[str, Any], None]:
        logger.info("query_start query=%r category=%r history_len=%s", req.query, req.category, len(req.history or []))
        if not req.query.strip():
            logger.info("query_reject_empty")
            yield {
                "data": json.dumps({"error": "请输入问题。"}, ensure_ascii=False),
                "event": "error",
            }
            return

        rag = get_rag()
        loop = asyncio.get_running_loop()
        generator = rag.stream_query(req.query, req.category, req.history)

        try:
            event_count = 0
            while True:
                item = await loop.run_in_executor(None, next, generator, None)
                if item is None:
                    break
                event_count += 1
                logger.info("query_event type=%s", item.get("type"))
                if item["type"] == "token":
                    yield {
                        "data": json.dumps({"text": item["data"]}, ensure_ascii=False),
                        "event": "token",
                    }
                elif item["type"] == "status":
                    yield {
                        "data": json.dumps({"status": item["data"]}, ensure_ascii=False),
                        "event": "status",
                    }
                elif item["type"] == "sources":
                    yield {
                        "data": json.dumps(item["data"], ensure_ascii=False),
                        "event": "sources",
                    }
                elif item["type"] == "error":
                    yield {
                        "data": json.dumps({"error": item["data"]}, ensure_ascii=False),
                        "event": "error",
                    }
                
                # SSE Heartbeat for long model generation
                if event_count > 0 and event_count % 15 == 0:
                     yield {"data": "", "event": "heartbeat"}
            
            logger.info("query_done events=%s", event_count)
        except (Exception, OSError) as exc:
            logger.exception("query_exception")
            message = f"异常: {exc}"
            lowered = str(exc).lower()
            if "connection refused" in lowered or "[errno 61]" in lowered:
                from src.config import OLLAMA_HOST
                message = f"无法连接 Ollama 服务（{OLLAMA_HOST}）。请先启动 Ollama 后重试。"
            yield {
                "data": json.dumps({"error": message}, ensure_ascii=False),
                "event": "error",
            }
            return # Stop generator on exception

    return EventSourceResponse(sse_generator())


if __name__ == "__main__":
    print("\n🚀 启动星澜知库 NebulaVault...")
    print("访问地址: http://127.0.0.1:8000\n")
    import uvicorn
    # Bind to 127.0.0.1 as requested by security audit to prevent public exposure
    uvicorn.run(
        "main:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
        reload_excludes=["chroma_db/*", "*.sqlite3", "venv/*", ".venv*/*", "__pycache__/*", "pdfs/*", "docs/*"],
    )

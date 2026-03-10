import os
import re
import json
import time
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional
from urllib.parse import quote
BASE_DIR = Path(__file__).resolve().parent.parent
LEGACY_PDFS_DIR = BASE_DIR / "pdfs"


def _resolve_project_path(env_name: str, default_dirname: str) -> Path:
    raw_value: Optional[str] = os.getenv(env_name)
    if not raw_value:
        return BASE_DIR / default_dirname

    path: Path = Path(raw_value).expanduser()
    if not path.is_absolute():
        path = BASE_DIR / path
    return path


DOCS_DIR = _resolve_project_path("RAG_DOCS_DIR", "docs")
SKILLS_DIR = BASE_DIR / "skills"
CHROMA_DIR = _resolve_project_path("RAG_CHROMA_DIR", "chroma_db")
MANIFEST_FILE = CHROMA_DIR / "index_manifest.json"
SESSIONS_DIR = BASE_DIR / "sessions"
MEMORY_DIR = BASE_DIR / "memory"

# --- Embedding 模型配置 ---
# 中文推荐: BAAI/bge-large-zh-v1.5
# 英文推荐: BAAI/bge-large-en-v1.5 或 intfloat/e5-large-v2
# 多语言推荐: intfloat/multilingual-e5-large
_embed_model = os.getenv("RAG_EMBED_MODEL", "").strip()
EMBED_MODEL = _embed_model if _embed_model else "BAAI/bge-large-zh-v1.5"

_llm_model = os.getenv("RAG_LLM_MODEL", "").strip()
LLM_MODEL = _llm_model if _llm_model else "qwen3:8b"

_ollama_host = os.getenv("OLLAMA_HOST", "").strip()
OLLAMA_HOST = _ollama_host if _ollama_host else "http://127.0.0.1:11434"

SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".txt", ".md", ".csv", ".html", ".htm", ".yml", ".yaml", ".png", ".jpg", ".jpeg", ".webp"}
USAGE_FILE = BASE_DIR / "file_usage.json"



def ensure_dirs() -> None:
    if not DOCS_DIR.exists() and LEGACY_PDFS_DIR.exists():
        print(f"📁 检测到旧目录 pdfs/，自动迁移为 {DOCS_DIR}")
        LEGACY_PDFS_DIR.rename(DOCS_DIR)
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    SKILLS_DIR.mkdir(parents=True, exist_ok=True)
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)


def list_doc_files() -> List[str]:
    ensure_dirs()
    files: List[str] = []
    # 扫描 docs 目录
    for entry in DOCS_DIR.rglob('*'):
        if entry.is_file() and entry.suffix.lower() in SUPPORTED_EXTENSIONS:
            files.append(str(entry.relative_to(DOCS_DIR)))
    return sorted(files)


def list_skill_files() -> List[str]:
    ensure_dirs()
    skills: List[str] = []
    # 扫描 skills 目录，支持所有扩展名 (Scan skills dir, support all extensions)
    for entry in SKILLS_DIR.rglob('*'):
        if entry.is_file() and entry.suffix.lower() in SUPPORTED_EXTENSIONS:
            skills.append(str(entry.relative_to(SKILLS_DIR)))
    return sorted(skills)


def has_persisted_index() -> bool:
    return CHROMA_DIR.exists() and any(CHROMA_DIR.iterdir())


def get_runtime_status() -> Dict[str, Any]:
    return {
        "doc_count": len(list_doc_files()),
        "has_index": has_persisted_index(),
        "docs_dir": str(DOCS_DIR.resolve()),
        "chroma_dir": str(CHROMA_DIR.resolve()),
        "llm_model": LLM_MODEL,
        "embed_model": EMBED_MODEL,
        "supported_formats": sorted(SUPPORTED_EXTENSIONS),
    }

import json

def record_file_usage(filenames: List[str]) -> None:
    try:
        usage: Dict[str, int] = {}
        if USAGE_FILE.exists():
            usage = json.loads(USAGE_FILE.read_text("utf-8"))
        for f in filenames:
            if not f: continue
            usage[f] = usage.get(f, 0) + 1
        USAGE_FILE.write_text(json.dumps(usage, ensure_ascii=False), "utf-8")
    except (OSError, json.JSONDecodeError) as e:
        print(f"Warning: Failed to record file usage - {e}")

def get_top_files(n: int = 4) -> List[str]:
    files = list_doc_files()
    if not files:
        return []
    try:
        if USAGE_FILE.exists():
            usage = json.loads(USAGE_FILE.read_text("utf-8"))
            # Sort files combining usage count (descending) and alphabetical (ascending)
            files.sort(key=lambda f: (-usage.get(f, 0), f))
    except (OSError, json.JSONDecodeError):
        pass
    return files[:n]


def switch_embedding_model(lang: str) -> Tuple[bool, str]:
    """根据语言切换 Embedding 模型，并直接修改配置文件以触发 uvicorn reload"""
    target_model = "BAAI/bge-large-zh-v1.5" if lang == "zh" else "BAAI/bge-large-en-v1.5"

    try:
        config_path = Path(__file__).resolve()
        content = config_path.read_text("utf-8")
        
        # 查找 EMBED_MODEL = os.getenv("RAG_EMBED_MODEL", "BAAI/bge-large-zh-v1.5")
        # 并替换其中的默认值
        new_content = re.sub(
            r'(EMBED_MODEL\s*=\s*_embed_model\s*if\s*_embed_model\s*else\s*")[^"]+(")',
            rf'\1{target_model}\2',
            content
        )
        
        if new_content != content:
            config_path.write_text(new_content, "utf-8")
            return True, target_model
    except OSError:
        pass
    return False, EMBED_MODEL


# --- 会话管理 (Session Management) ---

def list_sessions() -> List[Dict[str, Any]]:
    """返回所有会话的元数据列表"""
    ensure_dirs()
    sessions: List[Dict[str, Any]] = []
    for f in SESSIONS_DIR.glob("*.json"):
        try:
            data = json.loads(f.read_text("utf-8"))
            sessions.append({
                "id": f.stem,
                "title": data.get("title", "未命名会话"),
                "updated_at": f.stat().st_mtime
            })
        except (OSError, json.JSONDecodeError):
            continue
    # 按时间降序排序
    sessions.sort(key=lambda x: x["updated_at"], reverse=True)
    return sessions

def load_session(session_id: str) -> Optional[Dict[str, Any]]:
    """根据 ID 加载完整会话历史"""
    if not re.match(r'^[0-9a-f-]{36}$', session_id):
        return None
    path = SESSIONS_DIR / f"{session_id}.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text("utf-8"))
    except (OSError, json.JSONDecodeError):
        return None

def save_session(session_id: str, data: Dict[str, Any]) -> bool:
    """保存会话数据"""
    # 验证 session_id 是否为合法 UUID，防止文件名注入
    if not re.match(r'^[0-9a-f-]{36}$', session_id):
        return False
    ensure_dirs()
    path = SESSIONS_DIR / f"{session_id}.json"
    
    try:
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), "utf-8")
        return True
    except OSError:
        return False

def delete_session(session_id: str) -> bool:
    """删除会话"""
    if not re.match(r'^[0-9a-f-]{36}$', session_id):
        return False
    path = SESSIONS_DIR / f"{session_id}.json"
    try:
        if path.exists():
            path.unlink()
            return True
    except OSError:
        pass
    return False


# --- 知识记忆 (Knowledge Memory) ---

def _memory_key(filename: str) -> str:
    normalized = str(Path(filename).as_posix()).strip().lstrip("./")
    if not normalized:
        return ""
    return quote(normalized, safe="")


def save_memory(filename: str, insight: str) -> bool:
    """保存针对特定文件的见解/总结"""
    ensure_dirs()
    key = _memory_key(filename)
    if not key:
         return False

    path = MEMORY_DIR / f"{key}.json"
    data = {
        "filename": filename,
        "insight": insight,
        "updated_at": time.time()
    }
    
    try:
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), "utf-8")
        return True
    except OSError:
        return False

def load_memory(filename: str) -> Optional[Dict[str, Any]]:
    """加载特定文件的见解"""
    key = _memory_key(filename)
    candidates: List[Path] = []
    if key:
        candidates.append(MEMORY_DIR / f"{key}.json")
    # Backward compatibility for legacy basename-only memory files
    candidates.append(MEMORY_DIR / f"{Path(filename).name}.json")

    for path in candidates:
        if not path.exists():
            continue
        try:
            return json.loads(path.read_text("utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
    return None

def list_memories() -> List[str]:
    """返回所有有记忆的文件列表"""
    ensure_dirs()
    return [f.stem for f in MEMORY_DIR.glob("*.json")]

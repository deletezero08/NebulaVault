import os
import shutil
import time
import json
import logging
from typing import Dict, List, Any, Optional, Tuple

import chromadb
from langchain_community.document_loaders import (
    CSVLoader,
    Docx2txtLoader,
    PyMuPDFLoader,
    TextLoader,
    UnstructuredHTMLLoader,
)
from langchain_community.vectorstores import Chroma
from langchain_text_splitters import RecursiveCharacterTextSplitter

from .config import CHROMA_DIR, DOCS_DIR, SKILLS_DIR, MANIFEST_FILE, ensure_dirs, list_doc_files, list_skill_files

import threading
logger = logging.getLogger("rag_core")

# Global lock for indexing process
indexing_lock = threading.Lock()

class PytesseractImageLoader:
    def __init__(self, file_path: str) -> None:
        import traceback
        self.file_path = file_path
        self.logger = logging.getLogger("rag_core")

    def load(self) -> List[Any]:
        from langchain_core.documents import Document
        try:
            from PIL import Image
            import pytesseract
            
            img = Image.open(self.file_path)
            # 尝试获取支持的语言，如果支持中文则使用中文+英文，否则回退到英文
            try:
                available_langs = pytesseract.get_languages()
                lang = "chi_sim+eng" if "chi_sim" in available_langs else "eng"
            except Exception:
                lang = "chi_sim+eng" # 默认尝试中文+英文
                
            text = pytesseract.image_to_string(img, lang=lang)
            return [Document(page_content=text, metadata={"source": self.file_path})]
        except Exception as e:
            self.logger.warning(f"Failed to OCR image {self.file_path}: {e}")
            import traceback
            traceback.print_exc()
            return []

LOADER_MAP = {
    ".pdf": PyMuPDFLoader,
    ".docx": Docx2txtLoader,
    ".txt": lambda p: TextLoader(p, encoding="utf-8"),
    ".md": lambda p: TextLoader(p, encoding="utf-8"),
    ".yml": lambda p: TextLoader(p, encoding="utf-8"),
    ".yaml": lambda p: TextLoader(p, encoding="utf-8"),
    ".csv": lambda p: CSVLoader(p, encoding="utf-8"),
    ".html": UnstructuredHTMLLoader,
    ".htm": UnstructuredHTMLLoader,
    ".png": PytesseractImageLoader,
    ".jpg": PytesseractImageLoader,
    ".jpeg": PytesseractImageLoader,
    ".webp": PytesseractImageLoader,
}

FILE_CATEGORY_MAP = {
    ".pdf": "pdf",
    ".docx": "word_text",
    ".doc": "word_text",
    ".txt": "word_text",
    ".md": "markdown",
    ".yml": "markdown",
    ".yaml": "markdown",
    ".csv": "data_web",
    ".html": "data_web",
    ".htm": "data_web",
    ".png": "image",
    ".jpg": "image",
    ".jpeg": "image",
    ".webp": "image",
}


def _load_manifest() -> Dict[str, float]:
    if not MANIFEST_FILE.exists():
        return {}
    try:
        with open(MANIFEST_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        logger.warning(f"Failed to load manifest: {e}")
        return {}


def _save_manifest(manifest: Dict[str, float]) -> None:
    CHROMA_DIR.mkdir(parents=True, exist_ok=True)
    try:
        with open(MANIFEST_FILE, "w", encoding="utf-8") as f:
            json.dump(manifest, f, ensure_ascii=False, indent=2)
    except OSError as e:
        logger.error(f"Failed to save manifest: {e}")


def _clear_chroma_dir() -> None:
    if not CHROMA_DIR.exists():
        return

    print("🗑️ 清除旧索引，防止数据重复...")
    try:
        for root, dirs, files in os.walk(CHROMA_DIR):
            for name in files:
                os.chmod(os.path.join(root, name), 0o600)
            for name in dirs:
                os.chmod(os.path.join(root, name), 0o700)
        os.chmod(CHROMA_DIR, 0o700)
        shutil.rmtree(CHROMA_DIR)
    except OSError:
        backup_dir = f"{CHROMA_DIR}.bak.{int(time.time())}"
        print(f"⚠️ 无法删除旧索引，已移动到: {backup_dir}")
        shutil.move(CHROMA_DIR, backup_dir)

    try:
        import chromadb.api.client
        if hasattr(chromadb.api.client, "SharedSystemClient"):
            chromadb.api.client.SharedSystemClient.clear_system_cache()
    except Exception as e:
        logger.warning(f"Failed to clear chroma system cache: {e}")


def reset_index_storage() -> None:
    _clear_chroma_dir()
    CHROMA_DIR.mkdir(parents=True, exist_ok=True)


_chroma_client = None

def load_persisted_db(embeddings: Any) -> Chroma:
    global _chroma_client
    if _chroma_client is None:
        _chroma_client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    return Chroma(
        persist_directory=str(CHROMA_DIR),
        embedding_function=embeddings,
        client=_chroma_client,
    )


def _protect_tables(docs: List[Any]) -> List[Any]:
    """合并被拆散的表格行，防止表格跨 chunk 导致语义丢失。"""
    if not docs:
        return docs
    
    merged = []
    buffer = None
    
    for doc in docs:
        text = doc.page_content
        # 简单判断：如果 chunk 以 | 开头或者包含多行 |...|，则认为是表格片段
        lines = text.strip().split("\n")
        is_table_fragment = any(
            line.strip().startswith("|") and line.strip().endswith("|")
            for line in lines
        )
        
        if is_table_fragment and buffer is not None:
            # 把当前表格片段追加到 buffer 里
            from langchain_core.documents import Document as _Doc
            buffer = _Doc(
                page_content=buffer.page_content + "\n" + text,
                metadata=buffer.metadata,
            )
        else:
            if buffer is not None:
                merged.append(buffer)
            buffer = doc
    
    if buffer is not None:
        merged.append(buffer)
    
    return merged


def rebuild_index(embeddings: Any, progress_callback: Optional[Any] = None) -> Tuple[Optional[Any], Dict[str, Any]]:
    if not indexing_lock.acquire(blocking=False):
        logger.warning("Another indexing process is already running.")
        if progress_callback: progress_callback({"type": "error", "message": "🚫 索引正在由其他进程构建，请稍后再试"})
        return None, {"ok": False, "error": "知识库正在构建中，请稍后再试。"}
    try:
        return _do_rebuild_index(embeddings, progress_callback)
    finally:
        indexing_lock.release()

def _do_rebuild_index(embeddings: Any, progress_callback: Optional[Any] = None) -> Tuple[Optional[Any], Dict[str, Any]]:
    def notify(msg: str, msg_type: str = "progress") -> None:
        if progress_callback:
            progress_callback({"type": msg_type, "message": msg})

    print("📚 检查增量索引状态...")
    notify("开始检查项目目录...")
    logger.info("index_stage=start")
    ensure_dirs()

    # 1. 扫描磁盘上的文件并获取修改时间 (Docs + Skills)
    current_files = {}
    
    # Docs
    doc_files = list_doc_files()
    for filename in doc_files:
        filepath = DOCS_DIR / filename
        current_files[f"docs/{filename}"] = filepath.stat().st_mtime

    # Skills
    skill_files = list_skill_files()
    for filename in skill_files:
        filepath = SKILLS_DIR / filename
        current_files[f"skills/{filename}"] = filepath.stat().st_mtime

    # 2. 加载旧的 manifest 并对比差异
    old_manifest = _load_manifest()
    
    to_index = []  # 需要重新解析并索引的文件名列表
    to_delete = [] # 需要从向量库中删除的文件名列表 (物理删除或被修改)
    
    # 检测删除的文件
    for filename in old_manifest.keys():
        if filename not in current_files:
            to_delete.append(filename)
            
    # 检测新增或修改的文件
    for filename, mtime in current_files.items():
        if filename not in old_manifest:
            to_index.append(filename)
        elif abs(old_manifest[filename] - mtime) > 1.0: # 允许 1s 误差
            to_index.append(filename)
            to_delete.append(filename) # 修改过的文件也需要先删旧的

    if not to_index and not to_delete:
        print("   ✅ 已经是最新，跳过构建。")
        notify("知识库已是最新状态，无需更新。", "success")
        logger.info("index_stage=skip_no_changes")
        return load_persisted_db(embeddings), {
            "ok": True,
            "message": "索引已是最新，无需更新。",
            "doc_files": doc_files,
            "chunk_count": -1, # 表示跳过
        }

    print(f"   🔄 增量更新: 待处理 {len(to_index)} 个文件, 待移除 {len(to_delete)} 个失效项")
    notify(f"检测到变更：需更新 {len(to_index)} 个文件，移除 {len(to_delete)} 个过期项...")
    logger.info("index_delta to_index=%s to_delete=%s", len(to_index), len(to_delete))

    # 3. 初始化/加载 Chroma 数据库
    db = load_persisted_db(embeddings)

    # 4. 执行删除操作 (如果是修改或删除)
    if to_delete:
        for file_key in to_delete:
            if file_key.startswith("docs/"):
                source_path = str(DOCS_DIR / file_key[5:])
            else:
                source_path = str(SKILLS_DIR / file_key[7:])
                
            print(f"   🗑️ 移除旧记录: {file_key}")
            # 注意：Chroma 的 delete 需要传入精确匹配的 filter
            try:
                # 兼容性修复：部分版本 Chroma 可能需要元数据过滤精确匹配
                db.delete(where={"source": {"$eq": source_path}})
            except Exception:
                try:
                    db.delete(where={"source": source_path})
                except Exception as e:
                    logger.warning(f"Failed to delete {file_key} from chroma: {e}")

    # 5. 解析并切分新/修改的文件
    if not to_index:
        # 如果只有删除操作
        new_manifest = {k: v for k, v in current_files.items()}
        _save_manifest(new_manifest)
        notify("索引清理完成！", "success")
        return db, {
            "ok": True,
            "message": "索引清理完成",
            "doc_files": doc_files,
            "chunk_count": 0,
        }

    documents = []
    failed_files = []
    total_to_index = len(to_index)
    for i, file_key in enumerate(to_index, 1):
        if file_key.startswith("docs/"):
            filename = file_key[5:]
            filepath = DOCS_DIR / filename
            is_skill = False
        else:
            filename = file_key[7:]
            filepath = SKILLS_DIR / filename
            is_skill = True
            
        ext = filepath.suffix.lower()
        print(f"   📄 解析: {filename} {'(Skill)' if is_skill else ''}")
        notify(f"正在解析新文档 ({i}/{total_to_index}): {filename}...")
        try:
            loader_factory = LOADER_MAP.get(ext)
            if not loader_factory:
                continue
            loader = loader_factory(str(filepath))
            loaded_docs = loader.load()
            
            file_category = "skill" if is_skill else FILE_CATEGORY_MAP.get(ext, "all")
            mtime_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(current_files[file_key]))
            
            for doc in loaded_docs:
                doc.metadata["source"] = str(filepath)
                doc.metadata["file_ext"] = ext.lstrip(".")
                doc.metadata["file_category"] = file_category
                doc.metadata["file_mtime_str"] = mtime_str
                doc.metadata["is_skill"] = is_skill
                
            documents.extend(loaded_docs)
        except Exception as exc:
            print(f"   ⚠️ 解析失败 {filename}: {exc}")
            failed_files.append(filename)

    if not documents:
        # 可能解析全失败
        new_manifest = {k: v for k, v in current_files.items()}
        _save_manifest(new_manifest)
        return db, {
            "ok": True,
            "message": "更新完成（部分文件解析失败）",
            "doc_files": doc_files,
            "chunk_count": 0,
        }

    # ──────────────── 文本切分逻辑 (复用之前的 docs_by_strategy 逻辑) ────────────────
    docs_by_strategy = {"pdf_doc": [], "markdown": [], "code_config": [], "data": [], "other": []}
    for doc in documents:
        ext = doc.metadata.get("file_ext", "")
        if ext in ("pdf", "docx", "doc", "png", "jpg", "jpeg", "webp"):
            docs_by_strategy["pdf_doc"].append(doc)
        elif ext in ("md",):
            docs_by_strategy["markdown"].append(doc)
        elif ext in ("yml", "yaml", "txt"):
            docs_by_strategy["code_config"].append(doc)
        elif ext in ("csv", "html", "htm"):
            docs_by_strategy["data"].append(doc)
        else:
            docs_by_strategy["other"].append(doc)

    texts = []
    if docs_by_strategy["pdf_doc"]:
        # 增大 chunk_size 以减少向量化次数，提升索引速度
        pdf_splitter = RecursiveCharacterTextSplitter(chunk_size=2500, chunk_overlap=300, separators=["\n\n", "\n", "。", "！", "？", "；", "，", " ", ""])
        split_docs = _protect_tables(pdf_splitter.split_documents(docs_by_strategy["pdf_doc"]))
        texts.extend(split_docs)

    if docs_by_strategy["markdown"]:
        try:
            from langchain_text_splitters import MarkdownHeaderTextSplitter
            hd_splitter = MarkdownHeaderTextSplitter(headers_to_split_on=[("#","h1"),("##","h2"),("###","h3")])
            fb_splitter = RecursiveCharacterTextSplitter(chunk_size=2000, chunk_overlap=250)
            for doc in docs_by_strategy["markdown"]:
                chunks = hd_splitter.split_text(doc.page_content)
                for c in chunks: c.metadata = {**doc.metadata, **c.metadata}
                texts.extend(fb_splitter.split_documents(chunks))
        except ImportError:
            md_splitter = RecursiveCharacterTextSplitter(chunk_size=2000, chunk_overlap=250, separators=["\n## ", "\n### ", "\n\n", "\n", "。", " ", ""])
            texts.extend(md_splitter.split_documents(docs_by_strategy["markdown"]))

    if docs_by_strategy["code_config"]:
        code_splitter = RecursiveCharacterTextSplitter(chunk_size=600, chunk_overlap=100, separators=["\n\n", "\n", " ", ""])
        texts.extend(code_splitter.split_documents(docs_by_strategy["code_config"]))

    if docs_by_strategy["data"]:
        data_splitter = RecursiveCharacterTextSplitter(chunk_size=1400, chunk_overlap=180, separators=["\n\n", "\n", "。", "，", " ", ""])
        texts.extend(data_splitter.split_documents(docs_by_strategy["data"]))

    if docs_strategy_other := docs_by_strategy.get("other"):
        default_splitter = RecursiveCharacterTextSplitter(chunk_size=1500, chunk_overlap=200, separators=["\n\n", "\n", "。", " ", ""])
        texts.extend(default_splitter.split_documents(docs_strategy_other))

    # --- 技能文件特殊处理：保持原子性 (Skills: Keep Atomic) ---
    # 我们遍历所有解析出的原始技能文档，如果不长，就直接作为整块存入
    skills_to_add = []
    for doc in documents:
        if doc.metadata.get("is_skill"):
            # 如果技能文件内容小于 4000 字符，直接作为一个 chunk，不切分
            if len(doc.page_content) < 4000:
                skills_to_add.append(doc)
            else:
                # 如果太长，还是走默认切分逻辑
                skill_splitter = RecursiveCharacterTextSplitter(chunk_size=3000, chunk_overlap=400)
                skills_to_add.extend(skill_splitter.split_documents([doc]))
    
    # 将技能加入总列表
    texts.extend(skills_to_add)

    # 5.5 过滤非法输出：确保所有 chunk 的 content 都是有效字符串 (防止 pydantic 验证失败)
    valid_texts = []
    for t in texts:
        if t.page_content is not None and isinstance(t.page_content, str) and t.page_content.strip():
            valid_texts.append(t)
    
    if not valid_texts:
        print("   ⚠️ 警告：切分后没有产生有效的文本片段。")
        new_manifest = {k: v for k, v in current_files.items()}
        _save_manifest(new_manifest)
        return db, {
            "ok": True,
            "message": "更新完成（未产生有效文本片段）",
            "doc_files": doc_files,
            "chunk_count": 0,
        }

    # 6. 将新 Chunk 存入向量数据库 (Append)
    print(f"💾 存入向量库 ({len(valid_texts)} 个新片段)...")
    notify(f"正在向量化并追加 {len(valid_texts)} 个新片段...")
    db.add_documents(valid_texts)
    
    # 7. 更新并保存 manifest
    new_manifest = {k: v for k, v in current_files.items()}
    _save_manifest(new_manifest)

    print("   ✅ 增量索引更新完成！")
    notify("增量索引更新完毕！", "success")
    logger.info("index_stage=incremental_done added_chunks=%s", len(texts))

    return db, {
        "ok": True,
        "message": f"索引已更新（新增 {len(texts)} 个片段）",
        "doc_files": doc_files,
        "chunk_count": len(texts),
    }

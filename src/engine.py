import sys
import os
import time
import asyncio
import logging
import json
import re
from typing import Optional, Dict, Any, List, Union, Tuple, Iterator, AsyncGenerator

logger = logging.getLogger("rag_core")

if sys.version_info >= (3, 14):
    raise RuntimeError(
        "当前项目依赖的 chromadb 在 Python 3.14 下不兼容。"
        "请改用 Python 3.13 运行，例如执行 ./start_gui.command。"
    )

import torch
from langchain_core.documents import Document
from langchain_core.prompts import PromptTemplate
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_ollama import OllamaLLM
from .config import (
    DOCS_DIR,
    EMBED_MODEL,
    LLM_MODEL,
    OLLAMA_HOST,
    SKILLS_DIR,
    ensure_dirs,
    get_runtime_status,
    has_persisted_index,
    list_doc_files,
    list_skill_files,
)
from .indexer import LOADER_MAP, load_persisted_db, rebuild_index, reset_index_storage
from .retriever import build_qa_chain, build_retriever, extract_sources

logger = logging.getLogger("rag_core")


class LocalRAG:
    def __init__(self) -> None:
        print("🚀 初始化星澜知库 NebulaVault...")
        self.embeddings: Optional[HuggingFaceEmbeddings] = None
        self.llm: Optional[OllamaLLM] = None
        self.db: Optional[Any] = None
        self.qa: Optional[Any] = None
        self.retriever: Optional[Any] = None
        self._runtime_initialized: bool = False

        prompt_template = """你是一个专业的中文知识库问答助手。请仔细阅读以下参考资料和对话历史，然后据此回答用户的问题。

当前系统时间: {current_time}

规则：
1. 优先使用参考资料中的原文信息，并结合之前的对话上下文进行理解。
2. 如果参考资料中没有相关内容，请明确说明"根据提供的文档，我无法找到相关信息"。
3. 回答时尽量标注信息来源（如"根据第X页..."）。
4. 如果问题涉及时间线、最新文件或对比，请务必参考各个【参考资料】的修改时间与【当前系统时间】。
5. 如果问题涉及多个文档，请先在内心进行综合分析和信息梳理，再给出结构化的结论。
6. 【关键规则】如果用户的问题是要求“分析”、“翻译”、“总结”某个具体文件（如“分析 rag 下的第一个 pdf”），说明这就是一个指令任务。请直接将下面给出的【参考资料】视作用户所指的文件内容，并对其执行翻译或总结任务！不要死板地在内容里搜索“第一个pdf”这样的字眼。
7. 不要凭空捏造，只基于参考资料和历史上下文作答。
8. 输出请使用清晰的 Markdown 格式（使用标题、列表或表格让信息易读）。

{skills}
{global_memory}
【历史对话记录】（如果没有则忽略）:
{history}

【参考资料】:
{context}

用户问题: {question}

你的回答:"""
        self.prompt_zh = PromptTemplate(
            template=prompt_template,
            input_variables=["history", "context", "question", "current_time", "skills", "global_memory"],
        )
        
        prompt_template_en = """You are a professional RAG (Retrieval-Augmented Generation) assistant. document analysis. Please read the following reference materials and conversation history carefully, then answer the user's question.

Current System Time: {current_time}

Rules:
1. Prioritize information from the reference materials and use conversation context.
2. If the answer is not in the references, state "Based on the provided documents, I cannot find relevant information."
3. Cite sources (e.g., "According to page X...").
4. For timeline or comparison questions, refer to file modification times vs Current System Time.
5. If the user asks to "analyze", "translate", or "summarize" a specific file (e.g., "analyze the first pdf in rag/"), treat the provided 【Reference Materials】 as that file's content and perform the task. Do not literally search for "first pdf".
6. Do not hallucinate. Stay grounded in the references and context.
7. Use clear Markdown (headers, lists, or tables).

{skills}
{global_memory}
【Conversation History】 (Ignore if empty):
{history}

【Reference Materials】:
{context}

User Question: {question}

Your Answer (Please reply in English):"""
        self.prompt_en = PromptTemplate(
            template=prompt_template_en,
            input_variables=["history", "context", "question", "current_time", "skills", "global_memory"],
        )
        
        # Default prompt
        self.current_prompt: PromptTemplate = self.prompt_zh if "zh" in EMBED_MODEL.lower() else self.prompt_en

        if has_persisted_index():
            self.load_indexed_db()

    def _ensure_runtime(self) -> None:
        if self._runtime_initialized:
            return
        if self.embeddings is None:
            device = "cuda" if torch.cuda.is_available() else "mps" if torch.backends.mps.is_available() else "cpu"
            print(f"📥 加载 Embedding 模型 ({device} 加速): {EMBED_MODEL}")
            self.embeddings = HuggingFaceEmbeddings(
                model_name=EMBED_MODEL,
                model_kwargs={"device": device},
                encode_kwargs={
                    "normalize_embeddings": True,
                    "batch_size": 64
                },
            )

        if self.llm is None:
            import httpx
            print(f"🧠 唤醒本地大模型: {LLM_MODEL}")
            # 使用 httpx.Client 开启连接池支持
            self._http_client = httpx.Client(timeout=120.0)
            self.llm = OllamaLLM(
                model=LLM_MODEL, 
                temperature=0.1,
                base_url=OLLAMA_HOST
            )
        self._runtime_initialized = True

    def list_doc_files(self) -> List[str]:
        return list_doc_files()

    def list_skill_files(self) -> List[str]:
        return list_skill_files()

    @staticmethod
    def _ensure_dirs() -> None:
        ensure_dirs()

    def get_status(self) -> Dict[str, Any]:
        status = get_runtime_status()
        status["has_index"] = self.db is not None or status["has_index"]
        return status

    def index_docs(self, progress_callback: Optional[Any] = None) -> Dict[str, Any]:
        if progress_callback: progress_callback({"type": "progress", "message": "检查并加载向量模型..."})
        self._ensure_runtime()
        ensure_dirs()
        
        db, result = rebuild_index(self.embeddings, progress_callback=progress_callback)
        if not result["ok"]:
            return result
        
        # 仅在有变动或初始构建时更新
        if db:
            self.db = db
            self._build_qa_chain()
        return result

    def load_indexed_db(self) -> bool:
        if not has_persisted_index():
            return False

        print("📂 尝试加载已有知识库...")
        try:
            self._ensure_runtime()
            self.db = load_persisted_db(self.embeddings)
            self._build_qa_chain()
            print("   ✅ 知识库挂载成功！")
            return True
        except (ValueError, OSError, RuntimeError) as exc:
            print(f"   ⚠️ 加载已有知识库失败: {exc}")
            if "no such table: collections" in str(exc).lower():
                print("   ⚠️ 检测到损坏的 Chroma 索引，正在自动重置索引目录...")
                logger.warning("corrupt_chroma_detected_resetting_storage")
                try:
                    reset_index_storage()
                except OSError as reset_exc:
                    logger.exception("failed_to_reset_corrupt_chroma: %s", reset_exc)
            self.db = None
            self.qa = None
            self.retriever = None
            return False

    def _build_qa_chain(self) -> None:
        if self.db is None:
            self.qa = None
            self.retriever = None
            return

        print("🔍 构建检索器 (Hybrid Search)...")
        self.retriever = build_retriever(self.db)
        # 动态选择 Prompt
        self.current_prompt = self.prompt_zh if "zh" in EMBED_MODEL.lower() else self.prompt_en
        self.qa = build_qa_chain(self.llm, self.retriever, self.current_prompt)

    def _get_category_documents(self, category: Optional[str]) -> Optional[List[Document]]:
        if self.db is None or category in (None, "", "all"):
            return None

        db_data = self.db.get(where={"file_category": category})
        documents: List[Document] = []
        if db_data and db_data.get("documents"):
            for index, text in enumerate(db_data["documents"]):
                metadata = db_data["metadatas"][index] if db_data.get("metadatas") else {}
                documents.append(Document(page_content=text, metadata=metadata))
        return documents

    def _is_simple_query(self, question: str) -> bool:
        """检测是否为不需要检索知识库的简单/寒暄类问题。"""
        # 常见寒暄语、自我介绍问题、单纯的礼貌用语
        simple_patterns = [
            r"^(你好|哈喽|hi|hello|hey|早上好|中午好|中[午晚]好|下[午晚]好)$",
            r"^(你是谁|你叫什么|你的名字|你是什么)$",
            r"^(谢谢|感谢|太棒了|厉害了|真棒)$",
            r"^(再见|拜拜|bye)$"
        ]
        q = question.strip().lower()
        return any(re.search(p, q) for p in simple_patterns) or len(q) <= 2

    def _handle_simple_query(self, question: str) -> Iterator[str]:
        """对简单问题直接生成回复，不走 RAG 流程。"""
        system_prompt = "你是一个简洁友好的知识库助手。请直接回答用户的寒暄或简单问题，不要提及任何文档内容。保持回答在 1-2 句话内。"
        full_prompt = f"{system_prompt}\n\n用户: {question}\n回答:"
        if self.llm:
            return self.llm.stream(full_prompt)
        return iter([])

    def _extract_intent_with_llm(self, question: str, all_files: List[str]) -> Optional[Dict[str, Any]]:
        """使用 LLM 对用户的自然语言查询进行前置意图分析。
        优化版：增加了针对文件类型思考的引导，并减少了冗余 Token 输出以提升速度。
        """

        if self.llm is None:
            return None
            
        # 预剪枝：如果问题太短，没必要动用 LLM
        if len(question.strip()) < 5:
            return None
            
        # 意图引擎旁路 (Intent Engine Bypass)
        # 如果问题中没有暗示要找文件的关键词，直接跳过 LLM 意图分析，节省 10-60 秒！
        file_keywords = ["文件", "目录", "夹", "第", "最新", "最后", "pdf", "word", "由于", "属于", "关于此", "这篇", "那个"]
        if not any(k in question.lower() for k in file_keywords):
            logger.info("llm_intent_bypass question=%s", question[:80])
            return None

        # 仅向模型展示前 100 个文件，避免上下文爆炸
        display_files = all_files[:100]
        file_list_str = "\n".join(f"- {f}" for f in display_files)

        # 极简提示词，强迫模型快速响应
        intent_prompt = f"""[File Intent Engine] 
List:
{file_list_str}

重要规则:
1. 如果用户说"第一个文件"或"第1个"，请从文件列表中选出该目录下排序第1的文件。
2. 如果用户说"最新的"或"最后一个"，选出该目录下排序最后的文件。
3. 如果用户说"pdf文件"或"文字文件"等，设定 category 过滤而非 target_file。
4. 如果用户说"rag文件夹下的第一个pdf"，先定位到 rag/ 目录，再选出第一个 .pdf 文件。
5. 只输出 JSON，不要多余解释。"""

        try:
            logger.info("llm_intent_extraction_start question=%s", question[:80])
            raw = self.llm.invoke(intent_prompt)
            # 提取 JSON 部分 (兼容模型在 JSON 前后可能输出的 ```json 等标记)
            raw = raw.strip()
            if "```" in raw:
                # 去掉 markdown 代码块
                raw = raw.split("```")[1] if "```" in raw else raw
                if raw.startswith("json"):
                    raw = raw[4:]
                raw = raw.strip()

            result = json.loads(raw)
            logger.info("llm_intent_result=%s", result)
            return result
        except asyncio.TimeoutError:
            logger.warning("llm_intent_extraction_timeout")
            return None
        except Exception as e:
            logger.warning("llm_intent_extraction_failed: %s", e)
            return None

    def _analyze_intent(self, question: str, category: Optional[str] = None) -> Tuple[Optional[str], set, Optional[str]]:
        import re
        from pathlib import Path
        from .config import DOCS_DIR

        all_files = self.list_doc_files()

        target_filename: Optional[str] = None
        target_dirs: set = set()
        detected_category: Optional[str] = None

        # ─── Phase 0: Fast Track Regex / Substring Match (🏎️ Zero Latency) ───
        cleaned_q = question.lower()
        for rel_path in all_files:
            filename = Path(rel_path).name.lower()
            if rel_path.lower() in cleaned_q or filename in cleaned_q:
                target_filename = rel_path
                print(f"🎯 [Debug] Fast Track Match: {target_filename}")
                logger.info("fast_track_match_found=%s", target_filename)
                break

        llm_intent = None
        if not target_filename:
            # ─── Phase 1: LLM 前置意图分析 (仅在没有 Fast Track 命中时执行) ───
            llm_intent = self._extract_intent_with_llm(question, all_files)

        if llm_intent:
            if llm_intent.get("target_file"):
                candidate = llm_intent["target_file"]
                if candidate in all_files:
                    target_filename = candidate
                else:
                    for f in all_files:
                        if candidate.lower() in f.lower() or f.lower().endswith(candidate.lower()):
                            target_filename = f
                            break

            if not target_filename and llm_intent.get("target_dir"):
                target_dirs.add(llm_intent["target_dir"])

            if llm_intent.get("category"):
                detected_category = llm_intent["category"]

        # ─── Phase 2: 正则 Fallback (如果 LLM 没有解析出来) ───
        if not target_filename and not target_dirs:
            for rel_path in all_files:
                file_path_obj = Path(rel_path)
                if file_path_obj.name.lower() in question.lower() or rel_path.lower() in question.lower():
                    target_filename = rel_path
                    break

        if not target_filename and not target_dirs:
            for rel_path in all_files:
                parts = Path(rel_path).parent.parts
                for part in parts:
                    if part and part != "." and len(part) >= 2:
                        pattern = r'(?<![a-zA-Z])' + re.escape(part.lower()) + r'(?![a-zA-Z])'
                        if re.search(pattern, question.lower()):
                            target_dirs.add(part)

        if not detected_category:
            extension_to_category = {
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
                ".webp": "image"
            }
            for ext, cat in extension_to_category.items():
                if ext in question.lower():
                    detected_category = cat
                    logger.info("extension_match_found extension=%s category=%s", ext, cat)
                    break
            
            if not detected_category:
                category_keywords = {
                    "pdf": ["pdf", "电子书"],
                    "word_text": ["word", "docx", "doc", "文本", "txt", "记录", "文档"],
                    "data_web": ["csv", "表格", "数据", "html", "网页", "htm"],
                    "markdown": ["md", "markdown", "说明", "readme"],
                    "image": ["图片", "照片", "图", "png", "jpg", "jpeg", "webp", "识别", "ocr"]
                }
                for cat_id, keywords in category_keywords.items():
                    if any(re.search(r'(?<![a-zA-Z])' + re.escape(k) + r'(?![a-zA-Z])', question.lower(), re.IGNORECASE) for k in keywords):
                        detected_category = cat_id
                        break

        final_category = category if category not in (None, "", "all") else detected_category
        print(f"🔍 [Debug] Intent Result: file={target_filename}, category={final_category}")
        return target_filename, target_dirs, final_category

    def _retrieve_documents(self, question: str, category: Optional[str] = None) -> Tuple[List[Document], List[Document], Optional[str], Optional[str]]:
        if self.db is None:
            return [], [], None, None

        from pathlib import Path
        from .config import DOCS_DIR
        all_files = self.list_doc_files()
        
        target_filename, target_dirs, final_category = self._analyze_intent(question, category)

        filters: List[Dict[str, Any]] = []
        if final_category:
            logger.info("intent_extracted category=%s", final_category)
            filters.append({"file_category": final_category})

        if target_filename:
            logger.info("intent_extracted target_file=%s", target_filename)
            filters.append({"source": str(DOCS_DIR / target_filename)})
        elif target_dirs:
            logger.info("intent_extracted target_dirs=%s", target_dirs)
            dir_file_sources = []
            for filename in all_files:
                parts = Path(filename).parts
                if any(d in parts for d in target_dirs):
                    dir_file_sources.append({"source": str(DOCS_DIR / filename)})
            if dir_file_sources:
                if len(dir_file_sources) == 1:
                     filters.append(dir_file_sources[0])
                else:
                     filters.append({"$or": dir_file_sources})

        if not filters:
            docs = self.retriever.invoke(question)
        else:
            if len(filters) == 1:
                filter_dict = filters[0]
            else:
                filter_dict = {"$and": filters}

            logger.info("retrieval_filter_active filter=%s", filter_dict)
            target_k = 5 if target_filename else 6
            search_kwargs = {"k": target_k, "fetch_k": target_k * 2, "filter": filter_dict}
            vector_retriever = self.db.as_retriever(
                search_type="mmr",
                search_kwargs=search_kwargs,
            )
            docs = vector_retriever.invoke(question)

        # 4. 分离 Skill 和普通文档
        skills = [d for d in docs if d.metadata.get("is_skill")]
        regular_docs = [d for d in docs if not d.metadata.get("is_skill")]

        # Reranker 精排：对普通文档进行二次评分
        # 如果已经精确拿到了目标文件 (target_filename)，则不需要通过文本相似度重排，直接返回全量 chunks 即可
        if len(regular_docs) > 5 and not target_filename:
            top_k = 8
            regular_docs = self._rerank_documents(question, regular_docs, top_k=top_k)

        # --- 注入知识记忆 (Inject Knowledge Memory) ---
        from .config import load_memory, DOCS_DIR, SKILLS_DIR
        enriched_docs = []
        for doc in regular_docs:
            source_path = doc.metadata.get("source") or ""
            # 计算相对于 docs/ 或 skills/ 的路径，以匹配 save_memory 的 key
            rel_path = "未知"
            if source_path:
                p = Path(source_path)
                try:
                    if str(DOCS_DIR) in str(p):
                        rel_path = str(p.relative_to(DOCS_DIR))
                    elif str(SKILLS_DIR) in str(p):
                        rel_path = str(p.relative_to(SKILLS_DIR))
                except ValueError:
                    rel_path = p.name
            
            memory = load_memory(rel_path)
            if memory:
                # 添加记忆标记 (Add memory prefix)
                doc.page_content = f"【历史分析记忆 (Past Insight)】: {memory['insight']}\n\n【当前文档片段内容】:\n{doc.page_content}"
                logger.info("memory_injected filename=%s", rel_path)
            enriched_docs.append(doc)

        # 返回 (常规文档, 技能, 最终分类, 最终目标文件)
        return enriched_docs, skills, final_category, target_filename

    def distill_insights(self, history: List[Dict[str, Any]]) -> Optional[str]:
        """从会话历史中提炼关于文档的知识见解"""
        if not history:
            return None
            
        print(f"📖 [Debug] Distilling insights from {len(history)} messages...")
        # Frontend uses 'user' and 'assistant' keys
        history_text = ""
        for m in history:
            u = m.get('user', '')
            a = m.get('assistant', '')
            history_text += f"User: {u}\nAssistant: {a}\n---\n"
        
        prompt = f"""请分析以下对话历史，并提炼出关于其中提到的【物理文档】的核心结论、事实或深入见解。
要求：
1. 忽略琐碎的礼谈话，只保留有价值的知识、分析结果或结论。
2. 以第三人称客观描述（例如：“文档 X 提到...”，“分析得出 Y 结论...”）。
3. 语言精炼，适合作为未来检索的参考背景。
4. 如果对话中涉及多个文件，请尽量整合或选出最核心的一个分析结果。

对话历史：
{history_text}

提炼总结 (请用对应语言回复，中文或英文):"""

        try:
            print(f"🤖 [Debug] Sending distillation prompt to LLM...")
            summary = self.llm.invoke(prompt).strip()
            print(f"✨ [Debug] Distillation result: {summary[:100]}...")
            return summary
        except Exception as e:
            print(f"❌ [Debug] Distillation failed: {e}")
            logger.error("distill_insights_failed: %s", e)
            return None

    def _rerank_documents(self, question: str, docs: List[Document], top_k: int = 8) -> List[Document]:
        """
        性能优化版：使用单个 LLM 调用对多个候选段落进行批量打分。
        这比循环逐个打分快 10 倍以上。
        """
        if not docs or self.llm is None:
            return docs[:top_k]

        logger.info("rerank_bulk_start candidates=%s top_k=%s", len(docs), top_k)
        
        # 构造批量评分 Prompt
        snippets_text = ""
        for i, doc in enumerate(docs):
            # 截取较短长度以节省 Token
            content = doc.page_content.replace("\n", " ")[:200]
            snippets_text += f"ID:{i} | 内容: {content}\n"

        score_prompt = (
            f"请评估以下 {len(docs)} 个段落与用户问题“{question}”的相关性。\n"
            f"对于每个段落，给出 0-10 的评分（10为最相关）。\n"
            f"【严格要求】只返回一个 JSON 数组（按 ID 顺序排序的分数），例如: [8, 2, 9, 5...]\n"
            f"不要输出任何解释说明。\n\n"
            f"待评估段落：\n{snippets_text}\n"
            f"评分结果 (仅 JSON 数组):"
        )

        try:
            raw = self.llm.invoke(score_prompt).strip()
            # 尝试解析 JSON
            import json as _json
            import re
            
            # 使用正则提取数组部分，防止模型输出冗余 Markdown 标记
            match = re.search(r'\[[\d,\s.]+\]', raw)
            if match:
                scores = _json.loads(match.group())
            else:
                # Fallback: 手动按逗号/空格分割
                scores = [int(s) for s in re.findall(r'\d+', raw)]
            
            scored = []
            for i, doc in enumerate(docs):
                score = scores[i] if i < len(scores) else 5
                scored.append((score, doc))
            
            # 按分数降序排列
            scored.sort(key=lambda x: x[0], reverse=True)
            result = [doc for _, doc in scored[:top_k]]
            logger.info("rerank_bulk_success scores=%s", scores[:top_k])
            return result
            
        except Exception as e:
            logger.error("rerank_bulk_failed: %s", e)
            return docs[:top_k] # 失败时退回到截断模式

    def query(self, question: str, category: Optional[str] = None, history_arr: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        question = (question or "").strip()
        history_text = self._format_history(history_arr)

        if not question:
            return {
                "ok": False,
                "answer": "⚠️ 请输入问题。",
                "sources": [],
            }

        if self.qa is None:
            return {
                "ok": False,
                "answer": "⚠️ 请先执行选项 1 索引文档！",
                "sources": [],
            }

        self._ensure_runtime()
        print("🤔 思考中...")

        last_history_text = self._latest_history_text(history_arr)
        search_query = f"{last_history_text + ' ' if last_history_text else ''}{question}"
        source_docs, skills, _, _ = self._retrieve_documents(search_query, category)

        if category not in (None, "", "all") and not source_docs:
            return {
                "ok": False,
                "answer": "⚠️ 当前选择的文档类型下没有匹配内容，请切换左侧类型或重建索引后重试。",
                "sources": [],
            }

        current_time = time.strftime("%Y-%m-%d %H:%M:%S")
        context_parts = []
        for i, doc in enumerate(source_docs, 1):
            filename = os.path.basename(doc.metadata.get("source", "未知来源"))
            mtime = doc.metadata.get("file_mtime_str", "未知")
            context_parts.append(f"[文档 {i}] 文件名: {filename}, 修改时间: {mtime}\n内容: {doc.page_content}")
        context = "\n\n".join(context_parts)
        # --- 注入全局技能 (Global Skills Injection) ---
        # 扫描 skills/ 根目录下的所有文件作为全局指令
        global_skills = []
        from .config import SKILLS_DIR
        for f in SKILLS_DIR.glob('*'):
            if f.is_file() and f.name != '.gitkeep' and not f.name.startswith('.'):
                try:
                    content = f.read_text("utf-8").strip()
                    if content:
                        global_skills.append(f"【全局固定指令 - {f.name}】: {content}")
                except Exception: continue
        
        combined_skills_text = ""
        if global_skills or skills:
            combined_skills_text = "【检测到匹配的专业技能指令，请务必作为行为准则优先遵循】:\n"
            # 先放全局指令
            for i, s in enumerate(global_skills, 1):
                combined_skills_text += f"A{i}. {s}\n"
            # 再放检索到的技能
            for i, s in enumerate(skills, 1):
                fname = os.path.basename(s.metadata.get("source", "未知技能"))
                combined_skills_text += f"B{i}. 局部技能[{fname}]: {s.page_content}\n"

        # --- 获取全局记忆 (Global Memory Injection) ---
        from .config import load_memory
        global_mem_data = load_memory("global_memory")
        global_mem_text = ""
        if global_mem_data:
            global_mem_text = f"【全局知识库见解 (Global Insights)】: {global_mem_data.get('insight', '')}\n"

        prompt_text = self.current_prompt.format(
            history=history_text, 
            context=context, 
            question=question, 
            current_time=current_time, 
            skills=combined_skills_text,
            global_memory=global_mem_text
        )
        answer = self.llm.invoke(prompt_text)

        return {
            "ok": True,
            "answer": answer,
            "sources": extract_sources(source_docs),
        }

    def _format_history(self, history_arr: Optional[List[Dict[str, Any]]]) -> str:
        if not history_arr or not isinstance(history_arr, list):
            return ""
        lines = []
        for msg in history_arr[-5:]: # Keep last 5 messages for context window
            if not isinstance(msg, dict):
                continue
            role_raw = msg.get("role", "")
            role = "用户" if role_raw == "user" else "AI助手"
            content = msg.get("content", "").strip()
            if content:
                lines.append(f"{role}: {content}")
        return "\n".join(lines)

    def _latest_history_text(self, history_arr: Optional[List[Dict[str, Any]]]) -> str:
        if not history_arr or not isinstance(history_arr, list):
            return ""
        last = history_arr[-1]
        if not isinstance(last, dict):
            return ""
        if last.get("content"):
            return str(last.get("content")).strip()
        user_text = str(last.get("user", "")).strip()
        assistant_text = str(last.get("assistant", "")).strip()
        return assistant_text or user_text

    def stream_query(self, question: str, category: Optional[str] = None, history_arr: Optional[List[Dict[str, Any]]] = None) -> Iterator[Dict[str, Any]]:
        question = (question or "").strip()
        history_text = self._format_history(history_arr)

        logger.info("stream_query_start question_len=%s", len(question))
        if not question:
            logger.info("stream_query_reject_empty")
            yield {"type": "error", "data": "⚠️ 请输入问题！"}
            return

        if self.db is None or self.retriever is None:
            logger.info("stream_query_reject_no_index")
            yield {"type": "error", "data": "⚠️ 请先构建索引！"}
            return

        self._ensure_runtime()
        
        # --- 提速优化：简单问题短路 (Short-circuit) ---
        if self._is_simple_query(question):
            logger.info("stream_query_short_circuit question=%s", question)
            has_token = False
            for chunk in self._handle_simple_query(question):
                text = chunk if isinstance(chunk, str) else getattr(chunk, "content", str(chunk))
                if text:
                    has_token = True
                    yield {"type": "token", "data": text}
            if has_token:
                yield {"type": "sources", "data": []}
                return

        last_history_text = self._latest_history_text(history_arr)
        search_query = f"{last_history_text + ' ' if last_history_text else ''}{question}"
        
        # 0. 通知前端：正在分析意图
        yield {"type": "status", "data": "🔍 正在分析您的意图..."}
        
        # 1. 检索 (现在返回 常规文档, 技能, 分类, 目标文件)
        source_docs, skills, final_category, target_filename = self._retrieve_documents(search_query, category)
        
        # 通知前端：意图分析完成
        status_msg = "🔍 意图分析完成。"
        if final_category:
            status_msg += f" 类别: {final_category}."
        if target_filename:
            status_msg += f" 目标文件: {os.path.basename(target_filename)}."
        
        yield {"type": "status", "data": status_msg}

        if source_docs:
            first_source_path = source_docs[0].metadata.get("source", "")
            first_source = os.path.basename(first_source_path)
            yield {"type": "status", "data": f"📑 正在分析文档内容: {first_source}..."}
            
            # Record file usage for the primary retrieved document
            from .config import record_file_usage, DOCS_DIR
            try:
                rel_path = str(Path(first_source_path).relative_to(DOCS_DIR))
                record_file_usage([rel_path])
            except Exception:
                pass
        
        if category not in (None, "", "all") and not source_docs:
            logger.info("stream_query_no_docs_for_category category=%s", category)
            yield {
                "type": "error",
                "data": "当前选择的文档类型下没有匹配内容，请切换左侧类型或重建索引后重试。",
            }
            return
            
        logger.info("stream_query_retrieved_docs=%s skills=%s", len(source_docs), len(skills))
        
        # 2. 注入全局技能与格式化检索到的 Skill
        global_skills = []
        from .config import SKILLS_DIR
        for f in SKILLS_DIR.glob('*'):
            if f.is_file() and f.name != '.gitkeep' and not f.name.startswith('.'):
                try:
                    content = f.read_text("utf-8").strip()
                    if content:
                        global_skills.append(f"【全局固定指令 - {f.name}】: {content}")
                except Exception: continue

        combined_skills_text = ""
        if global_skills or skills:
            combined_skills_text = "【检测到匹配的专业技能指令，请务必作为行为准则优先遵循】:\n"
            for i, s in enumerate(global_skills, 1):
                combined_skills_text += f"A{i}. {s}\n"
            for i, s in enumerate(skills, 1):
                fname = os.path.basename(s.metadata.get("source", "未知技能"))
                combined_skills_text += f"B{i}. 局部技能[{fname}]: {s.page_content}\n"
        
        # 3. 注入全局见解 (Inject Global Insights)
        from .config import load_memory
        global_mem_data = load_memory("global_memory")
        global_mem_text = ""
        if global_mem_data:
            global_mem_text = f"【全局知识库见解 (Global Insights)】: {global_mem_data.get('insight', '')}\n"

        # 4. 格式化常规资料
        current_time = time.strftime("%Y-%m-%d %H:%M:%S")
        context_parts = []
        for i, doc in enumerate(source_docs, 1):
            filename = os.path.basename(doc.metadata.get("source", "未知来源"))
            mtime = doc.metadata.get("file_mtime_str", "未知")
            context_parts.append(f"[文档 {i}] 文件名: {filename}, 修改时间: {mtime}\n内容: {doc.page_content}")
        context = "\n\n".join(context_parts)
        
        # 5. 填充 Prompt
        prompt_text = self.current_prompt.format(
            history=history_text, 
            context=context, 
            question=question, 
            current_time=current_time,
            skills=combined_skills_text,
            global_memory=global_mem_text
        )

        has_token = False
        for chunk in self.llm.stream(prompt_text):
            text = chunk if isinstance(chunk, str) else getattr(chunk, "content", str(chunk))
            if text:
                has_token = True
                yield {"type": "token", "data": text}

        if not has_token:
            logger.info("stream_query_no_token")
            yield {
                "type": "error",
                "data": "模型未返回内容。请确认 Ollama 服务和模型状态（例如 qwen3:8b）后重试。",
            }
            return

        logger.info("stream_query_done_with_token")
        yield {"type": "sources", "data": extract_sources(source_docs)}

    @staticmethod
    def _extract_sources(source_docs):
        return extract_sources(source_docs)


def main():
    from scripts.cli import main as cli_main

    return cli_main()


if __name__ == "__main__":
    raise SystemExit(main())

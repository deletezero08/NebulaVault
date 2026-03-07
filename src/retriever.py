import os
import logging
from typing import List, Any

logger = logging.getLogger("rag_core")

from langchain_community.retrievers import BM25Retriever
from langchain_core.documents import Document
from langchain_classic.chains import RetrievalQA
from langchain_classic.retrievers.ensemble import EnsembleRetriever


def build_retriever(db: Any) -> Any:
    vector_retriever = db.as_retriever(
        search_type="mmr",
        search_kwargs={"k": 10, "fetch_k": 30},
    )

    # 性能优化：避免加载全量文档到内存构建 BM25
    # 我们只加载前 2000 个片段参与混合检索，或者由用户决定
    try:
        # 只获取必要字段，减轻负担
        db_data = db.get(limit=2000, include=["documents", "metadatas"])
    except Exception as e:
        logger.warning(f"Failed to fetch docs for BM25: {e}")
        return vector_retriever

    documents = []
    if db_data and db_data.get("documents"):
        for index, text in enumerate(db_data["documents"]):
            metadata = db_data["metadatas"][index] if db_data.get("metadatas") else {}
            documents.append(Document(page_content=text, metadata=metadata))

    if not documents:
        return vector_retriever

    try:
        bm25_retriever = BM25Retriever.from_documents(documents)
        bm25_retriever.k = 8
        return EnsembleRetriever(
            retrievers=[vector_retriever, bm25_retriever],
            weights=[0.7, 0.3],
        )
    except Exception as e:
        logger.error(f"Failed to build BM25 retriever: {e}")
        return vector_retriever


def build_qa_chain(llm: Any, retriever: Any, prompt: Any) -> Any:
    return RetrievalQA.from_chain_type(
        llm=llm,
        chain_type="stuff",
        retriever=retriever,
        chain_type_kwargs={"prompt": prompt},
        return_source_documents=True,
    )


def extract_sources(source_docs: List[Document]) -> List[str]:
    seen = set()
    sources: List[str] = []
    for doc in source_docs:
        source = doc.metadata.get("source", "未知来源")
        page = doc.metadata.get("page")
        label = os.path.basename(source)
        if page is not None:
            label += f" (page {page + 1})"
        if label not in seen:
            seen.add(label)
            sources.append(label)
    return sources

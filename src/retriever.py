import os
import logging
from typing import List, Any, Dict, Optional
from langchain_community.retrievers import BM25Retriever
from langchain_core.documents import Document
from langchain_classic.chains import RetrievalQA
from langchain_classic.retrievers.ensemble import EnsembleRetriever

logger = logging.getLogger("rag_core")


from langchain_core.retrievers import BaseRetriever
from langchain_core.callbacks import CallbackManagerForRetrieverRun
from src.config import settings

class HybridRetriever(BaseRetriever):
    """
    A custom retriever that combines vector search and BM25 using 
    Reciprocal Rank Fusion (RRF) or weighted ensemble.
    """
    vector_retriever: Any
    bm25_retriever: BM25Retriever
    mode: str = "rrf"
    weights: List[float] = [settings["retrieval"]["weights"]["vector"], settings["retrieval"]["weights"]["bm25"]]
    k: int = settings["retrieval"]["rrf_k"]

    def _get_relevant_documents(
        self, query: str, *, run_manager: CallbackManagerForRetrieverRun = None
    ) -> List[Document]:
        if self.mode == "vector_only":
            return self.vector_retriever.invoke(query)
        
        # 1. Fetch candidates from both routes
        vector_docs = self.vector_retriever.invoke(query)
        bm25_docs = self.bm25_retriever.invoke(query)
        
        if self.mode == "ensemble":
            # Simple weighted ensemble
            ensemble = EnsembleRetriever(
                retrievers=[self.vector_retriever, self.bm25_retriever],
                weights=self.weights
            )
            return ensemble.invoke(query)
            
        # 2. Implement manual RRF (Reciprocal Rank Fusion)
        doc_scores: Dict[str, float] = {}
        doc_map: Dict[str, Document] = {}
        
        def update_scores(docs: List[Document], weight: float = 1.0):
            for rank, doc in enumerate(docs, 1):
                doc_id = doc.page_content
                doc_map[doc_id] = doc
                if doc_id not in doc_scores:
                    doc_scores[doc_id] = 0.0
                doc_scores[doc_id] += weight * (1.0 / (rank + self.k))

        update_scores(vector_docs, weight=1.5)
        update_scores(bm25_docs, weight=1.0)
        
        sorted_ids = sorted(doc_scores.keys(), key=lambda x: doc_scores[x], reverse=True)
        return [doc_map[did] for did in sorted_ids[:10]]


def get_bm25_docs(db: Any, limit: int = 3000) -> List[Document]:
    """Helper to fetch documents for BM25 initialization."""
    try:
        db_data = db.get(limit=limit, include=["documents", "metadatas"])
        documents = []
        if db_data and db_data.get("documents"):
            for index, text in enumerate(db_data["documents"]):
                metadata = db_data["metadatas"][index] if db_data.get("metadatas") else {}
                documents.append(Document(page_content=text, metadata=metadata))
        return documents
    except Exception as e:
        logger.warning(f"Failed to fetch docs for BM25: {e}")
        return []


def build_retriever(db: Any, mode: str = "ensemble") -> Any:
    """
    Builds the retrieval chain based on requested mode. 
    Supported modes: 'vector_only', 'ensemble', 'rrf'
    """
    vector_config = settings["retrieval"]
    vector_retriever = db.as_retriever(
        search_type="mmr",
        search_kwargs={
            "k": vector_config.get("vector_k", 12),
            "fetch_k": vector_config.get("vector_k", 12) * 3
        },
    )

    if mode == "vector_only":
        return vector_retriever

    documents = get_bm25_docs(db)
    if not documents:
        return vector_retriever

    try:
        bm25_retriever = BM25Retriever.from_documents(documents)
        bm25_retriever.k = 10
        
        if mode == "rrf":
            return HybridRetriever(
                vector_retriever=vector_retriever, 
                bm25_retriever=bm25_retriever, 
                mode="rrf",
                k=settings["retrieval"].get("rrf_k", 60)
            )
        else:
            # Default to ensemble
            w = settings["retrieval"]["weights"]
            return EnsembleRetriever(
                retrievers=[vector_retriever, bm25_retriever],
                weights=[w["vector"], w["bm25"]],
            )
    except Exception as e:
        logger.error(f"Failed to build hybrid retriever: {e}")
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

#!/usr/bin/env python3
import os
import sys
import time
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.engine import LocalRAG

def test_modes():
    print("🧪 开始混合检索模式对比测试...")
    
    # 确保有知识库
    rag = LocalRAG()
    status = rag.get_status()
    if not status.get("has_index") or rag.db is None:
        print("❌ 错误：知识库未加载，正在尝试构建临时索引...")
        rag.index_docs()
    
    # 打印数据库统计
    try:
        count = rag.db._collection.count()
        print(f"📊 数据库当前包含 {count} 个片段。")
    except Exception as e:
        print(f"⚠️ 无法获取数据库统计: {e}")

    test_queries = [
        "系统在高并发下需要启用什么？", 
        "项目代号是什么？",
    ]

    modes = ["vector_only", "ensemble", "rrf"]
    
    for query in test_queries:
        print(f"\n❓ 问题: {query}")
        print("-" * 50)
        
        for mode in modes:
            rag.retrieval_mode = mode
            rag._build_qa_chain()
            
            if rag.retriever is None:
                print(f"[{mode:12}] ❌ 错误：检索器未初始化")
                continue

            start_time = time.time()
            # 注意：BaseRetriever 建议调用 invoke()
            docs, skills, _, _ = rag._retrieve_documents(query)
            elapsed = time.time() - start_time
            
            print(f"[{mode:12}] 耗时: {elapsed:.3f}s | 召回数量: {len(docs)}")
            if docs:
                for i, d in enumerate(docs[:3], 1):
                    src = os.path.basename(d.metadata.get("source", "unknown"))
                    snippet = d.page_content.replace("\n", " ")[:80]
                    print(f"   Rank {i}: [{src}] {snippet}...")
            else:
                print("   ⚠️ 未召回到任何文档")

if __name__ == "__main__":
    test_modes()

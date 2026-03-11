#!/usr/bin/env python3
import sys
import os
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.engine import LocalRAG, INTENT_STATS

def test_intent_accuracy():
    print("🚀 开始意图识别准确性回归测试 (Final Validation)...")
    rag = LocalRAG()
    
    # 期望动作定义：
    # - smalltalk: 寒暄检测，短路跳过 RAG
    # - open_domain: 知识库全库检索，无特定文件锁定
    # - target_file: 命中特定文件，进入针对性检索
    
    test_cases = [
        {"q": "分析 docs 下的第一个文件", "expected": "target_file"},
        {"q": "总结一下 api_docs.md", "expected": "target_file"},
        {"q": "你好，请问你是？", "expected": "smalltalk"},
        {"q": "什么是量子纠缠的原理？", "expected": "open_domain"},
        {"q": "帮我看看这个不存在的文件.txt", "expected": "open_domain"},
    ]
    
    results = []
    
    for case in test_cases:
        INTENT_STATS["hits"] = 0
        INTENT_STATS["bypass"] = 0
        INTENT_STATS["misses"] = 0
        
        print(f"\n测试问题: {case['q']}")
        print("  运行中: ", end="", flush=True)
        
        status_events = []
        for event in rag.stream_query(case['q']):
            if event['type'] == 'status':
                evt_data = event['data']
                status_events.append(evt_data)
                print(f"[{evt_data}] ", end="", flush=True)
            elif event['type'] == 'error':
                 print(f"[ERROR: {event['data']}] ", end="", flush=True)
        
        # Determine actual action label
        actual = "unknown"
        has_retrieval = any("检索知识库" in s for s in status_events)
        has_target = any("正在分析指定文档" in s for s in status_events)
        
        if not has_retrieval:
            actual = "smalltalk"
        elif has_target:
            actual = "target_file"
        else:
            actual = "open_domain"
        
        status = "✅ 通过" if actual == case["expected"] else f"❌ 失败"
        results.append((case['q'], status, actual))
        print(f"\n  最终动作判定: {actual} -> {status}")

    print("\n" + "="*60)
    print("📊 毕设意图识别路由回归测试报告")
    print("-"*60)
    print(f"{'测试问题':<30} | {'预期标签':<15} | {'实际动作':<15} | {'状态'}")
    print("-"*60)
    for q, (qq, status, actual) in zip(test_cases, results):
        print(f"{qq[:28]:<30} | {q['expected']:<15} | {actual:<15} | {status}")
    print("="*60)
    
    print("\n✅ 测试脚本执行完毕。")

if __name__ == "__main__":
    test_intent_accuracy()

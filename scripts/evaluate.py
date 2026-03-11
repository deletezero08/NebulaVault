#!/usr/bin/env python3
import os
import sys
import json
import time
from typing import List, Dict, Any
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.engine import LocalRAG
from src.config import settings
from scripts.logger import log_entry

class RAGEvaluator:
    def __init__(self, model_name: str = None):
        self.rag = LocalRAG()
        # Use config if model_name not provided
        self.grading_model = model_name or settings.get("llm", {}).get("judge_model", "qwen3:8b")
        self.results_dir = Path(ROOT_DIR) / "experiments" / "results"
        self.results_dir.mkdir(parents=True, exist_ok=True)

    def _get_grade(self, question: str, ground_truth: str, answer: str, context: str) -> Dict[str, float]:
        """Uses the LLM to grade the answer based on Faithfulness and Relevance."""
        metrics = settings.get("evaluation", {}).get("metrics", ["faithfulness", "relevance"])
        metrics_desc = "\n".join([f"{i+1}. {m.capitalize()}: ..." for i, m in enumerate(metrics)])
        
        prompt = f"""作为一名公正的评分员，请评估 RAG 系统的回答质量。
参考资料: {context}
用户问题: {question}
标准答案: {ground_truth}
系统回答: {answer}

请给出以下指标的评分（0-10分，只输出 JSON 格式，如 {{"faithfulness": 8, "relevance": 9}}）：
{metrics_desc}
评分 JSON:"""
        
        try:
            # Re-use the RAG instance's LLM for grading (or a separate one if needed)
            raw = self.rag.llm.invoke(prompt).strip()
            # Clean up the output to get pure JSON
            if "```" in raw:
                raw = raw.split("```")[1]
                if raw.startswith("json"): raw = raw[4:]
            return json.loads(raw)
        except Exception as e:
            print(f"⚠️ 评分失败: {e}")
            return {"faithfulness": 0.0, "relevance": 0.0}

    def evaluate_mode(self, mode: str, test_cases: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        print(f"\n🚀 开始评估模式: {mode}")
        self.rag.retrieval_mode = mode
        self.rag._build_qa_chain()
        
        results = []
        for case in test_cases:
            print(f"  📝 处理问题 {case['id']}...")
            start_time = time.time()
            
            # Use query instead of stream for evaluation convenience
            response = self.rag.query(case['question'], category="all")
            elapsed = time.time() - start_time
            
            # Combine sources for grading context
            context_text = "\n".join([d.page_content for d in self.rag.retriever.invoke(case['question'])])
            
            grades = self._get_grade(case['question'], case['ground_truth'], response['answer'], context_text)
            
            results.append({
                "id": case['id'],
                "question": case['question'],
                "answer": response['answer'],
                "latency": elapsed,
                "scores": grades,
                "sources_count": len(response.get('sources', []))
            })
            
        return results

    def run(self):
        cases_file = Path(ROOT_DIR) / "experiments" / "test_cases.json"
        if not cases_file.exists():
            print("❌ 未找到测试用例文件。")
            return
            
        with open(cases_file, "r", encoding="utf-8") as f:
            test_cases = json.load(f)

        all_results = {}
        for mode in ["vector_only", "rrf"]:
            all_results[mode] = self.evaluate_mode(mode, test_cases)
            
        output_file = self.results_dir / f"evaluation_{int(time.time())}.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(all_results, f, ensure_ascii=False, indent=2)
            
        self._print_summary(all_results)
        
        # Log to Research Log
        summary_str = " | ".join([f"{m}: Faith={sum(r['scores']['faithfulness'] for r in res)/len(res):.1f}" for m, res in all_results.items()])
        log_entry(
            entry_type="Result",
            description="自动化评估实验 (Auto-Evaluation)",
            results=summary_str,
            note=f"报告详情: {output_file.name}"
        )
        
        print(f"\n✅ 评估报告已生成: {output_file}")

    def _print_summary(self, all_results: Dict[str, List[Any]]):
        print("\n" + "="*50)
        print("📊 评估结果摘要 (Averaged Scores)")
        print("-" * 50)
        for mode, res in all_results.items():
            avg_faith = sum(r['scores']['faithfulness'] for r in res) / len(res)
            avg_rel = sum(r['scores']['relevance'] for r in res) / len(res)
            avg_lat = sum(r['latency'] for r in res) / len(res)
            print(f"[{mode:12}] Faithfulness: {avg_faith:.2f} | Relevance: {avg_rel:.2f} | Latency: {avg_lat:.2f}s")
        print("="*50)

if __name__ == "__main__":
    evaluator = RAGEvaluator()
    evaluator.run()

#!/usr/bin/env python3
import os
import json
import argparse
from datetime import datetime
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
LOG_MD = ROOT_DIR / "RESEARCH_LOG.md"
LOG_JSON = ROOT_DIR / "experiments" / "research_history.json"

def init_logs():
    if not LOG_MD.exists():
        with open(LOG_MD, "w", encoding="utf-8") as f:
            f.write("# NebulaVault 毕业论文研究与实验日志 (Research Log)\n\n")
            f.write("| 日期 | 类型 | 内容描述 | 实验结果/指标 | 备注 |\n")
            f.write("| :--- | :--- | :--- | :--- | :--- |\n")
    
    LOG_JSON.parent.mkdir(parents=True, exist_ok=True)
    if not LOG_JSON.exists():
        with open(LOG_JSON, "w", encoding="utf-8") as f:
            json.dump([], f)

def log_entry(entry_type: str, description: str, results: str = "-", note: str = "-"):
    init_logs()
    date_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    
    # Update Markdown
    with open(LOG_MD, "a", encoding="utf-8") as f:
        f.write(f"| {date_str} | {entry_type} | {description} | {results} | {note} |\n")
    
    # Update JSON
    try:
        with open(LOG_JSON, "r", encoding="utf-8") as f:
            history = json.load(f)
    except:
        history = []
        
    history.append({
        "timestamp": date_str,
        "type": entry_type,
        "description": description,
        "results": results,
        "note": note
    })
    
    with open(LOG_JSON, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="NebulaVault Research Logger")
    parser.add_argument("--type", choices=["Modification", "Result", "Note"], default="Modification")
    parser.add_argument("--desc", required=True, help="Detailed description of the change or result")
    parser.add_argument("--res", default="-", help="Experimental results or metrics")
    parser.add_argument("--note", default="-", help="Additional notes")
    
    args = parser.parse_args()
    log_entry(args.type, args.desc, args.res, args.note)
    print(f"✅ 日志已更新: {args.type} - {args.desc[:30]}...")

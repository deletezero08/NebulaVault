# Contributing

感谢你对 LocalRAG 的贡献。

## 开发前准备

1. 使用 Python 3.13 创建虚拟环境。
2. 安装依赖：`pip install -r requirements.txt`
3. 确保本地 Ollama 可用（如果要跑真实联调）。

## 提交流程

1. 新建分支：`feat/...`、`fix/...`、`docs/...`
2. 保持提交粒度小且信息清晰
3. 提交前执行：
   - `python -m py_compile main.py src/*.py scripts/*.py`
   - `python scripts/regression_smoke.py`
4. 发起 PR 并填写模板

## 代码风格

- 优先可读性，避免过度抽象
- 不提交本地运行产物（日志、向量库、私有文档）
- 与现有目录结构和命名保持一致

## 报告问题

- 使用 Issue 模板提交
- 提供复现步骤、预期行为、实际行为和运行环境

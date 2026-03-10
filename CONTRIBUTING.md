# Contributing to NebulaVault

感谢你对 NebulaVault (星澜知库) 的贡献！作为一个纯本地的 RAG 系统，我们非常看重代码的稳定性、隐私安全以及交互的流畅度。

## 开发前准备

1. **环境**: 使用 Python 3.13 (目前 `chromadb` 对 3.14 兼容性欠佳)。
2. **依赖**: `pip install -r requirements.txt`。
3. **模型**: 确保本地 `Ollama` 已启动，并 `pull` 了必要的模型 (如 `qwen3:8b`, `bge-large-zh-v1.5`)。
4. **测试**: 如果涉及前端修改，请确保在 Chrome 环境下验证。

## 提交流程

1. **分支策略**: 
   - `feat/xxx`: 新功能
   - `fix/xxx`: 修复 Bug
   - `docs/xxx`: 文档更新
   - `refactor/xxx`: 代码重构
2. **原子提交**: 保持每笔 commit 的粒度清晰，包含简洁明了的 message。
3. **自测要求**: 
   - 提交前请运行 `python scripts/regression_smoke.py` 进行基础烟雾测试。
   - 涉及 RAG 逻辑变更，由于模型输出有随机性，请提供至少 3 组对比 case 截图。

## 代码风格与规范

- **交互逻辑**: 严禁在 AI 推理过程中（`isProcessing=true`）允许可能导致状态冲突的操作。
- **资源清理**: 所有新增的 API 或后端逻辑必须考虑资源释放，避免内存或僵尸进程。
- **可读性**: 优先使用语义化的变量名，复杂 RAG 算法需附带简要 Markdown 流程图或注释。
- **禁止提交**: 严禁将 `chroma_db/`, `sessions/*.json`, `logs/*.log` 等私有数据提交至 Git。

## 报告问题

- 使用 GitHub Issues 模板。
- **重中之重**: 必须附带后端 `server.log` 中的 Error Stack Trace，以及前端控制台的错误截图。

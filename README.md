# 🌌 星澜知库 NebulaVault - 纯本地知识库问答系统

![Python](https://img.shields.io/badge/python-3.13+-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Status](https://img.shields.io/badge/status-active-success)
![PRs](https://img.shields.io/badge/PRs-welcome-brightgreen)

基于 LangChain + ChromaDB + Ollama 的本地 RAG 系统，支持多格式文档索引、流式问答、多会话与会话记忆。

> [!NOTE]
> **毕业论文研究进展**: 本项目目前正作为毕业论文实验平台。关于 RRF 混合检索优化及自动化评估（EncouRAGe）的详细记录，请参阅 [THESIS_PROGRESS.md](./THESIS_PROGRESS.md)。

## 特性

- 纯本地运行，数据不出本机
- 混合检索（Vector + BM25 + 重排序）
- 多格式文档（PDF、DOCX、TXT、MD、CSV、HTML、图片 OCR）
- **技能引擎（Skills System）**：支持全局技能与按需检索技能（递归目录扫描）
- **双重记忆（Memory System）**：支持基于会话的提炼记忆与全局固定记忆
- **智能会话排队**：AI 响应期间自动排队切换请求，完成后无缝跳转
- Web UI + CLI + Gradio
- 增量索引（基于文件修改时间）
- 流式响应（SSE）

## 环境要求

- Python 3.13（`chromadb` 当前与 3.14 不兼容）
- 已安装并运行 Ollama
- 至少拉取一个模型（默认 `qwen3:8b`）

## 快速开始

```bash
# 1) 创建环境并安装依赖
python3.13 -m venv .venv313
source .venv313/bin/activate
pip install -r requirements.txt

# 2) 准备模型
ollama pull qwen3:8b

# 3) 启动服务（带热重载）
python main.py
```

浏览器访问：`http://127.0.0.1:8000`

## 目录说明

```text
.
├── main.py
├── src/
├── static/
├── docs/       # 待索引文档目录
├── skills/     # 技能定义（.txt），根目录下为全局技能，子目录下为检索技能
├── sessions/   # 会话历史
├── memory/     # 提炼记忆（global_memory.json 为全局记忆）
└── chroma_db/  # 向量库（运行时生成）
```

## 高级功能说明

### 1. 技能引擎 (Skills System)
- **全局技能**：放置在 `skills/` 根目录下的 `.txt` 文件（如 `global_rules.txt`），会对所有提问生效。
- **检索技能**：放置在 `skills/` 子目录下的文件，仅当问题触发相关意图时才会被检索并注入 Prompt。
- **原子性**：技能文件在索引时被视为独立原子，确保指令完整性。

### 2. 记忆系统 (Memory System)
- **会话记忆**：点击“存为记忆”可提炼当前会话精华并保存到 `memory/`。
- **全局记忆**：在 `memory/global_memory.json` 中定义的数据将作为 LLM 的长期背景知识。

### 3. 前端交互
- **自动排队切换**：在 AI 流式输出时，您可以点击切换会话，系统将自动进入“排队状态”，并在当前回复结束后自动跳转。
- **流畅滚动**：采用 `overflow-anchor` 技术，确保长文本输出时滚动极为平滑。

## 环境变量

| 变量 | 默认值 | 说明 |
|---|---|---|
| `RAG_API_KEY` | 运行时随机生成 | API 鉴权密钥，建议显式设置固定值 |
| `RAG_LLM_MODEL` | `qwen3:8b` | Ollama 模型名 |
| `RAG_EMBED_MODEL` | `BAAI/bge-large-zh-v1.5` | Embedding 模型 |
| `OLLAMA_HOST` | `http://127.0.0.1:11434` | Ollama 地址 |
| `RAG_DOCS_DIR` | `./docs` | 文档目录 |
| `RAG_CHROMA_DIR` | `./chroma_db` | 向量库目录 |

## 常用命令

```bash
# Web 服务
python main.py

# CLI
python scripts/cli.py

# Gradio
python scripts/gui.py
```

## API（核心）

| 端点 | 方法 | 说明 |
|---|---|---|
| `/api/status` | GET | 系统状态 |
| `/api/health` | GET | 健康检查 |
| `/api/index` | POST | 构建/更新索引（SSE） |
| `/api/query` | POST | 问答（SSE） |
| `/api/upload` | POST | 上传文件 |
| `/api/files` | GET | 文件树 |
| `/api/sessions` | GET/POST | 会话管理 |

## 回归测试

```bash
# Mock 回归（不依赖真实模型）
python scripts/regression_smoke.py

# 真实联调回归（调用真实 Ollama）
python scripts/regression_real_ollama.py
```

## Docker

```bash
docker build -t localrag:latest .
docker run --rm -p 8000:8000 \
  -e RAG_API_KEY=your-token \
  -e OLLAMA_HOST=http://host.docker.internal:11434 \
  localrag:latest
```

注意：容器内访问宿主 Ollama 时，macOS/Windows 可用 `host.docker.internal`。

## License

MIT

## 参与贡献

- 贡献指南见 [CONTRIBUTING.md](./CONTRIBUTING.md)
- 行为准则见 [CODE_OF_CONDUCT.md](./CODE_OF_CONDUCT.md)
- 安全报告见 [SECURITY.md](./SECURITY.md)
# NebulaVault

# NebulaVault 毕设改进计划书（基于文献调研）

目标：将当前系统改造成“可论文验证 + 可复现 + 可答辩演示”的毕业设计成果，覆盖检索、代理、记忆、评测与部署五个方向。

## 1. 改进目标与验收标准

### 1.1 目标
- 混合检索在真实数据集上显著优于向量检索基线。
- 代理与技能机制具备稳定的意图路由与回退能力。
- 记忆机制可控、可解释、可衰减，支持跨会话稳定性。
- 评测体系可复现，包含自动与人工两类指标。
- 本地部署在受限硬件下可运行，性能指标达标。

### 1.2 验收标准
- 以固定测试集得到完整 Exp-A~F 实验结果与统计检验。
- 评测日志可回放，实验配置、硬件与结果一一对应。
- 论文中所有结论可被实验日志与脚本复现。

## 2. 技术改进路线

### 2.1 混合检索与重排序
- 固化混合检索模式：`vector_only` / `ensemble` / `rrf`（代码位置：`src/retriever.py`）。
- 调整 RRF 参数与权重，形成明确的参数表与默认值（记录到 `experiments/config.yaml`）。
- 明确是否启用独立 Reranker，若无则在配置中标注为 `none`。
- 输出对比实验：BM25-only、Vector-only、Vector+BM25、Vector+BM25+RRF（评测脚本：`scripts/evaluate.py`）。

### 2.2 代理与技能机制
- 引入“按需检索”意图路由：仅在需要时触发检索链路（建议位置：`src/engine.py` 的意图提取与检索触发逻辑）。
- 设定技能调用规范：工具描述统一、语义中立，避免提示偏置（文档规范新增：`docs/skills_spec.md`）。
- 建立回退策略：检索低置信度时触发二次检索或替代技能（日志字段加入 `fallback_triggered`）。

### 2.3 记忆与见解蒸馏
- 采用碎片化记忆结构（Fragment-then-Compose），输出统一 JSON 结构（建议位置：`memory/` 与 `src/engine.py`）。
- 为记忆增加时间戳与衰减因子，优先使用近期信息（新增字段：`created_at`, `decay_score`）。
- 明确记忆写入时机、淘汰策略与冲突处理方式（文档规范新增：`docs/memory_spec.md`）。

### 2.4 评测与统计
- 扩展测试集至 60 条（factual/summary/cross-doc 各 20），更新 `experiments/question_set.md`。
- 引入自动评测（LLM-as-a-Judge）与人工评分并行（脚本：`scripts/evaluate.py`）。
- 对关键指标进行显著性检验，记录均值与置信区间（新增汇总脚本：`scripts/aggregate_results.py`）。
- 统一日志字段（见 `experiments/log_schema.json`），补齐人工评分字段。

### 2.5 本地部署与性能
- 固化硬件与软件版本（`experiments/hardware.md`）。
- 记录 TTFT、TTR、CPU、MEM 等性能指标（输出到 `experiments/results/`）。
- 明确模型量化或降级策略作为兜底方案（文档规范新增：`docs/deploy_spec.md`）。

## 3. 实施计划（12 周）

### 第 1-2 周：目标对齐与基线固化
- 固化实验配置、日志规范、硬件记录（文件：`experiments/config.yaml`, `experiments/log_schema.json`, `experiments/hardware.md`）。
- 完成向量检索基线测试与日志输出（脚本：`scripts/evaluate.py`）。

### 第 3-5 周：混合检索与重排序验证
- 实现 RRF、权重与参数表（记录默认值到 `experiments/config.yaml`）。
- 完成 BM25-only 与混合检索对照实验（输出到 `experiments/results/`）。

### 第 6-7 周：代理与技能机制
- 落地按需检索的意图路由（代码与日志标记）。
- 定义技能描述规范与回退策略（新增 `docs/skills_spec.md`）。

### 第 8-9 周：记忆与蒸馏机制
- 实现碎片化记忆结构与时间衰减（新增 `docs/memory_spec.md`）。
- 验证跨会话一致性与记忆效果（新增最小可复现实验记录）。

### 第 10-11 周：评测完善与统计分析
- 完成 60 条问题集与人工评价（更新 `experiments/question_set.md`）。
- 输出统计检验与置信区间（新增 `scripts/aggregate_results.py` 输出汇总表）。

### 第 12 周：论文收尾与答辩准备
- 补齐图表与实验日志引用。
- 完成答辩 PPT 与演示脚本。

## 4. 交付物清单
- 实验配置、硬件记录、日志规范与结果文件（`experiments/`）。
- 完整评测数据与统计检验结果。
- 论文与答辩材料（PPT + 演示脚本）。
 - 设计规范与实现说明（`docs/skills_spec.md`, `docs/memory_spec.md`, `docs/deploy_spec.md`）。

## 5. 风险与应对
- 模型性能不足：启用轻量模型与降级策略。
- 数据不足：扩充问题集与文档规模。
- 评测不可复现：严格按日志规范与配置执行。

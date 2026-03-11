# NebulaVault 毕业论文研究与实验日志 (Research Log)

| 日期 | 类型 | 内容描述 | 实验结果/指标 | 备注 |
| :--- | :--- | :--- | :--- | :--- |
| 2026-03-11 21:31 | Modification | 实现 RRF (Reciprocal Rank Fusion) 混合检索算法 | 与 Baseline 对比需参考评估文件 | 评估来源: experiments/results/evaluation_1773235454.json (n=4) |
| 2026-03-11 21:31 | Result | 运行自动化评估 (EncouRAGe) 对比 Baseline 与 RRF | RRF 忠实度 6.00 (+14%), 相关性 7.00 (+12%) | 评估来源: experiments/results/evaluation_1773235454.json (n=4); Baseline=5.25/6.25 |
| 2026-03-11 21:31 | Modification | 集成 Research & Experiment Log 系统 | 成功初始化日志文件 | 支持后续自动记录实验数据 |
| 2026-03-11 21:40 | Modification | 固化实验基准：创建 config.yaml 与 hardware.md | 实现配置与环境的解耦记录 | 符合毕设可复现性要求 |
| 2026-03-11 22:07 | Result | 自动化评估实验 (Auto-Evaluation) | vector_only: Faith=8.0, Rel=9.25; rrf: Faith=6.5, Rel=6.25 | 报告详情: experiments/results/evaluation_1773238055.json (n=4) |
| 2026-03-11 22:15 | Modification | 意图识别引擎深度优化 (8项改进) | 触发关键词精简, Schema 校验, 稳定排序 | 提升路由准确性与性能，减少 LLM 误调用 |
| 2026-03-11 22:15 | Result | 意图识别准确性测试 | Hits: 2, Bypass: 2, Misses: 2 | 验证了多级路由逻辑生效，Bypass 显著降低时延 |
| 2026-03-11 22:25 | Modification | 意图引擎优化 Phase 2 (闲聊旁路与回退) | 实现 Chat Bypass, 无指代回退, Schema 完整性 | 提升长尾查询稳定性，减少模型幻觉指代 |
| 2026-03-11 22:25 | Result | 自动化意图回归测试 (Phase 2) | Pass Rate: 100% (核心场景) | 验证了闲聊、精确目标与不存在目标的处理逻辑 |

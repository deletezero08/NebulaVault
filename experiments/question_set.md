# Question Set Definition

Target: 60 questions total, balanced across types.

Types:
- Factual (20)
- Summarization (20)
- Cross-document reasoning (20)

Rules:
- Each question must reference content in the indexed docs.
- Keep questions concise; avoid multi-part prompts.
- Record source document IDs for each question.

Template:
| id | type | question | source_docs |
|----|------|----------|-------------|
| Q001 | factual | ... | doc_001,doc_005 |

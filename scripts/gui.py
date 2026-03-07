import os
import sys
from pathlib import Path

# Add project root to sys.path for internal imports
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import gradio as gr
from src.engine import LocalRAG


def render_status(rag):
    status = rag.get_status()
    index_state = "已加载" if status["has_index"] else "未建立"
    doc_files = rag.list_doc_files()
    doc_list = "\n".join(f"- {name}" for name in doc_files) if doc_files else "- 暂无文档"
    formats = ", ".join(status.get("supported_formats", []))
    return (
        f"模型: `{status['llm_model']}`\n\n"
        f"Embedding: `{status['embed_model']}`\n\n"
        f"文档数量: `{status['doc_count']}`\n\n"
        f"索引状态: `{index_state}`\n\n"
        f"支持格式: `{formats}`\n\n"
        f"文档目录: `{status['docs_dir']}`\n\n"
        f"向量库目录: `{status['chroma_dir']}`\n\n"
        f"当前文档:\n{doc_list}"
    )


def create_app(rag):
    def rebuild_index(progress=gr.Progress()):
        progress(0, desc="正在索引文档...")
        result = rag.index_docs()
        progress(1, desc="完成")
        if result["ok"]:
            files = "\n".join(f"- {name}" for name in result["doc_files"])
            message = (
                f"索引完成。\n\n"
                f"片段数: `{result['chunk_count']}`\n\n"
                f"已处理文件:\n{files}"
            )
        else:
            message = result["message"]
        return message, render_status(rag)

    def ask_question(question, progress=gr.Progress()):
        question = (question or "").strip()
        if not question:
            return "请输入问题。", ""

        progress(0, desc="正在思考...")
        result = rag.query(question)
        progress(1, desc="完成")
        sources = "\n".join(f"- {item}" for item in result["sources"]) if result["sources"] else "无"
        answer = result["answer"]
        return answer, sources

    with gr.Blocks(title="星澜知库 NebulaVault") as demo:
        gr.Markdown("# 星澜知库 NebulaVault")
        gr.Markdown("索引本地文档（PDF / Word / TXT / MD / CSV / HTML），使用本机 Ollama 模型问答。")

        with gr.Row():
            status_box = gr.Markdown(render_status(rag))
            index_output = gr.Markdown('点击"重建索引"开始。')

        rebuild_btn = gr.Button("重建索引", variant="primary")
        rebuild_btn.click(rebuild_index, outputs=[index_output, status_box])

        question_box = gr.Textbox(label="问题", placeholder="输入你想问文档的问题")
        ask_btn = gr.Button("提问")
        answer_box = gr.Markdown(label="回答")
        sources_box = gr.Markdown(label="参考来源")

        ask_btn.click(ask_question, inputs=[question_box], outputs=[answer_box, sources_box])
        question_box.submit(ask_question, inputs=[question_box], outputs=[answer_box, sources_box])

    return demo


if __name__ == "__main__":
    rag = LocalRAG()
    demo = create_app(rag)
    demo.launch(server_name="127.0.0.1", server_port=7860, inbrowser=True)

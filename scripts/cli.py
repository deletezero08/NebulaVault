import os
import sys
from pathlib import Path

# Add project root to sys.path for internal imports
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.engine import LocalRAG


def main():
    rag = LocalRAG()

    while True:
        print("\n" + "=" * 50)
        print("📚 星澜知库 NebulaVault")
        print("=" * 50)
        print("1. 📥 建立/刷新文档索引")
        print("2. ❓ 向文档提问")
        print("3. 🚪 退出")

        choice = input("\n请选择 (1/2/3): ").strip()

        if choice == "1":
            result = rag.index_docs()
            print(result["message"])
        elif choice == "2":
            question = input("\n请输入问题: ").strip()
            if question:
                result = rag.query(question)
                print(f"\n🤖 回答:\n{result['answer']}")
                if result["sources"]:
                    print("\n📎 参考片段:")
                    for source in result["sources"]:
                        print(f"- {source}")
        elif choice == "3":
            print("👋 再见！")
            return 0


if __name__ == "__main__":
    raise SystemExit(main())

from mem0 import Memory
from mem0.configs.base import MemoryConfig
import os


DB_PATH = os.getenv("MEM0_DB_PATH", "./mem0_db")
GRAPH_PATH = os.getenv("MEM0_GRAPH_PATH", "./mem0_graph.kuzu")


def build_memory():
    """
    使用与 main.py 相同的配置构建 Memory 实例。
    这样自检脚本与正式导入共享同一套向量库和图谱库。
    """
    config = {
        "vector_store": {"provider": "chroma", "config": {"path": DB_PATH}},
        "graph_store": {"provider": "kuzu", "config": {"db": GRAPH_PATH}},
        "llm": {"provider": "ollama", "config": {"model": "mythomax-l2-13b"}},
        "embedder": {"provider": "ollama", "config": {"model": "nomic-embed-text"}},
    }
    return Memory(MemoryConfig(**config))


def run_graph_health_check():
    """
    向 Mem0 写入几句极简关系句子，用于验证 Kuzu 图谱是否会产生 Entity 节点。
    """
    memory = build_memory()

    user_id = "default"
    agent_id = "graph_test"

    samples = [
        "姜望认识宇文铎。",
        "宇文铎是人族修士。",
        "姜望从宇文铎那里得到一份舆图。",
    ]

    print("=== Graph Health Check: 开始写入测试关系句子到 Mem0 ===")
    for idx, s in enumerate(samples, start=1):
        memory.add(s, user_id=user_id, agent_id=agent_id)
        print(f"  - 已写入测试句子 {idx}: {s}")

    print("\n✅ 自检写入完成。")
    print(
        "现在请运行 `uv run view_graph.py`，检查是否出现带有 agent_id=graph_test 的 Entity 节点。"
    )


if __name__ == "__main__":
    run_graph_health_check()

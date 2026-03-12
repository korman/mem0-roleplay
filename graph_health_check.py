from mem0 import Memory
from mem0.configs.base import MemoryConfig
import os


DB_PATH = os.getenv("MEM0_DB_PATH", "./mem0_db")


def build_memory():
    """
    使用与 main.py 相同的配置构建 Memory 实例。
    这样自检脚本与正式导入共享同一套向量库和图谱库。
    当前仅使用向量记忆（Graph Memory 已关闭）。
    """
    config = {
        "vector_store": {"provider": "chroma", "config": {"path": DB_PATH}},
        # 自检脚本也只验证向量写入，不再触发 Graph Memory
        # "graph_store": {"provider": "kuzu", "config": {"db": GRAPH_PATH}},
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
        "（当前 Graph Memory 已关闭：本自检仅确认向量写入是否成功，不再检查图谱节点）"
    )


if __name__ == "__main__":
    run_graph_health_check()

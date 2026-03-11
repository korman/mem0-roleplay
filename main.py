# main.py  （直接覆盖）
from mem0 import Memory
from mem0.configs.base import MemoryConfig
import ollama
import os
import re
import sys

# 数据路径可配置（跨设备友好）
DB_PATH = os.getenv("MEM0_DB_PATH", "./mem0_db")
GRAPH_PATH = os.getenv("MEM0_GRAPH_PATH", "./mem0_graph.kuzu")

config = {
    "vector_store": {"provider": "chroma", "config": {"path": DB_PATH}},
    "graph_store": {"provider": "kuzu", "config": {"db": GRAPH_PATH}},
    "llm": {"provider": "ollama", "config": {"model": "qwen2.5:14b"}},
    "embedder": {"provider": "ollama", "config": {"model": "nomic-embed-text"}},
}

memory = Memory(MemoryConfig(**config))
LLM_MODEL = config["llm"]["config"]["model"]

# 单段字数上限（长章分段）
CHUNK_MAX_CHARS = 6000

# Kuzu 图存储要求 filters 中必须有 user_id，与 agent_id 一起使用
USER_ID = "default"


# ==================== 一键初始化角色（改成你的书和女主角） ====================
def init_character(txt_path, book_name, character_name, force_reinit=False):
    agent_id = f"{book_name}_{character_name}"

    if not os.path.exists(txt_path):
        print("❌ 小说文件没找到！")
        print(
            "请将 main.py 中的 txt_path 改为实际小说路径，或通过环境变量 NOVEL_TXT_PATH 传入。"
        )
        return None

    try:
        with open(txt_path, "r", encoding="utf-8") as f:
            text = f.read()
    except FileNotFoundError:
        print("❌ 小说文件没找到！")
        print(
            "请将 main.py 中的 txt_path 改为实际小说路径，或通过环境变量 NOVEL_TXT_PATH 传入。"
        )
        return None
    except UnicodeDecodeError as e:
        print(f"❌ 文件编码错误，请检查是否为 UTF-8：{e}")
        return None

    # 重复初始化防护：若已有该角色记忆则跳过章节导入
    if not force_reinit:
        try:
            search_out = memory.search(
                query=book_name, user_id=USER_ID, agent_id=agent_id, limit=1
            )
            existing = (
                search_out.get("results", [])
                if isinstance(search_out, dict)
                else search_out
            )
            if existing:
                print(
                    f"⚠️ 该角色已初始化，跳过章节导入。若需重新导入请使用 force_reinit=True。"
                )
                memory.add(
                    f"你是《{book_name}》里的 {character_name}，严格按照书中你的性格、说话方式和所有经历来回应。",
                    user_id=USER_ID,
                    agent_id=agent_id,
                )
                print(f"✅ {character_name} 人格记忆已更新")
                return agent_id
        except Exception as e:
            print(f"⚠️ 检查已有记忆时出错，继续导入：{e}")

    print(f"正在导入《{book_name}》并为 {character_name} 构建记忆 + 图谱...")

    # 按「第X章」分章（兼容中文数字与阿拉伯数字）
    chapters = re.split(r"第[一二三四五六七八九十百千零\d]+章", text)
    chapter_num = 0
    for i, chap in enumerate(chapters):
        chap = chap.strip()
        if len(chap) <= 300:
            continue
        chapter_num += 1
        # 按单段上限切分
        for seg_idx in range(0, len(chap), CHUNK_MAX_CHARS):
            segment = chap[seg_idx : seg_idx + CHUNK_MAX_CHARS]
            if len(segment.strip()) < 50:
                continue
            try:
                memory.add(
                    f"第{chapter_num}章（部分{seg_idx // CHUNK_MAX_CHARS + 1}）：{segment}",
                    user_id=USER_ID,
                    agent_id=agent_id,
                    metadata={
                        "book": book_name,
                        "chapter": chapter_num,
                        "segment_index": seg_idx // CHUNK_MAX_CHARS,
                    },
                )
            except Exception as e:
                print(f"⚠️ 写入第{chapter_num}章片段时出错：{e}")

    # 核心人格记忆（让第一句就很像原著）
    try:
        memory.add(
            f"你是《{book_name}》里的 {character_name}，严格按照书中你的性格、说话方式和所有经历来回应。",
            user_id=USER_ID,
            agent_id=agent_id,
        )
    except Exception as e:
        print(f"⚠️ 写入人格记忆时出错：{e}")
        return None

    print(f"✅ {character_name} 初始化完成！记忆和 Kuzu 图谱已就绪")
    return agent_id


# 固定人格描述（与 init_character 中的人格记忆一致，保证「你是谁」稳定）
def _system_prompt(agent_id):
    character_name = agent_id.split("_")[-1]
    return f"你是书中的 {character_name}，严格按照书中你的性格、说话方式和经历来回应。"


# ==================== 聊天（记忆驱动） ====================
def chat(agent_id, user_input, turn_id=None):
    try:
        search_out = memory.search(
            query=user_input, user_id=USER_ID, agent_id=agent_id, limit=5
        )
        relevant = (
            search_out.get("results", [])
            if isinstance(search_out, dict)
            else search_out
        )
    except Exception as e:
        print(f"⚠️ 检索记忆时出错：{e}")
        relevant = []
    context = "\n".join([m.get("memory", m.get("text", str(m))) for m in relevant])
    ref_block = f"参考记忆：\n{context}\n\n" if context else ""

    system_content = _system_prompt(agent_id) + "\n\n" + ref_block

    try:
        response = ollama.chat(
            model=LLM_MODEL,
            messages=[
                {"role": "system", "content": system_content.strip()},
                {"role": "user", "content": user_input},
            ],
        )["message"]["content"]
    except Exception as e:
        print(f"⚠️ 调用 Ollama 失败，请确认已启动 Ollama 并拉取模型 {LLM_MODEL}：{e}")
        return None

    try:
        meta = {"type": "conversation"}
        if turn_id is not None:
            meta["turn_id"] = turn_id
        memory.add(
            f"用户：{user_input}\n你：{response}",
            user_id=USER_ID,
            agent_id=agent_id,
            metadata=meta,
        )
    except Exception as e:
        print(f"⚠️ 写入对话记忆时出错：{e}")

    return response


def _check_ollama():
    """启动时检查 Ollama 是否可用。"""
    try:
        ollama.list()
        return True
    except Exception as e:
        print(f"⚠️ Ollama 不可用（请先启动 Ollama 并拉取模型 {LLM_MODEL}）：{e}")
        return False


# ==================== 使用示例 ====================
if __name__ == "__main__":
    # 小说路径：环境变量 NOVEL_TXT_PATH > 命令行参数 > 默认占位
    txt_path = os.getenv("NOVEL_TXT_PATH")
    if not txt_path and len(sys.argv) > 1:
        txt_path = sys.argv[1]
    if not txt_path:
        txt_path = "小城恋歌.txt"  # 把小说拖进来改名

    if not _check_ollama():
        sys.exit(1)

    agent_id = init_character(
        txt_path=txt_path,
        book_name="小城恋歌",
        character_name="林晓薇",
    )

    if agent_id:
        print("\n🎉 角色已活！开始聊天吧（输入 '退出' 结束）")
        turn_id = 0
        while True:
            msg = input("\n你（男主角）：")
            if msg in ["退出", "exit", "quit"]:
                break
            turn_id += 1
            reply = chat(agent_id, msg, turn_id=turn_id)
            if reply is not None:
                print(f"她：{reply}")
            else:
                print("（本轮无回复，请检查 Ollama）")

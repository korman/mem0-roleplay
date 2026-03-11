# main.py  （完整防幻觉加强版 - 可直接运行）
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
    "llm": {"provider": "ollama", "config": {"model": "mythomax-l2-13b"}},
    "embedder": {"provider": "ollama", "config": {"model": "nomic-embed-text"}},
}

memory = Memory(MemoryConfig(**config))
LLM_MODEL = config["llm"]["config"]["model"]

CHUNK_MAX_CHARS = 6000
USER_ID = "default"


# ==================== 一键初始化角色（完整函数） ====================
def init_character(txt_path, book_name, character_name, force_reinit=False):
    agent_id = f"{book_name}_{character_name}"

    if not os.path.exists(txt_path):
        print("❌ 小说文件没找到！")
        return None

    try:
        with open(txt_path, "r", encoding="utf-8") as f:
            text = f.read()
    except Exception as e:
        print(f"❌ 读取小说失败：{e}")
        return None

    # 重复初始化防护
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
                    f"⚠️ 该角色已初始化，跳过章节导入。若要重新导入请把 force_reinit=True"
                )
                return agent_id
        except:
            pass

    print(f"正在导入《{book_name}》并为 {character_name} 构建记忆 + 图谱...")

    # 分章
    chapters = re.split(r"第[一二三四五六七八九十百千零\d]+章", text)
    chapter_num = 0
    for i, chap in enumerate(chapters):
        chap = chap.strip()
        if len(chap) <= 300:
            continue
        chapter_num += 1
        for seg_idx in range(0, len(chap), CHUNK_MAX_CHARS):
            segment = chap[seg_idx : seg_idx + CHUNK_MAX_CHARS]
            if len(segment.strip()) < 50:
                continue
            memory.add(
                f"第{chapter_num}章（部分{seg_idx // CHUNK_MAX_CHARS + 1}）：{segment}",
                user_id=USER_ID,
                agent_id=agent_id,
                metadata={"book": book_name, "chapter": chapter_num},
            )

    # 核心人格记忆
    memory.add(
        f"你是《{book_name}》里的 {character_name}，严格按照书中你的性格、说话方式和所有经历来回应。",
        user_id=USER_ID,
        agent_id=agent_id,
    )

    print(f"✅ {character_name} 初始化完成！记忆和 Kuzu 图谱已就绪")
    return agent_id


# ==================== 超级严格的系统提示（防幻觉核心） ====================
def _system_prompt(agent_id):
    character_name = agent_id.split("_")[-1]
    return f"""你是《赤心巡天》里的男主角 {character_name}。
【铁律 - 必须严格遵守，否则就是错误回答】
1. 你只能使用下面「参考记忆」里出现的具体内容来回答，绝不能添加、编造、猜测任何书中没有出现过的对话、动作、场景、细节或情节。
2. 如果参考记忆里没有相关信息，就回答“我不太记得了”或“书里没提到这件事”。
3. 严格保持书中你的性格和说话方式，但绝不发挥创意。
4. 永远沉浸在角色中，不要打破第四面墙。"""


# ==================== 聊天函数（记忆驱动 + 强约束） ====================
def chat(agent_id, user_input, turn_id=None):
    try:
        search_out = memory.search(
            query=user_input, user_id=USER_ID, agent_id=agent_id, limit=8
        )
        relevant = (
            search_out.get("results", [])
            if isinstance(search_out, dict)
            else search_out
        )
    except Exception as e:
        print(f"⚠️ 检索记忆时出错：{e}")
        relevant = []

    context = "\n".join(
        [f"- {m.get('memory', m.get('text', str(m)))}" for m in relevant]
    )
    ref_block = (
        f"【书中参考记忆 - 这是你唯一可以使用的内容】\n{context}\n\n" if context else ""
    )

    system_content = (
        _system_prompt(agent_id)
        + "\n\n"
        + ref_block
        + "现在请严格按照以上记忆自然回应用户的问题："
    )

    try:
        response = ollama.chat(
            model=LLM_MODEL,
            messages=[
                {"role": "system", "content": system_content.strip()},
                {"role": "user", "content": user_input},
            ],
            options={"temperature": 0.6, "top_p": 0.9},
        )["message"]["content"]
    except Exception as e:
        print(f"⚠️ 调用 Ollama 失败：{e}")
        return None

    memory.add(
        f"用户：{user_input}\n你：{response}", user_id=USER_ID, agent_id=agent_id
    )
    return response


def _check_ollama():
    try:
        ollama.list()
        return True
    except Exception as e:
        print(f"⚠️ Ollama 不可用：{e}")
        return False


# ==================== 启动 ====================
if __name__ == "__main__":
    txt_path = os.getenv("NOVEL_TXT_PATH")
    if not txt_path and len(sys.argv) > 1:
        txt_path = sys.argv[1]
    if not txt_path:
        txt_path = "赤心巡天.txt"  # ← 默认读取《赤心巡天》

    if not _check_ollama():
        sys.exit(1)

    agent_id = init_character(
        txt_path=txt_path,
        book_name="赤心巡天",
        character_name="姜望",
        force_reinit=True,  # ← 强制重新导入，确保新 prompt 生效
    )

    if agent_id:
        print("\n🎉 角色已活！开始聊天吧（输入 '退出' 结束）")
        turn_id = 0
        while True:
            msg = input("\n你：")
            if msg in ["退出", "exit", "quit"]:
                break
            turn_id += 1
            reply = chat(agent_id, msg, turn_id=turn_id)
            if reply is not None:
                print(f"{'姜望'}：{reply}")
            else:
                print("（本轮无回复，请检查 Ollama）")

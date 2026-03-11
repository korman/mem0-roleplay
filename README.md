## mem0-roleplay：基于小说记忆图谱的防幻觉角色扮演

`mem0-roleplay` 是一个基于 [Mem0](https://docs.mem0.ai)、Kuzu 图数据库和 Ollama 的**小说角色扮演与记忆图谱实验项目**。

它可以：
- 从整本小说（TXT）中自动导入章节内容，构建向量记忆与关系图谱；
- 将某个角色“活起来”，与你进行持续对话；
- 使用**强约束 System Prompt + 检索记忆**的方式，尽量避免模型胡编乱造（防幻觉）；
- 通过命令行脚本快速查看 Kuzu 图数据库中的节点和关系结构。

当前默认示例基于测试小说 `小城恋歌.txt` 和女主角 **林晓薇**，你可以很容易替换成任意中文小说与角色。

---

## 目录

- [项目概述](#项目概述)
- [核心功能](#核心功能)
- [项目结构](#项目结构)
- [环境与依赖](#环境与依赖)
- [安装与运行](#安装与运行)
  - [1. 准备环境](#1-准备环境)
  - [2. 安装依赖](#2-安装依赖)
  - [3. 准备小说文本](#3-准备小说文本)
  - [4. 初始化角色并开始聊天](#4-初始化角色并开始聊天)
  - [5. 查看记忆图谱](#5-查看记忆图谱)
- [核心 API / 函数说明](#核心-api--函数说明)
  - [`init_character`](#initcharactertxt_path-book_name-character_name-force_reinitfalse)
  - [`chat`](#chatagent_id-user_input-turn_idnone)
- [配置与自定义](#配置与自定义)
- [示例交互流程](#示例交互流程)
- [常见问题 FAQ](#常见问题-faq)
- [贡献指南](#贡献指南)

---

## 项目概述

`mem0-roleplay` 的目标是探索这样一个流程：

1. 给定一部小说 TXT 和一个角色名；
2. 自动分章、切片，将内容导入 Mem0 的**向量存储 + 图存储（Kuzu）**；
3. 定义一个**极其严格的系统提示**，要求模型仅凭“检索到的原文记忆”回答；
4. 用户从命令行与角色对话，并可以用脚本查看背后生成的记忆图谱。

---

## 核心功能

- **一键初始化角色**（`init_character`）
  - 支持整本小说 TXT 导入；
  - 自动按“第X章”粗分章节，并按长度切片写入 Mem0；
  - 为每段内容写入 `book`、`chapter` 等元数据；
  - 最后写入一条“人格记忆”，强调角色是谁、性格和经历。

- **防幻觉聊天**（`chat`）
  - 使用 `memory.search` 从 Mem0 中检索与当前问题最相关的 8 条记忆；
  - 将这些记忆组织成「【书中参考记忆 - 这是你唯一可以使用的内容】」的上下文；
  - 系统提示中写明**只能使用这些记忆内容回答**，不能编造新情节；
  - 若记忆不足，角色会倾向于说“我不太记得了”而非胡编。

- **记忆图谱查看**（`view_graph.py`）
  - 直接连接 Kuzu 数据库 `mem0_graph.kuzu`；
  - 列出图中的 `Entity` 节点及其 `user_id`、`agent_id`；
  - 显示 `CONNECTED_TO` 关系，直观查看谁与谁存在什么联系。

---

## 项目结构

```text
mem0-roleplay/
├─ main.py          # 主入口：初始化角色 + 防幻觉聊天逻辑
├─ view_graph.py    # 图谱查看脚本（Kuzu）
├─ 小城恋歌.txt     # 示例小说（需自行准备内容）
├─ pyproject.toml   # 项目依赖 & uv 配置
├─ README.md        # 本文档
└─ .gitignore
```

---

## 环境与依赖

### 运行环境

- 操作系统：Windows / macOS / Linux
- Python：**3.13+**（项目 `requires-python >=3.13`，推荐使用 [uv](https://github.com/astral-sh/uv) 管理虚拟环境）
- 已安装并可用的 **Ollama**（本地大模型服务）：
  - 需要准备的模型：
    - `qwen2.5:14b`（或你在 `main.py` 里配置的任意模型）
    - `nomic-embed-text`（作为 Embedding 模型）

### Python 依赖（来自 `pyproject.toml`）

```toml
[project]
dependencies = [
    "chromadb>=1.5.5",
    "kuzu>=0.11.3",
    "mem0ai>=1.0.5",
    "ollama>=0.6.1",
    "rank-bm25>=0.2.2",
]
```

---

## 安装与运行

### 1. 准备环境

确保本地已安装：

- Python 3.13+
- [uv](https://github.com/astral-sh/uv)
- [Ollama](https://ollama.ai) 并已拉取所需模型，例如：

```bash
ollama pull qwen2.5:14b
ollama pull nomic-embed-text
```

### 2. 安装依赖

```bash
cd c:/code/mem0-roleplay
uv sync
```

### 3. 准备小说文本

- 将你的小说 TXT 文件放到项目根目录；
- 当前示例默认文件名为：`小城恋歌.txt`，你可以：
  - 直接命名为 `小城恋歌.txt`，或
  - 使用命令行参数/环境变量覆盖（见下文）。

### 4. 初始化角色并开始聊天

#### 方式一：使用默认文件名

```bash
uv run main.py
```

`main.py` 中默认设定：

- 小说路径优先级：`NOVEL_TXT_PATH` 环境变量 > 第一个命令行参数 > 默认 `小城恋歌.txt`
- 默认角色：
  - `book_name="小城恋歌"`
  - `character_name="林晓薇"`
  - `agent_id="小城恋歌_林晓薇"`
  - `force_reinit=True`（方便开发测试时多次重导）

#### 方式二：命令行参数指定 TXT

```bash
uv run main.py 你的小说.txt
```

#### 方式三：环境变量指定 TXT

```powershell
$env:NOVEL_TXT_PATH = "C:/path/to/你的小说.txt"
uv run main.py
```

运行后，你会在控制台看到章节导入与“角色已活”的提示，然后可以直接在命令行中与角色对话（输入 `退出/exit/quit` 结束）。

### 5. 查看记忆图谱

初始化完成后，运行：

```bash
uv run python view_graph.py
```

脚本会：

- 连接 `./mem0_graph.kuzu`；
- 打印前 5 个 `Entity` 节点；
- 列出所有节点的 `name / user_id / agent_id`；
- 列出所有 `CONNECTED_TO` 关系。

如果输出中节点/关系为 0，通常说明：

- 小说太短，或缺少可抽取的实体关系；
- 或导入没有成功（可重新运行 `main.py` 并注意报错）。

---

## 核心 API / 函数说明

### `init_character(txt_path, book_name, character_name, force_reinit=False)`

**位置**：`main.py`  
**作用**：从 TXT 导入整本小说，分章切片后写入 Mem0，并为角色写入人格记忆，构建后续聊天和图谱所需的底层记忆。

核心行为：

- 读取 `txt_path`，整体加载为字符串；
- 用正则 `r"第[一二三四五六七八九十百千零\\d]+章"` 分章；
- 使用 `CHUNK_MAX_CHARS=6000` 对每章切片，过滤极短片段；
- 调用 `memory.add(...)` 写入：
  - `user_id="default"`
  - `agent_id=f"{book_name}_{character_name}"`
  - `metadata={"book": book_name, "chapter": chapter_num}`
- 最后写入一条人格记忆：
  - “你是《{book_name}》里的 {character_name}，严格按照书中你的性格、说话方式和所有经历来回应。”

当 `force_reinit=False` 时，会先用 `memory.search` 检查该 `agent_id` 是否已有记忆，若有则跳过重新导入。

---

### `chat(agent_id, user_input, turn_id=None)`

**位置**：`main.py`  
**作用**：基于 Mem0 中的记忆，构造带“铁律”的 System Prompt，通过 Ollama 生成防幻觉回复，并把本轮对话写入记忆。

逻辑概要：

1. 检索记忆：

```python
search_out = memory.search(
    query=user_input, user_id=USER_ID, agent_id=agent_id, limit=8
)
relevant = search_out.get("results", [])
context = "\n".join(
    [f"- {m.get('memory', m.get('text', str(m)))}" for m in relevant]
)
ref_block = (
    f"【书中参考记忆 - 这是你唯一可以使用的内容】\n{context}\n\n" if context else ""
)
```

2. 构造系统提示（铁律）：

```python
system_content = (
    _system_prompt(agent_id)
    + "\n\n"
    + ref_block
    + "现在请严格按照以上记忆自然回应用户的问题："
)
```

`_system_prompt` 中明确要求：

- 只能引用参考记忆中的内容；
- 不能编造新对话/动作/细节/情节；
- 记忆中没有就承认“记不太清了”；
- 保持角色性格但不过度发挥。

3. 调用 Ollama：

```python
response = ollama.chat(
    model=LLM_MODEL,
    messages=[
        {"role": "system", "content": system_content.strip()},
        {"role": "user", "content": user_input},
    ],
    options={"temperature": 0.6, "top_p": 0.9},
)["message"]["content"]
```

4. 记录对话：

```python
memory.add(
    f"用户：{user_input}\n你：{response}",
    user_id=USER_ID,
    agent_id=agent_id,
)
```

---

## 配置与自定义

你可以在 `main.py` 顶部修改：

- **模型配置**：`LLM_MODEL`、Embedding 模型；
- **存储路径**：`MEM0_DB_PATH`、`MEM0_GRAPH_PATH` 环境变量；
- **默认书名与角色名**：`book_name` / `character_name`；
- **防幻觉程度**：`_system_prompt` 中的规则内容与 `temperature` 参数。

---

## 示例交互流程

1. 把自己的小说重命名为 `小城恋歌.txt` 放到项目根目录；
2. 运行：

```bash
uv run main.py
```

3. 看到导入完成和“角色已活”的提示；
4. 在命令行中和角色（林晓薇）对话：

```text
你（男主角）：你还记得第一次见到我是在哪里吗？
她：...
```

当你问到书中未提及的内容时，角色会更偏向回答“记不太清了”或“书里没写”，而不是胡编。

---

## 常见问题 FAQ

**Q：为什么 `view_graph.py` 显示 0 节点/0 关系？**  
A：可能是：
- 小说太短或缺少有明确关系的剧情；
- 初始化导入过程出现错误（请检查 `main.py` 输出），重跑一遍试试。

**Q：为什么角色经常说“记不太清了”？**  
A：这是设计使然。系统提示要求模型**严格只使用检索到的记忆**，当检索结果不足或无关时，就会选择“不乱说”。

**Q：如何支持多本书、多角色？**  
A：可以为每本书/角色组合使用不同的 `book_name` / `character_name`，从而生成不同的 `agent_id`，再在启动代码中提供选择逻辑或命令行参数进行切换。

---

## 贡献指南

欢迎在此基础上继续扩展功能，例如：

- 支持多角色、多书切换；
- 将图谱导出为 JSON 并用前端可视化；
- 为不同类型的小说（推理、修仙、都市等）定制不同的防幻觉策略。

建议流程：

1. Fork 本仓库；
2. 新建分支进行开发；
3. 提交 PR，简要说明改动内容、动机和使用方式。

如有问题或改进建议，欢迎在 Issue 中讨论。

## Mem0 + Kuzu 图谱配置示例

下面是两套典型配置，方便你根据实际环境选择。

---

### 方案 A：全部使用 Ollama（当前代码正在使用）

```python
DB_PATH = os.getenv("MEM0_DB_PATH", "./mem0_db")
GRAPH_PATH = os.getenv("MEM0_GRAPH_PATH", "./mem0_graph.kuzu")

config = {
    "vector_store": {"provider": "chroma", "config": {"path": DB_PATH}},
    "graph_store": {"provider": "kuzu", "config": {"db": GRAPH_PATH}},
    "llm": {"provider": "ollama", "config": {"model": "mythomax-l2-13b"}},
    "embedder": {"provider": "ollama", "config": {"model": "nomic-embed-text"}},
}
memory = Memory(MemoryConfig(**config))
```

> 说明：  
> - 对话、图谱抽取都走同一个 Ollama LLM。  
> - 如果你确认当前 Mem0 版本允许用非 OpenAI 模型做 Graph 抽取，可以直接使用本方案。  

---

### 方案 B：对话用 Ollama，图谱抽取单独使用 OpenAI 兼容 LLM

有些 Mem0 版本要求 Graph Memory 使用支持 OpenAI tool-calling 的模型，这时可以为 `graph_store` 单独配置 LLM：

```python
DB_PATH = os.getenv("MEM0_DB_PATH", "./mem0_db")
GRAPH_PATH = os.getenv("MEM0_GRAPH_PATH", "./mem0_graph.kuzu")

config = {
    "vector_store": {"provider": "chroma", "config": {"path": DB_PATH}},
    "graph_store": {
        "provider": "kuzu",
        "config": {"db": GRAPH_PATH},
        "llm": {
            "provider": "openai",
            "config": {
                "model": "gpt-4o-mini",
                # 这里假设你通过环境变量提供 OpenAI API Key
                # "api_key": os.getenv("OPENAI_API_KEY"),
            },
        },
    },
    "llm": {"provider": "ollama", "config": {"model": "mythomax-l2-13b"}},
    "embedder": {"provider": "ollama", "config": {"model": "nomic-embed-text"}},
}

memory = Memory(MemoryConfig(**config))
```

> 说明：  
> - 对话仍然用 `mythomax-l2-13b`（Ollama）。  
> - Graph Memory 抽取部分单独使用 OpenAI 的 `gpt-4o-mini`，满足 tool-calling 要求。  
> - 如果你启用本方案，请确保已经在环境变量中正确设置了 OpenAI API Key。  


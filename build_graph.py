"""
build_graph.py

只负责：
1) 导入 TXT（分章/切片）
2) 启用 Mem0 Graph Memory（Kuzu）生成图谱
3) 直接连接 Kuzu 做基础分析输出（节点/关系/统计）

不包含聊天逻辑。
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
from pathlib import Path

import kuzu
from mem0 import Memory
from mem0.configs.base import MemoryConfig


CHAPTER_SPLIT_RE = r"第[一二三四五六七八九十百千零\d]+章"
CHUNK_MAX_CHARS = 6000
MIN_CHAPTER_CHARS = 100
MIN_SEGMENT_CHARS = 50


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Import TXT into Mem0 and build Kuzu graph, then analyze it."
    )
    p.add_argument("--txt", type=str, default=os.getenv("NOVEL_TXT_PATH"))
    p.add_argument("--book", type=str, default=None)
    p.add_argument("--user-id", type=str, default="graph")
    p.add_argument("--agent-id", type=str, default=None)
    p.add_argument(
        "--db-path", type=str, default=os.getenv("MEM0_DB_PATH", "./mem0_db")
    )
    p.add_argument(
        "--graph-path",
        type=str,
        default=os.getenv("MEM0_GRAPH_PATH", "./mem0_graph.kuzu"),
    )
    p.add_argument("--llm-model", type=str, default="qwen2.5:14b")
    p.add_argument("--embed-model", type=str, default="nomic-embed-text")
    p.add_argument(
        "--embedding-dims",
        type=int,
        default=512,
        help="Embedding dimensions for the embedder/vector store schema.",
    )
    p.add_argument(
        "--infer",
        type=str,
        default="true",
        choices=["true", "false"],
        help="Whether to run Mem0 inference (true builds graph; false is for diagnostics).",
    )
    p.add_argument(
        "--force",
        action="store_true",
        help="Delete existing DB/graph directories before building.",
    )
    return p.parse_args()


def _resolve_book_and_agent(txt_path: str, book: str | None, agent_id: str | None):
    p = Path(txt_path)
    book_name = book or p.stem
    resolved_agent_id = agent_id or f"{book_name}_graph"
    return book_name, resolved_agent_id


def _maybe_clean_paths(force: bool, db_path: str, graph_path: str) -> None:
    db_exists = os.path.exists(db_path)
    graph_exists = os.path.exists(graph_path)
    if not (db_exists or graph_exists):
        return

    if not force:
        print("[WARN] Existing storage paths detected:")
        if db_exists:
            print(f"   - vector db:  {db_path}")
        if graph_exists:
            print(f"   - graph db:   {graph_path}")
        print("Exit to avoid mixing old/new data. Re-run with: --force")
        raise SystemExit(2)

    if db_exists:
        shutil.rmtree(db_path, ignore_errors=True)
    if graph_exists:
        shutil.rmtree(graph_path, ignore_errors=True)


def _build_memory(
    db_path: str,
    graph_path: str,
    llm_model: str,
    embed_model: str,
    embedding_dims: int,
) -> Memory:
    config = {
        "vector_store": {"provider": "chroma", "config": {"path": db_path}},
        "graph_store": {"provider": "kuzu", "config": {"db": graph_path}},
        "llm": {"provider": "ollama", "config": {"model": llm_model}},
        "embedder": {
            "provider": "ollama",
            "config": {"model": embed_model, "embedding_dims": embedding_dims},
        },
    }
    return Memory(MemoryConfig(**config))


def _ensure_kuzu_schema(graph_path: str, embedding_dims: int) -> None:
    """
    Kuzu arrays are fixed-size. Mem0's default schema uses `FLOAT[]`, which in Kuzu
    can behave like a fixed-size ARRAY with an implicit size (often 512), causing
    insert failures when embeddings have a different length (e.g., 768).

    We pre-create the schema with an explicit `FLOAT[embedding_dims]` so Mem0 can
    insert embeddings of the expected length.
    """
    db = kuzu.Database(graph_path)
    conn = kuzu.Connection(db)
    conn.execute(
        f"""
        CREATE NODE TABLE IF NOT EXISTS Entity(
            id SERIAL PRIMARY KEY,
            user_id STRING,
            agent_id STRING,
            run_id STRING,
            name STRING,
            mentions INT64,
            created TIMESTAMP,
            embedding FLOAT[{embedding_dims}]
        );
        """
    )
    conn.execute(
        """
        CREATE REL TABLE IF NOT EXISTS CONNECTED_TO(
            FROM Entity TO Entity,
            name STRING,
            mentions INT64,
            created TIMESTAMP,
            updated TIMESTAMP
        );
        """
    )


def _iter_segments(text: str):
    chapters = re.split(CHAPTER_SPLIT_RE, text)
    chapter_num = 0
    for chap in chapters:
        chap = chap.strip()
        if len(chap) <= MIN_CHAPTER_CHARS:
            continue
        chapter_num += 1
        for seg_idx in range(0, len(chap), CHUNK_MAX_CHARS):
            segment = chap[seg_idx : seg_idx + CHUNK_MAX_CHARS].strip()
            if len(segment) < MIN_SEGMENT_CHARS:
                continue
            part_idx = seg_idx // CHUNK_MAX_CHARS + 1
            yield chapter_num, part_idx, segment


def import_txt_build_graph(
    *,
    memory: Memory,
    txt_path: str,
    book_name: str,
    user_id: str,
    agent_id: str,
    infer: bool,
) -> None:
    if not os.path.exists(txt_path):
        raise FileNotFoundError(f"TXT not found: {txt_path}")

    with open(txt_path, "r", encoding="utf-8") as f:
        text = f.read()

    total = ok = fail = 0
    print(
        f"Importing book='{book_name}' and building graph (user_id={user_id}, agent_id={agent_id})..."
    )
    for chapter_num, part_idx, segment in _iter_segments(text):
        total += 1
        try:
            print(f"[import] add: chapter={chapter_num}, part={part_idx}", flush=True)
            memory.add(
                f"第{chapter_num}章（部分{part_idx}）：{segment}",
                user_id=user_id,
                agent_id=agent_id,
                metadata={"book": book_name, "chapter": chapter_num, "part": part_idx},
                infer=infer,
            )
            ok += 1
        except Exception as e:
            fail += 1
            print(
                f"[WARN] add failed: chapter={chapter_num}, part={part_idx}, err={type(e).__name__}: {e}"
            )

    print(f"[import] total={total}, ok={ok}, fail={fail}")


def analyze_kuzu_graph(
    graph_path: str, user_id: str | None, agent_id: str | None
) -> None:
    if not os.path.exists(graph_path):
        print(f"[ERROR] Graph path not found: {graph_path}")
        raise SystemExit(3)

    print(f"\n[info] Reading Kuzu graph: {graph_path}\n")
    db = kuzu.Database(graph_path)
    conn = kuzu.Connection(db)

    print("=== 节点属性结构预览（前 5 个节点）===")
    result = conn.execute("MATCH (n:Entity) RETURN n LIMIT 5")
    for row in result:
        print(row[0])

    print("\n" + "=" * 50)
    print("=== 1. 图谱中的所有节点（人物/实体）===")

    match_clause = "MATCH (n:Entity)"
    where_clauses = []
    params = {}
    if user_id:
        where_clauses.append("n.user_id = $user_id")
        params["user_id"] = user_id
    if agent_id:
        where_clauses.append("n.agent_id = $agent_id")
        params["agent_id"] = agent_id
    where_sql = (" WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

    node_query = (
        match_clause
        + where_sql
        + """
    RETURN n.name AS name,
           n.user_id AS user_id,
           n.agent_id AS agent_id
    LIMIT 30
"""
    )
    result = conn.execute(node_query, params) if params else conn.execute(node_query)
    nodes = []
    for row in result:
        name = row[0] or "Unknown"
        uid = row[1] or "-"
        aid = row[2] or "-"
        print(f"  - {name}  (user_id={uid}, agent_id={aid})")
        nodes.append(name)
    print(f"\n共找到 {len(nodes)} 个节点\n")

    print("=== 2. 图谱中的所有关系（谁 → 什么 → 谁）===")
    rel_match = "MATCH (a:Entity)-[r:CONNECTED_TO]->(b:Entity)"
    rel_where_clauses = []
    rel_params = {}
    if user_id:
        rel_where_clauses.append("a.user_id = $user_id")
        rel_params["user_id"] = user_id
    if agent_id:
        rel_where_clauses.append("a.agent_id = $agent_id")
        rel_params["agent_id"] = agent_id
    rel_where_sql = (
        (" WHERE " + " AND ".join(rel_where_clauses)) if rel_where_clauses else ""
    )

    rel_query = (
        rel_match
        + rel_where_sql
        + """
    RETURN 
        a.name AS source,
        r.name AS rel_name,
        b.name AS target
    LIMIT 50
"""
    )
    result = (
        conn.execute(rel_query, rel_params) if rel_params else conn.execute(rel_query)
    )
    rel_count = 0
    for row in result:
        source = row[0] or "Unknown"
        rel_name = row[1] or "CONNECTED_TO"
        target = row[2] or "Unknown"
        print(f"  {source}  ──[{rel_name}]──>  {target}")
        rel_count += 1

    print("\n=== 3. 图谱总体统计 ===")
    total_nodes = conn.execute("MATCH (n:Entity) RETURN COUNT(*) AS c").get_next()[0]
    total_rels = conn.execute(
        "MATCH (:Entity)-[r:CONNECTED_TO]->(:Entity) RETURN COUNT(*) AS c"
    ).get_next()[0]
    print(f"- 全局 Entity 节点总数：{total_nodes}")
    print(f"- 全局 CONNECTED_TO 关系总数：{total_rels}")


def main() -> None:
    args = _parse_args()
    if not args.txt:
        print("[ERROR] Missing --txt (or env NOVEL_TXT_PATH)")
        raise SystemExit(1)

    book_name, agent_id = _resolve_book_and_agent(args.txt, args.book, args.agent_id)
    infer = args.infer.lower() == "true"

    _maybe_clean_paths(args.force, args.db_path, args.graph_path)

    # Avoid Unicode issues on some Windows consoles (e.g., GBK).
    print("[Graph Build Mode] Mem0 + Kuzu")
    print(f"   - txt:        {args.txt}")
    print(f"   - book:       {book_name}")
    print(f"   - user_id:    {args.user_id}")
    print(f"   - agent_id:   {agent_id}")
    print(f"   - vector db:  {args.db_path}")
    print(f"   - graph db:   {args.graph_path}")
    print(f"   - llm:        {args.llm_model}")
    print(f"   - embedder:   {args.embed_model}")
    print(f"   - infer:      {infer}")
    print(f"   - dims:       {args.embedding_dims}")

    _ensure_kuzu_schema(args.graph_path, args.embedding_dims)

    memory = _build_memory(
        args.db_path,
        args.graph_path,
        args.llm_model,
        args.embed_model,
        args.embedding_dims,
    )
    import_txt_build_graph(
        memory=memory,
        txt_path=args.txt,
        book_name=book_name,
        user_id=args.user_id,
        agent_id=agent_id,
        infer=infer,
    )

    analyze_kuzu_graph(args.graph_path, user_id=args.user_id, agent_id=agent_id)
    print("\n[info] Done.")


if __name__ == "__main__":
    main()

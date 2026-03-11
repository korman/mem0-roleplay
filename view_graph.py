# view_graph.py  —— 修复版（自动适配 Mem0 的 Kuzu 图谱）
import kuzu
import os
import sys

db_path = "./mem0_graph.kuzu"

if not os.path.exists(db_path):
    print(
        "[错误] mem0_graph.kuzu 文件夹不存在！请先运行 main.py 或 graph_health_check.py 生成图谱"
    )
    exit()

print("[信息] Kuzu 图谱文件夹存在，正在读取内容...\n")

db = kuzu.Database(db_path)
conn = kuzu.Connection(db)

# 可选过滤：从命令行读取 user_id 和 agent_id
user_filter = None
agent_filter = None
if len(sys.argv) >= 2:
    user_filter = sys.argv[1] or None
if len(sys.argv) >= 3:
    agent_filter = sys.argv[2] or None

print(f"[过滤条件] user_id={user_filter or '*'} , agent_id={agent_filter or '*'}\n")

# ==================== 1. 先查看节点真实属性结构（调试用） ====================
print("=== 节点属性结构预览（前 5 个节点）===")
# Kuzu 不支持 Neo4j 的 properties(n) 函数，直接返回节点对象看一下即可
result = conn.execute("MATCH (n:Entity) RETURN n LIMIT 5")
for row in result:
    print(row[0])

print("\n" + "=" * 50)

# ==================== 2. 显示所有节点（人物） ====================
print("=== 1. 图谱中的所有节点（人物/实体）===")

match_clause = "MATCH (n:Entity)"
where_clauses = []
params = {}

if user_filter:
    where_clauses.append("n.user_id = $user_id")
    params["user_id"] = user_filter
if agent_filter:
    where_clauses.append("n.agent_id = $agent_id")
    params["agent_id"] = agent_filter

where_sql = ""
if where_clauses:
    where_sql = " WHERE " + " AND ".join(where_clauses)

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
    user_id = row[1] or "-"
    agent_id = row[2] or "-"
    print(f"  - {name}  (user_id={user_id}, agent_id={agent_id})")
    nodes.append(name)

print(f"\n共找到 {len(nodes)} 个节点\n")

# ==================== 3. 显示所有关系（最重要！） ====================
print("=== 2. 图谱中的所有关系（谁 → 什么 → 谁）===")

rel_match = "MATCH (a:Entity)-[r:CONNECTED_TO]->(b:Entity)"
rel_where_clauses = []
rel_params = {}

if user_filter:
    rel_where_clauses.append("a.user_id = $user_id")
    rel_params["user_id"] = user_filter
if agent_filter:
    rel_where_clauses.append("a.agent_id = $agent_id")
    rel_params["agent_id"] = agent_filter

rel_where_sql = ""
if rel_where_clauses:
    rel_where_sql = " WHERE " + " AND ".join(rel_where_clauses)

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

result = conn.execute(rel_query, rel_params) if rel_params else conn.execute(rel_query)
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

print("\n- 按 agent_id 聚合的节点数量：")
agg_result = conn.execute(
    """
    MATCH (n:Entity)
    RETURN n.agent_id AS agent_id, COUNT(*) AS cnt
    ORDER BY cnt DESC
    LIMIT 20
"""
)
for row in agg_result:
    print(f"  agent_id={row[0] or '-'}  节点数={row[1]}")

print("\n[信息] 图谱查看完成！")

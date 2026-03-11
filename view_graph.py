# view_graph.py  —— 修复版（自动适配 Mem0 的 Kuzu 图谱）
import kuzu
import os

db_path = "./mem0_graph.kuzu"

if not os.path.exists(db_path):
    print("[错误] mem0_graph.kuzu 文件夹不存在！请先运行 main.py 初始化角色")
    exit()

print("[信息] Kuzu 图谱文件夹存在，正在读取内容...\n")

db = kuzu.Database(db_path)
conn = kuzu.Connection(db)

# ==================== 1. 先查看节点真实属性结构（调试用） ====================
print("=== 节点属性结构预览（前 5 个节点）===")
# Kuzu 不支持 Neo4j 的 properties(n) 函数，直接返回节点对象看一下即可
result = conn.execute("MATCH (n:Entity) RETURN n LIMIT 5")
for row in result:
    print(row[0])

print("\n" + "=" * 50)

# ==================== 2. 显示所有节点（人物） ====================
print("=== 1. 图谱中的所有节点（人物/实体）===")
result = conn.execute("""
    MATCH (n:Entity) 
    RETURN n.name AS name, 
           n.user_id AS user_id,
           n.agent_id AS agent_id
    LIMIT 30
""")
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
result = conn.execute("""
    MATCH (a:Entity)-[r:CONNECTED_TO]->(b:Entity) 
    RETURN 
        a.name AS source,
        r.name AS rel_name,
        b.name AS target
    LIMIT 50
""")
rel_count = 0
for row in result:
    source = row[0] or "Unknown"
    rel_name = row[1] or "CONNECTED_TO"
    target = row[2] or "Unknown"
    print(f"  {source}  ──[{rel_name}]──>  {target}")
    rel_count += 1

print("\n[信息] 图谱查看完成！")
if "林晓薇" in str(nodes) or "张逸" in str(nodes):
    print("[提示] 图谱已经成功生成，并且包含人物关系～")
else:
    print("[警告] 节点较少，可能是小说太短或初始化没完成")

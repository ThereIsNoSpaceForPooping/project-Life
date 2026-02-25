"""
执行建表操作并展示结果
"""
from supabase_tools import execute_sql, list_tables

print("正在创建 demo 表...")
create_sql = """
CREATE TABLE IF NOT EXISTS demo (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    content TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
"""
result = execute_sql.invoke(create_sql)
print(f"建表结果: {result}")

if "失败" not in result:
    print("\n正在插入测试数据...")
    insert_sql = "INSERT INTO demo (name, content) VALUES ('测试数据', '这是一条由代码生成的记录');"
    execute_sql.invoke(insert_sql)
    
    print("\n现在的表列表:")
    print(list_tables.invoke({}))
else:
    print("\n建表似乎失败了，请检查连接。")

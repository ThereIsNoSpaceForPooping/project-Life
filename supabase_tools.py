"""
Supabase 数据库工具类 (psycopg2 核心实现)
提供稳定、高效的 SQL 直连方案
"""
import os
import json
import psycopg2
from psycopg2.extras import RealDictCursor
from contextlib import contextmanager
from langchain.tools import tool
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

class DatabaseConfig:
    """数据库配置管理"""
    def __init__(self):
        self.user = os.getenv("user")
        self.password = os.getenv("password")
        self.host = os.getenv("host")
        self.port = os.getenv("port", "5432")
        self.dbname = os.getenv("dbname", "postgres")

    def get_connection_params(self):
        return {
            "user": self.user,
            "password": self.password,
            "host": self.host,
            "port": self.port,
            "dbname": self.dbname,
            "sslmode": 'require'
        }

class DatabaseManager:
    """使用 psycopg2 的数据库操作管理器"""
    def __init__(self):
        self.config = DatabaseConfig()

    @contextmanager
    def get_cursor(self):
        """数据库连接上下文管理器，确保连接和游标正确关闭"""
        conn = None
        try:
            conn = psycopg2.connect(**self.config.get_connection_params())
            # 设置为自动提交，方便执行 DDL (如 CREATE TABLE)
            conn.autocommit = True
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                yield cur
        except Exception as e:
            # 增加性能解释：psycopg2 是基于 C 语言实现的 PostgreSQL 适配器，
            # 在 Python 中具有极高的性能和稳定性。
            print(f"数据库操作异常: {str(e)}")
            raise
        finally:
            if conn:
                conn.close()

    def execute_query(self, sql: str, params=None):
        """执行 SQL 并返回所有结果"""
        with self.get_cursor() as cur:
            cur.execute(sql, params)
            try:
                if cur.description:
                    return cur.fetchall()
            except psycopg2.ProgrammingError:
                # 某些语句（如 CREATE）没有返回结果
                pass
            return "操作执行成功"

# 实例化管理器
db_manager = DatabaseManager()

# --- LangChain 工具集 ---

@tool
def list_tables() -> str:
    """
    列出数据库中所有的公开表 (public schema)。
    """
    sql = """
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public'
        ORDER BY table_name;
    """
    try:
        results = db_manager.execute_query(sql)
        if not results or isinstance(results, str):
            return "数据库中目前没有表。"
        return "数据库中的表有: \n" + "\n".join([f"- {r['table_name']}" for r in results])
    except Exception as e:
        return f"获取表列表失败: {str(e)}"

@tool
def execute_sql(sql: str) -> str:
    """
    执行 SQL 语句。支持查询、建表、插入、更新等。
    示例: "SELECT * FROM demo LIMIT 5;" 或 "CREATE TABLE products (id serial primary key, name text);"
    """
    try:
        result = db_manager.execute_query(sql)
        if isinstance(result, list):
            return json.dumps(result, indent=2, default=str, ensure_ascii=False)
        return str(result)
    except Exception as e:
        return f"SQL 执行失败: {str(e)}"

@tool
def describe_table(table_name: str) -> str:
    """
    获取指定表的字段名称和数据类型信息。
    """
    sql = f"""
        SELECT column_name, data_type, is_nullable
        FROM information_schema.columns
        WHERE table_name = %s
        ORDER BY ordinal_position;
    """
    try:
        results = db_manager.execute_query(sql, (table_name,))
        if not results or isinstance(results, str):
            return f"找不到表 '{table_name}' 或该表没有字段信息。"
        return f"表 '{table_name}' 的结构如下:\n" + \
               "\n".join([f"- {r['column_name']} ({r['data_type']}, 可为空: {r['is_nullable']})" for r in results])
    except Exception as e:
        return f"获取表结构失败: {str(e)}"

# 导出供 Agent 使用的工具列表
DATABASE_TOOLS = [list_tables, execute_sql, describe_table]

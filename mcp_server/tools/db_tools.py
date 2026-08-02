# -*- coding: utf-8 -*-
"""
MCP Server - 数据库工具

提供 SQLite 数据库查询功能。
"""

import aiosqlite
from typing import List, Dict, Any
from config import Config


class DatabaseTools:
    """数据库操作工具集"""
    
    @staticmethod
    async def _get_db() -> aiosqlite.Connection:
        """获取数据库连接"""
        db = await aiosqlite.connect(str(Config.DB_PATH))
        db.row_factory = aiosqlite.Row
        return db
    
    @staticmethod
    async def db_query(sql: str, params: List[Any] = None) -> dict:
        """
        执行 SQL 查询
        
        Args:
            sql: SQL 查询语句
            params: SQL 参数列表
        
        Returns:
            {"rows": [...], "columns": [...], "count": 10}
        """
        try:
            db = await DatabaseTools._get_db()
            
            try:
                if params:
                    cursor = await db.execute(sql, params)
                else:
                    cursor = await db.execute(sql)
                
                # 获取列名
                columns = [desc[0] for desc in cursor.description] if cursor.description else []
                
                # 获取所有行
                rows = await cursor.fetchall()
                
                # 转换为字典列表
                result_rows = [dict(zip(columns, row)) for row in rows]
                
                return {
                    "rows": result_rows,
                    "columns": columns,
                    "count": len(result_rows)
                }
            
            finally:
                await db.close()
        
        except Exception as e:
            return {"error": f"查询失败: {str(e)}"}
    
    @staticmethod
    async def db_execute(sql: str, params: List[Any] = None) -> dict:
        """
        执行 SQL 语句（INSERT/UPDATE/DELETE）
        
        Args:
            sql: SQL 语句
            params: SQL 参数列表
        
        Returns:
            {"affected_rows": 1, "last_insert_id": 123}
        """
        try:
            db = await DatabaseTools._get_db()
            
            try:
                if params:
                    cursor = await db.execute(sql, params)
                else:
                    cursor = await db.execute(sql)
                
                await db.commit()
                
                return {
                    "affected_rows": cursor.rowcount,
                    "last_insert_id": cursor.lastrowid
                }
            
            finally:
                await db.close()
        
        except Exception as e:
            return {"error": f"执行失败: {str(e)}"}
    
    @staticmethod
    async def db_tables() -> dict:
        """
        列出所有表
        
        Returns:
            {"tables": ["users", "orders", ...]}
        """
        try:
            db = await DatabaseTools._get_db()
            
            try:
                cursor = await db.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
                )
                tables = [row[0] for row in await cursor.fetchall()]
                
                return {"tables": tables}
            
            finally:
                await db.close()
        
        except Exception as e:
            return {"error": f"查询失败: {str(e)}"}
    
    @staticmethod
    async def db_schema(table: str) -> dict:
        """
        获取表结构
        
        Args:
            table: 表名
        
        Returns:
            {"columns": [{"name": "id", "type": "INTEGER", ...}, ...]}
        """
        try:
            db = await DatabaseTools._get_db()
            
            try:
                cursor = await db.execute(f"PRAGMA table_info({table})")
                columns = []
                
                for row in await cursor.fetchall():
                    columns.append({
                        "cid": row[0],
                        "name": row[1],
                        "type": row[2],
                        "notnull": bool(row[3]),
                        "default": row[4],
                        "pk": bool(row[5])
                    })
                
                return {"table": table, "columns": columns}
            
            finally:
                await db.close()
        
        except Exception as e:
            return {"error": f"查询失败: {str(e)}"}


# 工具注册信息
DB_TOOLS = [
    {
        "name": "db_query",
        "description": "执行 SQL 查询（SELECT）",
        "parameters": {
            "type": "object",
            "properties": {
                "sql": {
                    "type": "string",
                    "description": "SQL 查询语句"
                },
                "params": {
                    "type": "array",
                    "description": "SQL 参数列表",
                    "items": {"type": "string"}
                }
            },
            "required": ["sql"]
        },
        "handler": DatabaseTools.db_query
    },
    {
        "name": "db_execute",
        "description": "执行 SQL 语句（INSERT/UPDATE/DELETE）",
        "parameters": {
            "type": "object",
            "properties": {
                "sql": {
                    "type": "string",
                    "description": "SQL 语句"
                },
                "params": {
                    "type": "array",
                    "description": "SQL 参数列表",
                    "items": {"type": "string"}
                }
            },
            "required": ["sql"]
        },
        "handler": DatabaseTools.db_execute
    },
    {
        "name": "db_tables",
        "description": "列出所有表",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": []
        },
        "handler": DatabaseTools.db_tables
    },
    {
        "name": "db_schema",
        "description": "获取表结构",
        "parameters": {
            "type": "object",
            "properties": {
                "table": {
                    "type": "string",
                    "description": "表名"
                }
            },
            "required": ["table"]
        },
        "handler": DatabaseTools.db_schema
    }
]

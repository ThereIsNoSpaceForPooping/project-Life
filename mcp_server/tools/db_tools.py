# -*- coding: utf-8 -*-
"""
MCP 数据库操作工具

使用 FastMCP 的 @mcp.tool() 装饰器注册 4 个 SQLite 数据库工具：
    - db_query：执行 SELECT 查询
    - db_execute：执行 INSERT/UPDATE/DELETE
    - db_tables：列出所有表
    - db_schema：获取表结构

数据库默认使用 SQLite（aiosqlite 异步驱动）。
所有 SQL 必须使用参数化查询（? 占位符），防止 SQL 注入。
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

import aiosqlite

from config import Config

logger: logging.Logger = logging.getLogger("mcp.db")


# ============================================================
# 数据库连接管理
# ============================================================
async def _get_connection() -> aiosqlite.Connection:
    """
    获取异步数据库连接

    Returns:
        aiosqlite.Connection: 已配置 row_factory 的连接
    """
    # 确保父目录存在
    Config.DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    db: aiosqlite.Connection = await aiosqlite.connect(str(Config.DB_PATH))
    db.row_factory = aiosqlite.Row  # 字典式访问
    return db


def _rows_to_dicts(rows: List[Any], columns: List[str]) -> List[Dict[str, Any]]:
    """
    将 aiosqlite Row 列表转换为字典列表

    Args:
        rows: aiosqlite Row 列表
        columns: 列名列表

    Returns:
        字典列表
    """
    result: List[Dict[str, Any]] = []
    for row in rows:
        item: Dict[str, Any] = {}
        for col in columns:
            value = row[col]
            # JSON 不支持 bytes，转为 base64 字符串
            if isinstance(value, bytes):
                import base64
                value = base64.b64encode(value).decode("ascii")
            item[col] = value
        result.append(item)
    return result


# ============================================================
# 危险 SQL 防护
# ============================================================
_DANGEROUS_KEYWORDS: List[str] = [
    "DROP DATABASE", "DROP SCHEMA", "TRUNCATE", "GRANT", "REVOKE",
    "ATTACH DATABASE", "DETACH DATABASE",
]


def _check_sql_safety(sql: str, allow_write: bool = False) -> Optional[str]:
    """
    校验 SQL 安全性

    Args:
        sql: SQL 语句
        allow_write: 是否允许写操作

    Returns:
        错误消息（如果安全返回 None）
    """
    if not sql or not sql.strip():
        return "SQL 不能为空"

    sql_upper: str = sql.upper().strip()

    # 检查危险关键词
    for keyword in _DANGEROUS_KEYWORDS:
        if keyword in sql_upper:
            return f"禁止执行危险 SQL: {keyword}"

    if not allow_write:
        # 仅允许 SELECT / PRAGMA / EXPLAIN
        if not any(
            sql_upper.startswith(prefix)
            for prefix in ("SELECT", "PRAGMA", "EXPLAIN", "WITH")
        ):
            return f"db_query 仅支持 SELECT/PRAGMA/EXPLAIN，请使用 db_execute 执行写操作"

    return None


# ============================================================
# 工具注册函数
# ============================================================
def register_db_tools(mcp: Any) -> int:
    """
    注册数据库工具到 FastMCP 实例

    Args:
        mcp: FastMCP 实例

    Returns:
        注册的工具数量
    """
    # ============================================================
    # 工具 1：db_query（只读）
    # ============================================================
    @mcp.tool(
        name="db_query",
        description=(
            "执行 SQL 查询（SELECT/PRAGMA/EXPLAIN），返回结果行列表。"
            "支持参数化查询（使用 ? 占位符）。"
            "【必用·SQL查询专用 SELECT】"
        ),
        annotations={
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def db_query(sql: str, params: Optional[List[Any]] = None) -> Dict[str, Any]:
        """
        执行 SQL 查询

        Args:
            sql: SQL 查询语句
            params: 参数化查询参数

        Returns:
            包含 rows / columns / count 的字典
        """
        # 安全性校验
        safety_error: Optional[str] = _check_sql_safety(sql, allow_write=False)
        if safety_error:
            logger.warning("[db_query] 安全校验失败: %s", safety_error)
            return {
                "isError": True,
                "content": [{"type": "text", "text": safety_error}],
            }

        try:
            db: aiosqlite.Connection = await _get_connection()
            try:
                cursor: aiosqlite.Cursor
                if params:
                    cursor = await db.execute(sql, params)
                else:
                    cursor = await db.execute(sql)

                # 列名
                columns: List[str] = (
                    [desc[0] for desc in cursor.description]
                    if cursor.description
                    else []
                )

                rows: List[Any] = await cursor.fetchall()
                result_rows: List[Dict[str, Any]] = _rows_to_dicts(rows, columns)

                logger.info(
                    "[db_query] SQL: %s ... → %d 行", sql[:60], len(result_rows)
                )

                return {
                    "rows": result_rows,
                    "columns": columns,
                    "count": len(result_rows),
                }
            finally:
                await db.close()

        except Exception as exc:
            logger.exception("[db_query] 查询失败: %s", exc)
            return {
                "isError": True,
                "content": [{"type": "text", "text": f"查询失败: {exc}"}],
            }

    # ============================================================
    # 工具 2：db_execute
    # ============================================================
    @mcp.tool(
        name="db_execute",
        description=(
            "执行 SQL 写操作（INSERT/UPDATE/DELETE/CREATE TABLE）。"
            "返回受影响行数与最后插入 ID。"
            "【必用·SQL执行专用 INSERT/UPDATE/DELETE】"
        ),
        annotations={
            "readOnlyHint": False,
            "destructiveHint": True,
            "idempotentHint": False,
            "openWorldHint": False,
        },
    )
    async def db_execute(sql: str, params: Optional[List[Any]] = None) -> Dict[str, Any]:
        """
        执行 SQL 写操作

        Args:
            sql: SQL 语句
            params: 参数化查询参数

        Returns:
            包含 affected_rows / last_insert_id 的字典
        """
        safety_error: Optional[str] = _check_sql_safety(sql, allow_write=True)
        if safety_error:
            logger.warning("[db_execute] 安全校验失败: %s", safety_error)
            return {
                "isError": True,
                "content": [{"type": "text", "text": safety_error}],
            }

        try:
            db: aiosqlite.Connection = await _get_connection()
            try:
                cursor: aiosqlite.Cursor
                if params:
                    cursor = await db.execute(sql, params)
                else:
                    cursor = await db.execute(sql)

                await db.commit()

                result: Dict[str, Any] = {
                    "affected_rows": cursor.rowcount,
                    "last_insert_id": cursor.lastrowid,
                }
                logger.info(
                    "[db_execute] SQL: %s ... → %d 行受影响",
                    sql[:60],
                    cursor.rowcount,
                )
                return result
            finally:
                await db.close()

        except Exception as exc:
            logger.exception("[db_execute] 执行失败: %s", exc)
            return {
                "isError": True,
                "content": [{"type": "text", "text": f"执行失败: {exc}"}],
            }

    # ============================================================
    # 工具 3：db_tables（只读）
    # ============================================================
    @mcp.tool(
        name="db_tables",
        description=(
            "列出数据库中所有用户表。"
            "【必用·数据库表列表专用】"
        ),
        annotations={
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def db_tables() -> Dict[str, Any]:
        """列出所有表"""
        try:
            db: aiosqlite.Connection = await _get_connection()
            try:
                cursor: aiosqlite.Cursor = await db.execute(
                    "SELECT name FROM sqlite_master "
                    "WHERE type='table' AND name NOT LIKE 'sqlite_%' "
                    "ORDER BY name"
                )
                tables: List[str] = [row[0] for row in await cursor.fetchall()]
                logger.info("[db_tables] 找到 %d 张表", len(tables))
                return {"tables": tables, "count": len(tables)}
            finally:
                await db.close()
        except Exception as exc:
            logger.exception("[db_tables] 查询失败: %s", exc)
            return {
                "isError": True,
                "content": [{"type": "text", "text": f"查询失败: {exc}"}],
            }

    # ============================================================
    # 工具 4：db_schema（只读）
    # ============================================================
    @mcp.tool(
        name="db_schema",
        description=(
            "获取指定表的结构（列名、类型、是否可空、默认值、主键）。"
            "【必用·表结构查询专用】"
        ),
        annotations={
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def db_schema(table: str) -> Dict[str, Any]:
        """
        获取表结构

        Args:
            table: 表名（必须只包含字母数字下划线）

        Returns:
            包含 columns 的字典
        """
        # 表名校验（防止 SQL 注入）
        if not table or not table.replace("_", "").isalnum():
            return {
                "isError": True,
                "content": [
                    {"type": "text", "text": f"非法表名: {table}（仅允许字母数字下划线）"}
                ],
            }

        try:
            db: aiosqlite.Connection = await _get_connection()
            try:
                cursor: aiosqlite.Cursor = await db.execute(
                    f"PRAGMA table_info({table})"
                )
                columns: List[Dict[str, Any]] = []
                for row in await cursor.fetchall():
                    columns.append(
                        {
                            "cid": row[0],
                            "name": row[1],
                            "type": row[2],
                            "notnull": bool(row[3]),
                            "default": row[4],
                            "pk": bool(row[5]),
                        }
                    )
                logger.info("[db_schema] %s: %d 列", table, len(columns))
                return {"table": table, "columns": columns}
            finally:
                await db.close()
        except Exception as exc:
            logger.exception("[db_schema] 查询失败: %s", exc)
            return {
                "isError": True,
                "content": [{"type": "text", "text": f"查询失败: {exc}"}],
            }

    return 4  # 注册的工具数量

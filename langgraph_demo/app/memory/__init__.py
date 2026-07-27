# -*- coding: utf-8 -*-
"""
记忆模块

支持多种持久化后端：
- 内存模式（开发/测试）
- SQLite 模式（单机生产）
- 可扩展 PostgreSQL/Redis
"""

import os
from typing import Optional
from pathlib import Path

from app.core.logging import get_logger

logger = get_logger(__name__)

# ============================================================
# 记忆后端类型
# ============================================================
MEMORY_BACKEND = os.getenv("MEMORY_BACKEND", "memory")  # memory / sqlite
SQLITE_DB_PATH = os.getenv("SQLITE_DB_PATH", "data/memory.db")


class ConversationMemory:
    """
    对话记忆管理器

    根据 MEMORY_BACKEND 环境变量选择存储后端：
    - memory: 内存模式，进程重启后丢失（适合开发）
    - sqlite: SQLite 持久化，进程重启后保留（适合生产）
    """

    def __init__(self):
        """初始化记忆管理器"""
        self._backend = MEMORY_BACKEND
        self._checkpointer = None

        if self._backend == "sqlite":
            self._init_sqlite()
        else:
            self._init_memory()

    def _init_memory(self):
        """初始化内存模式"""
        from langgraph.checkpoint.memory import MemorySaver
        self._checkpointer = MemorySaver()
        logger.info("对话记忆管理器已初始化（内存模式）")

    def _init_sqlite(self):
        """初始化 SQLite 持久化模式"""
        try:
            from langgraph.checkpoint.sqlite import SqliteSaver
            import sqlite3

            # 确保数据目录存在
            db_path = Path(SQLITE_DB_PATH)
            db_path.parent.mkdir(parents=True, exist_ok=True)

            # 创建 SQLite 连接和 checkpointer
            self._conn = sqlite3.connect(str(db_path))
            self._checkpointer = SqliteSaver(self._conn)
            logger.info(f"对话记忆管理器已初始化（SQLite 模式: {db_path}）")

        except ImportError:
            logger.warning("langgraph-checkpoint-sqlite 未安装，回退到内存模式")
            self._init_memory()
        except Exception as e:
            logger.error(f"SQLite 初始化失败: {e}，回退到内存模式")
            self._init_memory()

    @property
    def checkpointer(self):
        """
        获取 checkpointer 实例

        Returns:
            MemorySaver | SqliteSaver: LangGraph checkpointer
        """
        return self._checkpointer

    @property
    def backend(self) -> str:
        """获取当前后端类型"""
        return self._backend

    def get_config(self, conversation_id: str) -> dict:
        """
        获取对话配置

        Args:
            conversation_id: 对话 ID

        Returns:
            dict: LangGraph 配置字典
        """
        return {
            "configurable": {
                "thread_id": conversation_id
            }
        }

    def get_history(self, conversation_id: str) -> list:
        """
        获取对话历史记录

        Args:
            conversation_id: 对话 ID

        Returns:
            list: 历史消息列表
        """
        try:
            config = self.get_config(conversation_id)
            state = self._checkpointer.get(config)
            if state and "messages" in state.get("channel_values", {}):
                return state["channel_values"]["messages"]
            return []
        except Exception as e:
            logger.error(f"获取历史记录失败: {e}")
            return []

    def clear_memory(self, conversation_id: str) -> bool:
        """
        清除指定对话的记忆

        Args:
            conversation_id: 对话 ID

        Returns:
            bool: 是否成功
        """
        try:
            logger.info(f"清除对话记忆: {conversation_id}")
            # SQLite 模式可以直接操作数据库
            if self._backend == "sqlite" and hasattr(self, '_conn'):
                cursor = self._conn.cursor()
                cursor.execute(
                    "DELETE FROM checkpoints WHERE thread_id = ?",
                    (conversation_id,)
                )
                self._conn.commit()
                logger.info(f"已清除对话 {conversation_id} 的 {cursor.rowcount} 条记录")
            return True
        except Exception as e:
            logger.error(f"清除记忆失败: {e}")
            return False

    def list_conversations(self) -> list:
        """
        列出所有对话

        Returns:
            list: 对话 ID 列表
        """
        try:
            if self._backend == "sqlite" and hasattr(self, '_conn'):
                cursor = self._conn.cursor()
                cursor.execute(
                    "SELECT DISTINCT thread_id FROM checkpoints"
                )
                return [row[0] for row in cursor.fetchall()]
            return []
        except Exception as e:
            logger.error(f"列出对话失败: {e}")
            return []

    def close(self):
        """关闭连接（SQLite 模式）"""
        if self._backend == "sqlite" and hasattr(self, '_conn'):
            try:
                self._conn.close()
                logger.info("SQLite 连接已关闭")
            except Exception as e:
                logger.error(f"关闭 SQLite 连接失败: {e}")


# 全局记忆管理器实例
memory_manager = ConversationMemory()

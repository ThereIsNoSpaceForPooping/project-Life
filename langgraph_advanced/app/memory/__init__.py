# -*- coding: utf-8 -*-
"""
记忆模块

管理 Agent 的对话记忆，支持：
1. 内存模式（MemorySaver）- 进程重启后丢失
2. SQLite 模式（SqliteSaver）- 持久化存储

学习要点：
1. Checkpointer 是 LangGraph 的记忆机制
2. 每次图执行都会自动保存状态
3. 通过 thread_id 区分不同对话
4. 支持时间旅行（查看/回退历史状态）
"""

import os
from pathlib import Path

from langgraph.checkpoint.memory import MemorySaver

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class MemoryManager:
    """
    记忆管理器
    
    管理 Agent 的对话记忆，根据配置选择存储后端。
    
    属性：
        backend: 存储后端类型（memory / sqlite）
        checkpointer: LangGraph Checkpointer 实例
    """
    
    def __init__(self):
        """初始化记忆管理器"""
        self.backend = settings.MEMORY_BACKEND
        self.checkpointer = self._create_checkpointer()
        logger.info(f"记忆管理器初始化完成，后端: {self.backend}")
    
    def _create_checkpointer(self):
        """
        创建 Checkpointer 实例
        
        Returns:
            BaseCheckpointSaver: Checkpointer 实例
        """
        if self.backend == "sqlite":
            return self._create_sqlite_checkpointer()
        else:
            return self._create_memory_checkpointer()
    
    def _create_memory_checkpointer(self):
        """
        创建内存 Checkpointer
        
        特点：
        - 速度快
        - 进程重启后数据丢失
        - 适合开发测试
        """
        logger.info("使用内存 Checkpointer")
        return MemorySaver()
    
    def _create_sqlite_checkpointer(self):
        """
        创建 SQLite Checkpointer
        
        特点：
        - 数据持久化
        - 进程重启后数据保留
        - 适合生产环境
        
        Returns:
            SqliteSaver: SQLite Checkpointer 实例
        """
        try:
            from langgraph.checkpoint.sqlite import SqliteSaver
            
            # 确保数据目录存在
            db_path = Path(settings.SQLITE_DB_PATH)
            db_path.parent.mkdir(parents=True, exist_ok=True)
            
            logger.info(f"使用 SQLite Checkpointer: {db_path}")
            return SqliteSaver.from_conn_string(str(db_path))
        
        except ImportError:
            logger.warning("langgraph-checkpoint-sqlite 未安装，回退到内存模式")
            return MemorySaver()
        
        except Exception as e:
            logger.error(f"SQLite Checkpointer 初始化失败: {e}，回退到内存模式")
            return MemorySaver()


# 全局记忆管理器实例
memory_manager = MemoryManager()

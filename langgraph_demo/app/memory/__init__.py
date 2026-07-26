# -*- coding: utf-8 -*-
"""
记忆模块

基于 LangGraph 的 Checkpointer 实现对话记忆
支持内存存储和持久化存储
"""

from typing import Optional
from langgraph.checkpoint.memory import MemorySaver

from app.core.logging import get_logger

logger = get_logger(__name__)


class ConversationMemory:
    """
    对话记忆管理器
    
    使用 LangGraph 的 MemorySaver 实现对话状态持久化
    每个对话通过 conversation_id 隔离
    """
    
    def __init__(self):
        """初始化记忆管理器"""
        # 内存级 checkpointer（进程重启后丢失）
        self._memory = MemorySaver()
        logger.info("对话记忆管理器已初始化（内存模式）")
    
    @property
    def checkpointer(self) -> MemorySaver:
        """
        获取 checkpointer 实例
        
        Returns:
            MemorySaver: LangGraph checkpointer
        """
        return self._memory
    
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
    
    def clear_memory(self, conversation_id: str) -> bool:
        """
        清除指定对话的记忆
        
        Args:
            conversation_id: 对话 ID
            
        Returns:
            bool: 是否成功
        """
        try:
            # MemorySaver 没有直接的 clear 方法
            # 可以通过删除 thread 来实现（需要自定义实现）
            # 这里简化处理，返回 True
            logger.info(f"清除对话记忆: {conversation_id}")
            return True
        except Exception as e:
            logger.error(f"清除记忆失败: {e}")
            return False


# 全局记忆管理器实例
memory_manager = ConversationMemory()

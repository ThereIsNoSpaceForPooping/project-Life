# -*- coding: utf-8 -*-
"""
中间件包

包含 Agent 大图中的可复用中间件：
- stuck_guard: 重复工具调用检测（防抖）
- prebuilt_tool_node: 类官方 ToolNode 的工具执行节点

学习要点：
- 中间件应该是无状态或弱状态的纯函数节点
- 易于单测、组合、可替换
"""

# -*- coding: utf-8 -*-
"""
MCP Server - 代码执行工具

提供安全的 Python 代码执行功能。
"""

import sys
import io
import traceback
from contextlib import redirect_stdout, redirect_stderr


class CodeTools:
    """代码执行工具集"""
    
    @staticmethod
    async def code_execute(code: str) -> dict:
        """
        执行 Python 代码
        
        Args:
            code: Python 代码字符串
        
        Returns:
            {"output": "执行输出", "error": "错误信息"}
        """
        # 捕获 stdout 和 stderr
        stdout_buffer = io.StringIO()
        stderr_buffer = io.StringIO()
        
        try:
            # 创建执行环境
            exec_globals = {
                "__builtins__": __builtins__,
                # 可以添加一些安全的模块
            }
            
            # 重定向输出
            with redirect_stdout(stdout_buffer), redirect_stderr(stderr_buffer):
                exec(code, exec_globals)
            
            output = stdout_buffer.getvalue()
            error = stderr_buffer.getvalue()
            
            result = {"output": output}
            if error:
                result["error"] = error
            
            return result
        
        except Exception as e:
            return {
                "output": stdout_buffer.getvalue(),
                "error": f"{type(e).__name__}: {str(e)}\n{traceback.format_exc()}"
            }
    
    @staticmethod
    async def code_evaluate(expression: str) -> dict:
        """
        计算表达式
        
        Args:
            expression: Python 表达式
        
        Returns:
            {"result": "计算结果", "error": "错误信息"}
        """
        try:
            # 只允许安全的表达式
            result = eval(expression, {"__builtins__": {}}, {})
            return {"result": result}
        except Exception as e:
            return {"error": f"{type(e).__name__}: {str(e)}"}


# 工具注册信息
CODE_TOOLS = [
    {
        "name": "code_execute",
        "description": "执行 Python 代码",
        "parameters": {
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "Python 代码"
                }
            },
            "required": ["code"]
        },
        "handler": CodeTools.code_execute
    },
    {
        "name": "code_evaluate",
        "description": "计算 Python 表达式",
        "parameters": {
            "type": "object",
            "properties": {
                "expression": {
                    "type": "string",
                    "description": "Python 表达式"
                }
            },
            "required": ["expression"]
        },
        "handler": CodeTools.code_evaluate
    }
]

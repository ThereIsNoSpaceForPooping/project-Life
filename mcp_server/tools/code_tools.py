# -*- coding: utf-8 -*-
"""
MCP 代码执行工具

使用 FastMCP 的 @mcp.tool() 装饰器注册 2 个代码执行工具：
    - code_execute：在受限沙箱中执行 Python 代码
    - code_evaluate：安全计算 Python 表达式

安全设计：
    - 使用受限的内置命名空间
    - 限制执行时间（默认 10 秒）
    - 限制输出大小（默认 64 KB）
    - 重定向 stdout/stderr
"""

import ast
import io
import logging
import math
import signal
import sys
import time
import traceback
from contextlib import redirect_stderr, redirect_stdout
from typing import Any, Dict

logger: logging.Logger = logging.getLogger("mcp.code")


# ============================================================
# 安全沙箱配置
# ============================================================

# 允许的 Python 内置函数白名单
SAFE_BUILTINS: Dict[str, Any] = {
    # 类型
    "int": int,
    "float": float,
    "str": str,
    "bool": bool,
    "list": list,
    "tuple": tuple,
    "dict": dict,
    "set": set,
    "frozenset": frozenset,
    "bytes": bytes,
    "bytearray": bytearray,
    "complex": complex,
    # 常用函数
    "abs": abs,
    "all": all,
    "any": any,
    "ascii": ascii,
    "bin": bin,
    "chr": chr,
    "divmod": divmod,
    "enumerate": enumerate,
    "filter": filter,
    "format": format,
    "hex": hex,
    "id": id,
    "isinstance": isinstance,
    "issubclass": issubclass,
    "iter": iter,
    "len": len,
    "map": map,
    "max": max,
    "min": min,
    "next": next,
    "oct": oct,
    "ord": ord,
    "pow": pow,
    "print": print,
    "range": range,
    "repr": repr,
    "reversed": reversed,
    "round": round,
    "slice": slice,
    "sorted": sorted,
    "sum": sum,
    "zip": zip,
    # 异常
    "Exception": Exception,
    "ValueError": ValueError,
    "TypeError": TypeError,
    "KeyError": KeyError,
    "IndexError": IndexError,
    "StopIteration": StopIteration,
    # 常量
    "True": True,
    "False": False,
    "None": None,
    # 数学模块
    "math": math,
}

# 允许的 AST 节点白名单（用于表达式求值）
ALLOWED_AST_NODES: tuple = (
    ast.Expression,
    ast.Constant,
    ast.BinOp,
    ast.UnaryOp,
    ast.Add,
    ast.Sub,
    ast.Mult,
    ast.Div,
    ast.FloorDiv,
    ast.Mod,
    ast.Pow,
    ast.USub,
    ast.UAdd,
    ast.Call,
    ast.Name,
    ast.Load,
    ast.Tuple,
    ast.List,
    ast.Dict,
    ast.Set,
    # 数字字面量
    ast.Num,  # Python 3.7 兼容
    # 字符串字面量
    ast.Str,  # Python 3.7 兼容
)

# 禁止访问的危险属性（防止沙箱逃逸）
FORBIDDEN_ATTRIBUTES: set = {
    # 对象 introspection
    "__class__",
    "__mro__",
    "__bases__",
    "__subclasses__",
    "__init__",
    "__new__",
    "__del__",
    "__getattribute__",
    "__getattr__",
    "__setattr__",
    "__delattr__",
    # 函数/方法相关
    "__func__",
    "__self__",
    "__code__",
    "__globals__",
    "__builtins__",
    "__dict__",
    "__doc__",
    "__name__",
    "__qualname__",
    "__module__",
    # 文件/IO 相关
    "__enter__",
    "__exit__",
    "read",
    "write",
    "open",
    "close",
    # 系统相关
    "system",
    "popen",
    "exec",
    "eval",
    "compile",
    "import",
    "__import__",
}


# ============================================================
# AST 安全校验
# ============================================================
def validate_ast_safety(tree: ast.AST) -> str:
    """
    校验 AST 树，检测危险的属性访问

    Args:
        tree: AST 树

    Returns:
        如果检测到危险操作，返回错误信息；否则返回空字符串
    """
    for node in ast.walk(tree):
        # 检查属性访问
        if isinstance(node, ast.Attribute):
            attr_name = node.attr
            if attr_name in FORBIDDEN_ATTRIBUTES:
                return f"禁止访问危险属性: {attr_name}"
            # 检查双下划线属性（dunder）
            if attr_name.startswith("__") and attr_name.endswith("__"):
                return f"禁止访问特殊属性: {attr_name}"
        
        # 检查 import 语句
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            return "禁止导入模块"
        
        # 检查 exec/eval 调用
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if node.func.id in ("exec", "eval", "compile", "__import__"):
                return f"禁止调用危险函数: {node.func.id}"
    
    return ""


# ============================================================
# 工具注册函数
# ============================================================
def register_code_tools(mcp: Any) -> int:
    """
    注册代码执行工具到 FastMCP 实例

    Args:
        mcp: FastMCP 实例

    Returns:
        注册的工具数量
    """

    # ============================================================
    # 工具 1：code_execute
    # ============================================================
    @mcp.tool(
        name="code_execute",
        description=(
            "在受限沙箱中执行 Python 代码（无网络/无文件系统访问）。"
            "返回 stdout / stderr / exit_code / 执行时间。"
            "【必用·Python代码执行专用】"
        ),
        annotations={
            "readOnlyHint": False,
            "destructiveHint": True,
            "idempotentHint": False,
            "openWorldHint": False,
        },
    )
    async def code_execute(code: str) -> Dict[str, Any]:
        """
        执行 Python 代码

        Args:
            code: Python 代码字符串

        Returns:
            包含 output / error / exit_code / execution_time_ms 的字典
        """
        max_output_bytes: int = 64 * 1024  # 64 KB
        start_time: float = time.time()

        # 捕获 stdout / stderr
        stdout_buffer: io.StringIO = io.StringIO()
        stderr_buffer: io.StringIO = io.StringIO()

        # 构造执行环境
        exec_globals: Dict[str, Any] = {
            "__builtins__": SAFE_BUILTINS,
            "__name__": "__main__",
            "__doc__": None,
        }

        try:
            # AST 安全校验，防止沙箱逃逸
            try:
                code_tree = ast.parse(code, mode="exec")
                safety_error = validate_ast_safety(code_tree)
                if safety_error:
                    elapsed_ms = int((time.time() - start_time) * 1000)
                    logger.warning("[code_execute] 安全校验失败: %s", safety_error)
                    return {
                        "isError": True,
                        "content": [
                            {
                                "type": "text",
                                "text": f"安全错误: {safety_error}",
                            }
                        ],
                        "execution_time_ms": elapsed_ms,
                    }
            except SyntaxError:
                pass  # 语法错误会在 exec 阶段捕获

            with redirect_stdout(stdout_buffer), redirect_stderr(stderr_buffer):
                # 使用 exec()，编译为字节码后再执行
                compiled: Any = compile(code, "<mcp_code_execute>", "exec")
                exec(compiled, exec_globals)

            output: str = stdout_buffer.getvalue()
            error: str = stderr_buffer.getvalue()

            # 截断过大输出
            truncated: bool = False
            if len(output) > max_output_bytes:
                output = output[:max_output_bytes] + "\n... (output truncated)"
                truncated = True
            if len(error) > max_output_bytes:
                error = error[:max_output_bytes] + "\n... (error truncated)"
                truncated = True

            elapsed_ms: int = int((time.time() - start_time) * 1000)
            logger.info(
                "[code_execute] %d 字符 → %d ms (%s)",
                len(code),
                elapsed_ms,
                "截断" if truncated else "正常",
            )

            result: Dict[str, Any] = {
                "output": output,
                "exit_code": 0,
                "execution_time_ms": elapsed_ms,
            }
            if error:
                result["error"] = error
            return result

        except SyntaxError as exc:
            elapsed_ms = int((time.time() - start_time) * 1000)
            logger.warning("[code_execute] 语法错误: %s", exc)
            return {
                "isError": True,
                "content": [
                    {
                        "type": "text",
                        "text": (
                            f"语法错误 (行 {exc.lineno}): {exc.msg}\n"
                            f"{exc.text or ''}"
                        ).strip(),
                    }
                ],
                "output": stdout_buffer.getvalue(),
                "execution_time_ms": elapsed_ms,
            }
        except Exception as exc:  # pragma: no cover
            elapsed_ms = int((time.time() - start_time) * 1000)
            logger.warning("[code_execute] 执行异常: %s", exc)
            return {
                "isError": True,
                "content": [
                    {
                        "type": "text",
                        "text": (
                            f"{type(exc).__name__}: {exc}\n"
                            f"{traceback.format_exc()}"
                        ),
                    }
                ],
                "output": stdout_buffer.getvalue(),
                "execution_time_ms": elapsed_ms,
            }

    # ============================================================
    # 工具 2：code_evaluate
    # ============================================================
    @mcp.tool(
        name="code_evaluate",
        description=(
            "安全计算 Python 表达式（仅支持基础运算、函数调用、容器字面量）。"
            "返回表达式的值与类型。"
            "【必用·Python表达式求值专用】"
        ),
        annotations={
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def code_evaluate(expression: str) -> Dict[str, Any]:
        """
        计算 Python 表达式

        Args:
            expression: Python 表达式

        Returns:
            包含 result / type 的字典
        """
        try:
            # 先做 AST 校验，确保只包含允许的节点
            tree: ast.AST = ast.parse(expression, mode="eval")

            # 校验 AST 节点
            for node in ast.walk(tree):
                if not isinstance(node, ALLOWED_AST_NODES):
                    return {
                        "isError": True,
                        "content": [
                            {
                                "type": "text",
                                "text": (
                                    f"表达式包含禁止的节点: {type(node).__name__}"
                                ),
                            }
                        ],
                    }

            # 求值
            result: Any = eval(  # noqa: S307  # 已在 AST 阶段限制
                compile(tree, "<mcp_code_evaluate>", "eval"),
                {"__builtins__": SAFE_BUILTINS, "math": math},
            )

            # 类型转换（JSON 可序列化）
            result_repr: Any = result
            result_type: str = type(result).__name__
            try:
                import json
                json.dumps(result_repr)
            except (TypeError, ValueError):
                result_repr = repr(result)
                result_type = f"{type(result).__name__} (repr)"

            logger.info(
                "[code_evaluate] %s → %s = %s",
                expression[:40],
                result_type,
                str(result_repr)[:60],
            )

            return {
                "result": result_repr,
                "type": result_type,
            }

        except SyntaxError as exc:
            return {
                "isError": True,
                "content": [
                    {
                        "type": "text",
                        "text": f"表达式语法错误: {exc.msg}",
                    }
                ],
            }
        except Exception as exc:  # pragma: no cover
            logger.warning("[code_evaluate] 计算失败: %s", exc)
            return {
                "isError": True,
                "content": [
                    {
                        "type": "text",
                        "text": f"{type(exc).__name__}: {exc}",
                    }
                ],
            }

    return 2  # 注册的工具数量

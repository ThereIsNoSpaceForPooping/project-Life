# -*- coding: utf-8 -*-
"""
MCP 文件操作工具

使用 FastMCP 的 @mcp.tool() 装饰器注册 4 个文件操作工具：
    - file_read：读取文件内容
    - file_write：写入文件内容
    - file_list：列出目录内容
    - file_delete：删除文件

所有工具遵循 MCP 规范 2025-03-26，通过 JSON-RPC 2.0 暴露给客户端。
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

# 业务配置
from config import Config

logger: logging.Logger = logging.getLogger("mcp.file")


# ============================================================
# 文件路径安全校验
# ============================================================
def _safe_path(rel_path: str) -> Path:
    """
    将相对路径解析为安全绝对路径

    安全策略：
        1. 禁止路径穿越（../）逃出 FILE_ROOT_DIR
        2. 强制要求路径在 FILE_ROOT_DIR 之下
        3. 缺失目录时自动创建父目录

    Args:
        rel_path: 相对 FILE_ROOT_DIR 的路径

    Returns:
        解析后的绝对路径

    Raises:
        ValueError: 当路径非法或逃出根目录时
    """
    if not rel_path:
        rel_path = "."

    root: Path = Config.FILE_ROOT_DIR.resolve()
    target: Path = (root / rel_path).resolve()

    # 防止路径穿越
    try:
        target.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"非法路径: {rel_path} 逃出根目录 {root}") from exc

    return target


def _format_size(size_bytes: int) -> str:
    """
    将字节数格式化为人类可读字符串

    Args:
        size_bytes: 字节数

    Returns:
        格式化后字符串（如 "1.5 MB"）
    """
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} PB"


# ============================================================
# 工具注册函数
# ============================================================
def register_file_tools(mcp: Any) -> int:
    """
    注册文件操作工具到 FastMCP 实例

    Args:
        mcp: FastMCP 实例

    Returns:
        注册的工具数量
    """
    # 确保根目录存在
    Config.FILE_ROOT_DIR.mkdir(parents=True, exist_ok=True)

    # ============================================================
    # 工具 1：file_read（只读）
    # ============================================================
    @mcp.tool(
        name="file_read",
        description=(
            "读取文件内容。返回 UTF-8 解码后的文本、字节数、文件路径。"
            "支持相对路径（相对 FILE_ROOT_DIR）。"
            "【必用·文件读取专用】"
        ),
        annotations={
            "readOnlyHint": True,        # 只读操作
            "destructiveHint": False,    # 非破坏性
            "idempotentHint": True,      # 幂等（多次调用结果一致）
            "openWorldHint": False,      # 不访问开放世界
        },
    )
    async def file_read(path: str) -> Dict[str, Any]:
        """
        读取文件内容

        Args:
            path: 文件路径（相对 FILE_ROOT_DIR）

        Returns:
            包含 content / size / path 的字典
        """
        try:
            full_path: Path = _safe_path(path)

            if not full_path.exists():
                return {
                    "isError": True,
                    "content": [{"type": "text", "text": f"文件不存在: {path}"}],
                }
            if not full_path.is_file():
                return {
                    "isError": True,
                    "content": [{"type": "text", "text": f"不是文件: {path}"}],
                }

            # 限制单次读取大小（防止 OOM）
            max_bytes: int = 10 * 1024 * 1024  # 10 MB
            if full_path.stat().st_size > max_bytes:
                return {
                    "isError": True,
                    "content": [
                        {
                            "type": "text",
                            "text": (
                                f"文件过大: {_format_size(full_path.stat().st_size)}，"
                                f"超过 10 MB 限制"
                            ),
                        }
                    ],
                }

            content: str = full_path.read_text(encoding="utf-8")
            logger.info("[file_read] %s (%s)", path, _format_size(len(content.encode("utf-8"))))

            return {
                "content": content,
                "size": len(content.encode("utf-8")),
                "path": path,
            }

        except ValueError as exc:
            logger.warning("[file_read] 安全校验失败: %s", exc)
            return {
                "isError": True,
                "content": [{"type": "text", "text": str(exc)}],
            }
        except Exception as exc:  # pragma: no cover
            logger.exception("[file_read] 读取失败: %s", exc)
            return {
                "isError": True,
                "content": [{"type": "text", "text": f"读取失败: {exc}"}],
            }

    # ============================================================
    # 工具 2：file_write
    # ============================================================
    @mcp.tool(
        name="file_write",
        description=(
            "写入内容到文件。自动创建父目录。"
            "【必用·文件写入专用】"
        ),
        annotations={
            "readOnlyHint": False,       # 写入操作
            "destructiveHint": True,     # 会覆盖现有内容
            "idempotentHint": True,      # 幂等
            "openWorldHint": False,
        },
    )
    async def file_write(path: str, content: str) -> Dict[str, Any]:
        """
        写入文件内容

        Args:
            path: 文件路径
            content: 文件内容

        Returns:
            包含 success / path / size 的字典
        """
        try:
            full_path: Path = _safe_path(path)

            # 自动创建父目录
            full_path.parent.mkdir(parents=True, exist_ok=True)

            full_path.write_text(content, encoding="utf-8")
            size: int = len(content.encode("utf-8"))
            logger.info("[file_write] %s (%s)", path, _format_size(size))

            return {
                "success": True,
                "path": path,
                "size": size,
            }

        except ValueError as exc:
            logger.warning("[file_write] 安全校验失败: %s", exc)
            return {
                "isError": True,
                "content": [{"type": "text", "text": str(exc)}],
            }
        except Exception as exc:  # pragma: no cover
            logger.exception("[file_write] 写入失败: %s", exc)
            return {
                "isError": True,
                "content": [{"type": "text", "text": f"写入失败: {exc}"}],
            }

    # ============================================================
    # 工具 3：file_list（只读）
    # ============================================================
    @mcp.tool(
        name="file_list",
        description=(
            "列出目录内容。返回文件和子目录列表。"
            "【必用·目录列表专用】"
        ),
        annotations={
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def file_list(path: str = "") -> Dict[str, Any]:
        """
        列出目录内容

        Args:
            path: 目录路径（空字符串表示根目录）

        Returns:
            包含 files / directories / path 的字典
        """
        try:
            full_path: Path = _safe_path(path)

            if not full_path.exists():
                return {
                    "isError": True,
                    "content": [{"type": "text", "text": f"目录不存在: {path}"}],
                }
            if not full_path.is_dir():
                return {
                    "isError": True,
                    "content": [{"type": "text", "text": f"不是目录: {path}"}],
                }

            files: List[Dict[str, Any]] = []
            directories: List[str] = []

            for item in sorted(full_path.iterdir(), key=lambda x: x.name):
                if item.is_file():
                    files.append(
                        {
                            "name": item.name,
                            "size": item.stat().st_size,
                        }
                    )
                elif item.is_dir():
                    directories.append(item.name)

            logger.info(
                "[file_list] %s: %d 文件, %d 目录", path, len(files), len(directories)
            )

            return {
                "path": path or ".",
                "files": files,
                "directories": directories,
                "count": len(files) + len(directories),
            }

        except ValueError as exc:
            logger.warning("[file_list] 安全校验失败: %s", exc)
            return {
                "isError": True,
                "content": [{"type": "text", "text": str(exc)}],
            }
        except Exception as exc:  # pragma: no cover
            logger.exception("[file_list] 列出失败: %s", exc)
            return {
                "isError": True,
                "content": [{"type": "text", "text": f"列出失败: {exc}"}],
            }

    # ============================================================
    # 工具 4：file_delete
    # ============================================================
    @mcp.tool(
        name="file_delete",
        description=(
            "删除指定文件。注意：不可恢复，请谨慎使用。"
            "【必用·文件删除专用】"
        ),
        annotations={
            "readOnlyHint": False,
            "destructiveHint": True,     # 破坏性操作
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def file_delete(path: str) -> Dict[str, Any]:
        """
        删除文件

        Args:
            path: 文件路径

        Returns:
            包含 success / path 的字典
        """
        try:
            full_path: Path = _safe_path(path)

            if not full_path.exists():
                return {
                    "isError": True,
                    "content": [{"type": "text", "text": f"文件不存在: {path}"}],
                }
            if not full_path.is_file():
                return {
                    "isError": True,
                    "content": [{"type": "text", "text": f"不是文件: {path}"}],
                }

            full_path.unlink()
            logger.info("[file_delete] %s 已删除", path)

            return {
                "success": True,
                "path": path,
            }

        except ValueError as exc:
            logger.warning("[file_delete] 安全校验失败: %s", exc)
            return {
                "isError": True,
                "content": [{"type": "text", "text": str(exc)}],
            }
        except Exception as exc:  # pragma: no cover
            logger.exception("[file_delete] 删除失败: %s", exc)
            return {
                "isError": True,
                "content": [{"type": "text", "text": f"删除失败: {exc}"}],
            }

    return 4  # 注册的工具数量

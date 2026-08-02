# -*- coding: utf-8 -*-
"""
MCP Server - 文件操作工具

提供文件读写、列表、删除等功能。
"""

from pathlib import Path
from typing import Optional
from config import Config


class FileTools:
    """文件操作工具集"""
    
    @staticmethod
    async def file_read(path: str) -> dict:
        """
        读取文件内容
        
        Args:
            path: 文件路径（相对于根目录）
        
        Returns:
            {"content": "文件内容", "size": 123}
        """
        full_path = Config.FILE_ROOT_DIR / path
        
        if not full_path.exists():
            return {"error": f"文件不存在: {path}"}
        
        if not full_path.is_file():
            return {"error": f"不是文件: {path}"}
        
        try:
            content = full_path.read_text(encoding="utf-8")
            return {
                "content": content,
                "size": len(content),
                "path": str(path)
            }
        except Exception as e:
            return {"error": f"读取失败: {str(e)}"}
    
    @staticmethod
    async def file_write(path: str, content: str) -> dict:
        """
        写入文件内容
        
        Args:
            path: 文件路径（相对于根目录）
            content: 文件内容
        
        Returns:
            {"success": true, "size": 123}
        """
        full_path = Config.FILE_ROOT_DIR / path
        
        try:
            full_path.parent.mkdir(parents=True, exist_ok=True)
            full_path.write_text(content, encoding="utf-8")
            return {
                "success": True,
                "path": str(path),
                "size": len(content)
            }
        except Exception as e:
            return {"error": f"写入失败: {str(e)}"}
    
    @staticmethod
    async def file_list(path: str = "") -> dict:
        """
        列出目录内容
        
        Args:
            path: 目录路径（相对于根目录）
        
        Returns:
            {"files": [...], "directories": [...]}
        """
        full_path = Config.FILE_ROOT_DIR / path
        
        if not full_path.exists():
            return {"error": f"目录不存在: {path}"}
        
        if not full_path.is_dir():
            return {"error": f"不是目录: {path}"}
        
        try:
            files = []
            directories = []
            
            for item in full_path.iterdir():
                if item.is_file():
                    files.append({
                        "name": item.name,
                        "size": item.stat().st_size
                    })
                elif item.is_dir():
                    directories.append(item.name)
            
            return {
                "path": str(path),
                "files": files,
                "directories": directories
            }
        except Exception as e:
            return {"error": f"列出失败: {str(e)}"}
    
    @staticmethod
    async def file_delete(path: str) -> dict:
        """
        删除文件
        
        Args:
            path: 文件路径（相对于根目录）
        
        Returns:
            {"success": true}
        """
        full_path = Config.FILE_ROOT_DIR / path
        
        if not full_path.exists():
            return {"error": f"文件不存在: {path}"}
        
        if not full_path.is_file():
            return {"error": f"不是文件: {path}"}
        
        try:
            full_path.unlink()
            return {"success": True, "path": str(path)}
        except Exception as e:
            return {"error": f"删除失败: {str(e)}"}


# 工具注册信息
FILE_TOOLS = [
    {
        "name": "file_read",
        "description": "读取文件内容",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "文件路径（相对于根目录）"
                }
            },
            "required": ["path"]
        },
        "handler": FileTools.file_read
    },
    {
        "name": "file_write",
        "description": "写入文件内容",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "文件路径（相对于根目录）"
                },
                "content": {
                    "type": "string",
                    "description": "文件内容"
                }
            },
            "required": ["path", "content"]
        },
        "handler": FileTools.file_write
    },
    {
        "name": "file_list",
        "description": "列出目录内容",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "目录路径（相对于根目录）",
                    "default": ""
                }
            },
            "required": []
        },
        "handler": FileTools.file_list
    },
    {
        "name": "file_delete",
        "description": "删除文件",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "文件路径（相对于根目录）"
                }
            },
            "required": ["path"]
        },
        "handler": FileTools.file_delete
    }
]

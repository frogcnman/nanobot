"""Full tool wrappers for webchat - same permissions as CLI"""
from typing import Any, Callable, Awaitable
from functools import wraps
import json
import asyncio
from pathlib import Path

class SafeToolRegistry:
    """Tool registry with full tools (same as CLI mode)"""
    
    def __init__(self, workspace: Path, brave_api_key: str = None, exec_config=None, cron_service=None):
        self.workspace = workspace
        self.brave_api_key = brave_api_key
        self.exec_config = exec_config
        self.cron_service = cron_service
        self._tools = {}
        self._register_all_tools()
    
    def _register_all_tools(self):
        """Register all tools (same as CLI mode)"""
        from nanobot.agent.tools.filesystem import ReadFileTool, WriteFileTool, EditFileTool, ListDirTool
        from nanobot.agent.tools.shell import ExecTool
        from nanobot.agent.tools.web import WebSearchTool, WebFetchTool
        from nanobot.agent.tools.message import MessageTool
        from nanobot.agent.tools.spawn import SpawnTool
        from nanobot.agent.tools.cron import CronTool
        
        # Filesystem tools - full access (no restrict_to_workspace)
        self.register(ReadFileTool(workspace=self.workspace, allowed_dir=None))
        self.register(WriteFileTool(workspace=self.workspace, allowed_dir=None))
        self.register(EditFileTool(workspace=self.workspace, allowed_dir=None))
        self.register(ListDirTool(workspace=self.workspace, allowed_dir=None))
        
        # Shell execution tool
        self.register(ExecTool(
            working_dir=str(self.workspace),
            timeout=self.exec_config.timeout if self.exec_config else 60,
            restrict_to_workspace=False,
        ))
        
        # Web tools
        self.register(WebSearchTool(api_key=self.brave_api_key))
        self.register(WebFetchTool())
        
        # Message tool (will set callback later)
        self.register(MessageTool(send_callback=None))
        
        # Spawn tool for subagents
        self.register(SpawnTool(manager=None))
        
        # Cron tool if service available
        if self.cron_service:
            self.register(CronTool(self.cron_service))
        
        print(f"[FullTools] Registered: {list(self._tools.keys())}")
    
    def register(self, tool):
        """Register a tool"""
        self._tools[tool.name] = tool
    
    def get(self, name: str):
        """Get a tool by name"""
        return self._tools.get(name)
    
    def get_definitions(self):
        """Get tool definitions for LLM"""
        return [t.to_schema() for t in self._tools.values()]
    
    async def execute(self, name: str, arguments: dict) -> str:
        """Execute a tool"""
        if name not in self._tools:
            return f"Error: Tool '{name}' not found"
        try:
            result = await self._tools[name].execute(**arguments)
            return str(result)
        except Exception as e:
            return f"Error executing {name}: {e}"


def create_safe_agent_tools(workspace: Path, brave_api_key: str = None, exec_config=None, cron_service=None):
    """Create a full tool registry for webchat (same as CLI)"""
    return SafeToolRegistry(workspace, brave_api_key, exec_config, cron_service)

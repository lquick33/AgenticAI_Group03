"""
Base classes for tools that can be used by AI agents.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from langchain_core.tools import BaseTool as LangChainBaseTool


class BaseTool(ABC):
    """
    Abstract base class for all agent tools.
    
    This provides a consistent interface for creating tools that can be
    used by LangGraph agents.
    """
    
    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description
    
    @abstractmethod
    def run(self, *args, **kwargs) -> Any:
        """Execute the tool with given arguments."""
        pass
    
    @abstractmethod
    def to_langchain_tool(self) -> LangChainBaseTool:
        """Convert this tool to a LangChain tool for use with agents."""
        pass
    
    def __str__(self) -> str:
        return f"{self.name}: {self.description}"


class ToolRegistry:
    """
    Registry for managing and organizing tools.
    
    This class helps organize tools by category and provides easy access
    to tools for agents.
    """
    
    def __init__(self):
        self._tools: Dict[str, BaseTool] = {}
        self._categories: Dict[str, List[str]] = {}
    
    def register(self, tool: BaseTool, category: str = "general") -> None:
        """Register a tool with the registry."""
        self._tools[tool.name] = tool
        
        if category not in self._categories:
            self._categories[category] = []
        self._categories[category].append(tool.name)
    
    def get_tool(self, name: str) -> Optional[BaseTool]:
        """Get a tool by name."""
        return self._tools.get(name)
    
    def get_tools_by_category(self, category: str) -> List[BaseTool]:
        """Get all tools in a specific category."""
        if category not in self._categories:
            return []
        
        return [self._tools[name] for name in self._categories[category]]
    
    def get_all_tools(self) -> List[BaseTool]:
        """Get all registered tools."""
        return list(self._tools.values())
    
    def get_langchain_tools(self, categories: Optional[List[str]] = None) -> List[LangChainBaseTool]:
        """
        Get LangChain tools for use with agents.
        
        Args:
            categories: List of categories to include. If None, includes all tools.
        """
        if categories is None:
            tools = self.get_all_tools()
        else:
            tools = []
            for category in categories:
                tools.extend(self.get_tools_by_category(category))
        
        return [tool.to_langchain_tool() for tool in tools]
    
    def list_categories(self) -> List[str]:
        """List all available categories."""
        return list(self._categories.keys())
    
    def list_tools(self) -> Dict[str, List[str]]:
        """List all tools organized by category."""
        return {
            category: [self._tools[name].description for name in tool_names]
            for category, tool_names in self._categories.items()
        }

import threading
from typing import Dict, List, Any, Optional, Callable
from abc import ABC, abstractmethod


class BasePlugin(ABC):
    """
    所有插件的基础抽象类
    """
    
    name: str = "unnamed_plugin"
    version: str = "0.1.0"
    description: str = "A plugin for EternalSelfAgent"
    
    def __init__(self):
        self._initialized = False
        self._enabled = True
    
    @abstractmethod
    def initialize(self, agent) -> None:
        """
        插件初始化方法，在插件加载时调用
        
        Args:
            agent: EternalSelfAgent 实例
        """
        self._initialized = True
    
    def shutdown(self, agent) -> None:
        """
        插件关闭方法，在插件卸载时调用
        
        Args:
            agent: EternalSelfAgent 实例
        """
        self._initialized = False
    
    @property
    def is_initialized(self) -> bool:
        return self._initialized
    
    @property
    def is_enabled(self) -> bool:
        return self._enabled
    
    def set_enabled(self, enabled: bool) -> None:
        self._enabled = enabled


class TaskHandlerPlugin(BasePlugin):
    """
    任务处理器插件基类
    """
    
    @abstractmethod
    def get_task_handlers(self) -> Dict[str, Callable]:
        """
        返回插件提供的任务处理器
        
        Returns:
            Dict[str, Callable]: 任务类型到处理函数的映射
        """
        return {}


class KnowledgeProcessorPlugin(BasePlugin):
    """
    知识处理插件基类
    """
    
    @abstractmethod
    def on_node_added(self, node_name: str, attributes: Dict[str, Any]) -> None:
        """
        当节点添加时调用
        """
        pass
    
    @abstractmethod
    def on_edge_added(self, source: str, target: str, relation: str, weight: float) -> None:
        """
        当边添加时调用
        """
        pass


class PluginManager:
    """
    插件管理器
    """
    
    def __init__(self):
        self._plugins: Dict[str, BasePlugin] = {}
        self._lock = threading.Lock()
        self._agent = None
    
    def register_plugin(self, plugin: BasePlugin) -> bool:
        """
        注册一个插件
        
        Args:
            plugin: 要注册的插件实例
            
        Returns:
            bool: 注册是否成功
        """
        with self._lock:
            if plugin.name in self._plugins:
                return False
            self._plugins[plugin.name] = plugin
            return True
    
    def unregister_plugin(self, plugin_name: str) -> bool:
        """
        注销一个插件
        
        Args:
            plugin_name: 要注销的插件名称
            
        Returns:
            bool: 注销是否成功
        """
        with self._lock:
            if plugin_name not in self._plugins:
                return False
            plugin = self._plugins[plugin_name]
            if self._agent and plugin.is_initialized:
                plugin.shutdown(self._agent)
            del self._plugins[plugin_name]
            return True
    
    def initialize_plugins(self, agent) -> None:
        """
        初始化所有注册的插件
        
        Args:
            agent: EternalSelfAgent 实例
        """
        self._agent = agent
        with self._lock:
            for plugin in self._plugins.values():
                if not plugin.is_initialized:
                    plugin.initialize(agent)
    
    def shutdown_plugins(self) -> None:
        """
        关闭所有已初始化的插件
        """
        with self._lock:
            for plugin in self._plugins.values():
                if plugin.is_initialized:
                    plugin.shutdown(self._agent)
            self._agent = None
    
    def get_plugin(self, name: str) -> Optional[BasePlugin]:
        """
        获取指定名称的插件
        
        Args:
            name: 插件名称
            
        Returns:
            Optional[BasePlugin]: 插件实例，不存在则返回 None
        """
        with self._lock:
            return self._plugins.get(name)
    
    def list_plugins(self) -> List[Dict[str, Any]]:
        """
        列出所有注册的插件信息
        
        Returns:
            List[Dict[str, Any]]: 插件信息列表
        """
        with self._lock:
            return [
                {
                    "name": p.name,
                    "version": p.version,
                    "description": p.description,
                    "initialized": p.is_initialized,
                    "enabled": p.is_enabled
                }
                for p in self._plugins.values()
            ]
    
    def get_task_handlers(self) -> Dict[str, Callable]:
        """
        获取所有已注册的任务处理器
        
        Returns:
            Dict[str, Callable]: 合并后的任务处理器
        """
        handlers = {}
        with self._lock:
            for plugin in self._plugins.values():
                if isinstance(plugin, TaskHandlerPlugin) and plugin.is_enabled:
                    handlers.update(plugin.get_task_handlers())
        return handlers

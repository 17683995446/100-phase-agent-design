import os
import tempfile
import pytest
from core import (
    EternalSelfAgent, BasePlugin, TaskHandlerPlugin, 
    PluginManager, KnowledgeProcessorPlugin
)
from plugins.hello_plugin import HelloWorldPlugin
from plugins.counter_plugin import CounterPlugin
from plugins.knowledge_monitor import KnowledgeMonitorPlugin


class SimpleTestPlugin(TaskHandlerPlugin):
    """简单的测试插件"""
    name = "simple_test"
    version = "0.1.0"
    description = "简单的测试插件"
    
    def initialize(self, agent):
        super().initialize(agent)
        self.agent = agent
    
    def get_task_handlers(self):
        return {"test_task": self._test_handler}
    
    def _test_handler(self, task, agent):
        agent.knowledge_graph.add_node("test_node")


class SimpleKnowledgeProcessor(KnowledgeProcessorPlugin):
    """简单的知识处理测试插件"""
    name = "simple_kp"
    version = "0.1.0"
    description = "简单的知识处理测试插件"
    
    def __init__(self):
        super().__init__()
        self.nodes = []
        self.edges = []
    
    def initialize(self, agent):
        super().initialize(agent)
    
    def on_node_added(self, node_name, attributes):
        self.nodes.append(node_name)
    
    def on_edge_added(self, source, target, relation, weight):
        self.edges.append((source, target))


class TestBasePlugin:
    """测试插件基础类"""
    
    def test_plugin_creation(self):
        """测试插件创建"""
        plugin = SimpleTestPlugin()
        assert plugin.name == "simple_test"
        assert plugin.version == "0.1.0"
        assert not plugin.is_initialized
        assert plugin.is_enabled
    
    def test_plugin_enable_disable(self):
        """测试插件启用/禁用"""
        plugin = SimpleTestPlugin()
        plugin.set_enabled(False)
        assert not plugin.is_enabled
        plugin.set_enabled(True)
        assert plugin.is_enabled


class TestPluginManager:
    """测试插件管理器"""
    
    def test_register_plugin(self):
        """测试插件注册"""
        manager = PluginManager()
        plugin = SimpleTestPlugin()
        
        success = manager.register_plugin(plugin)
        assert success
        
        # 重复注册应该失败
        success = manager.register_plugin(plugin)
        assert not success
        
        # 验证插件已注册
        plugins = manager.list_plugins()
        assert len(plugins) == 1
        assert plugins[0]["name"] == "simple_test"
    
    def test_unregister_plugin(self):
        """测试插件注销"""
        manager = PluginManager()
        plugin = SimpleTestPlugin()
        
        manager.register_plugin(plugin)
        assert len(manager.list_plugins()) == 1
        
        success = manager.unregister_plugin("simple_test")
        assert success
        
        success = manager.unregister_plugin("non_existent")
        assert not success
    
    def test_get_plugin(self):
        """测试获取插件"""
        manager = PluginManager()
        plugin = SimpleTestPlugin()
        manager.register_plugin(plugin)
        
        retrieved = manager.get_plugin("simple_test")
        assert retrieved is not None
        assert retrieved.name == "simple_test"
        
        assert manager.get_plugin("non_existent") is None
    
    def test_task_handlers_from_plugin(self):
        """测试从插件获取任务处理器"""
        manager = PluginManager()
        plugin = SimpleTestPlugin()
        manager.register_plugin(plugin)
        
        handlers = manager.get_task_handlers()
        assert "test_task" in handlers


class TestAgentPluginIntegration:
    """测试 Agent 与插件集成"""
    
    def test_agent_has_plugin_manager(self):
        """测试 Agent 有插件管理器"""
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            kg_path = f.name
        
        try:
            agent = EternalSelfAgent(kg_save_path=kg_path, loop_delay=0.001)
            assert hasattr(agent, "plugin_manager")
            assert isinstance(agent.plugin_manager, PluginManager)
            agent.shutdown()
        finally:
            if os.path.exists(kg_path):
                os.remove(kg_path)
            if os.path.exists("eternal_self_agent.log"):
                os.remove("eternal_self_agent.log")
    
    def test_register_plugin_to_agent(self):
        """测试向 Agent 注册插件"""
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            kg_path = f.name
        
        try:
            agent = EternalSelfAgent(kg_save_path=kg_path, loop_delay=0.001)
            plugin = SimpleTestPlugin()
            
            success = agent.register_plugin(plugin)
            assert success
            
            plugins = agent.list_plugins()
            assert len(plugins) == 1
            assert plugins[0]["name"] == "simple_test"
            
            agent.shutdown()
        finally:
            if os.path.exists(kg_path):
                os.remove(kg_path)
            if os.path.exists("eternal_self_agent.log"):
                os.remove("eternal_self_agent.log")
    
    def test_plugin_task_handler_executes(self):
        """测试插件任务处理器执行"""
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            kg_path = f.name
        
        try:
            agent = EternalSelfAgent(kg_save_path=kg_path, loop_delay=0.001)
            plugin = SimpleTestPlugin()
            agent.register_plugin(plugin)
            
            # 执行任务
            agent.execute_task("test_task:do_something")
            
            # 验证任务执行了
            assert agent.knowledge_graph.has_node("test_node")
            
            agent.shutdown()
        finally:
            if os.path.exists(kg_path):
                os.remove(kg_path)
            if os.path.exists("eternal_self_agent.log"):
                os.remove("eternal_self_agent.log")
    
    def test_example_plugins(self):
        """测试示例插件"""
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            kg_path = f.name
        
        try:
            agent = EternalSelfAgent(kg_save_path=kg_path, loop_delay=0.001)
            
            # 注册示例插件
            hello_plugin = HelloWorldPlugin()
            counter_plugin = CounterPlugin()
            
            agent.register_plugin(hello_plugin)
            agent.register_plugin(counter_plugin)
            
            # 执行示例任务
            agent.execute_task("greet:TestUser")
            agent.execute_task("count:1")
            agent.execute_task("count:2")
            
            # 验证
            assert agent.knowledge_graph.has_node("greeted:TestUser")
            # 检查计数器插件被正确初始化
            plugin = agent.plugin_manager.get_plugin("counter")
            assert plugin is not None
            assert plugin.counter >= 2
            
            agent.shutdown()
        finally:
            if os.path.exists(kg_path):
                os.remove(kg_path)
            if os.path.exists("eternal_self_agent.log"):
                os.remove("eternal_self_agent.log")
    
    def test_backward_compatibility(self):
        """测试向后兼容性"""
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            kg_path = f.name
        
        try:
            # 确保 Agent 的旧功能仍然正常
            agent = EternalSelfAgent(kg_save_path=kg_path, loop_delay=0.001)
            
            # 测试旧 API
            assert agent.knowledge_graph is not None
            assert agent.task_queue is not None
            
            # 测试注册旧的任务处理器方式
            called = [False]
            def old_handler(task, a):
                called[0] = True
            
            agent.register_task_handler("old_task", old_handler)
            agent.execute_task("old_task:something")
            
            assert called[0]
            
            agent.shutdown()
        finally:
            if os.path.exists(kg_path):
                os.remove(kg_path)
            if os.path.exists("eternal_self_agent.log"):
                os.remove("eternal_self_agent.log")
    
    def test_knowledge_processor_plugin(self):
        """测试知识处理插件"""
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            kg_path = f.name
        
        try:
            agent = EternalSelfAgent(kg_save_path=kg_path, loop_delay=0.001)
            plugin = SimpleKnowledgeProcessor()
            
            agent.register_plugin(plugin)
            
            # 添加节点和边
            agent.knowledge_graph.add_node("test_node1")
            agent.knowledge_graph.add_node("test_node2")
            agent.knowledge_graph.add_edge("test_node1", "test_node2", "related", 0.5)
            
            # 验证回调被触发
            assert "test_node1" in plugin.nodes
            assert "test_node2" in plugin.nodes
            assert ("test_node1", "test_node2") in plugin.edges
            
            agent.shutdown()
        finally:
            if os.path.exists(kg_path):
                os.remove(kg_path)
            if os.path.exists("eternal_self_agent.log"):
                os.remove("eternal_self_agent.log")
    
    def test_unregister_knowledge_processor_plugin(self):
        """测试注销知识处理插件"""
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            kg_path = f.name
        
        try:
            agent = EternalSelfAgent(kg_save_path=kg_path, loop_delay=0.001)
            plugin = SimpleKnowledgeProcessor()
            
            agent.register_plugin(plugin)
            
            # 添加节点以触发回调
            agent.knowledge_graph.add_node("before_unregister")
            
            # 注销插件
            agent.unregister_plugin("simple_kp")
            
            # 再添加节点，应该不会触发回调
            agent.knowledge_graph.add_node("after_unregister")
            
            # 验证
            assert "before_unregister" in plugin.nodes
            assert "after_unregister" not in plugin.nodes
            
            agent.shutdown()
        finally:
            if os.path.exists(kg_path):
                os.remove(kg_path)
            if os.path.exists("eternal_self_agent.log"):
                os.remove("eternal_self_agent.log")
    
    def test_knowledge_monitor_plugin(self):
        """测试知识监控插件"""
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            kg_path = f.name
        
        try:
            agent = EternalSelfAgent(kg_save_path=kg_path, loop_delay=0.001)
            plugin = KnowledgeMonitorPlugin()
            
            agent.register_plugin(plugin)
            
            # 添加一些节点和边
            agent.knowledge_graph.add_node("node1")
            agent.knowledge_graph.add_node("node2")
            agent.knowledge_graph.add_edge("node1", "node2", "connected", 0.7)
            agent.knowledge_graph.add_node("node3")
            agent.knowledge_graph.add_edge("node2", "node3", "linked", 0.6)
            
            # 验证统计
            stats = plugin.get_statistics()
            assert stats["node_count"] >= 3
            assert stats["edge_count"] >= 2
            
            agent.shutdown()
        finally:
            if os.path.exists(kg_path):
                os.remove(kg_path)
            if os.path.exists("eternal_self_agent.log"):
                os.remove("eternal_self_agent.log")

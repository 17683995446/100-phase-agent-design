import tempfile
import os
from core import EternalSelfAgent
from plugins.counter_plugin import CounterPlugin


def test_counter_plugin():
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        kg_path = f.name
    
    try:
        agent = EternalSelfAgent(kg_save_path=kg_path, loop_delay=0.001)
        
        counter_plugin = CounterPlugin()
        agent.register_plugin(counter_plugin)
        
        # 测试插件注册
        plugins = agent.list_plugins()
        print("Plugins:", plugins)
        
        # 检查任务处理器
        print("\nTask handlers from manager:", agent.plugin_manager.get_task_handlers())
        
        # 执行任务
        print("\nExecuting count task...")
        agent.execute_task("count")
        
        # 查看节点
        print("\nNodes:", list(agent.knowledge_graph.nodes.keys()))
        
        # 查看计数器
        plugin = agent.plugin_manager.get_plugin("counter")
        print("\nPlugin counter:", plugin.counter if plugin else "Not found")
        
        agent.shutdown()
        
    finally:
        if os.path.exists(kg_path):
            os.remove(kg_path)
        if os.path.exists("eternal_self_agent.log"):
            os.remove("eternal_self_agent.log")


if __name__ == "__main__":
    test_counter_plugin()

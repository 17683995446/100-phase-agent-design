#!/usr/bin/env python3
"""
插件系统使用示例
"""

import tempfile
import os
from core import EternalSelfAgent
from plugins.hello_plugin import HelloWorldPlugin
from plugins.counter_plugin import CounterPlugin


def main():
    print("=" * 60)
    print("插件系统使用示例")
    print("=" * 60)
    
    # 创建临时文件
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        kg_path = f.name
    
    try:
        # 初始化 Agent
        agent = EternalSelfAgent(kg_save_path=kg_path, loop_delay=0.001)
        
        print("\n1. 注册插件...")
        hello_plugin = HelloWorldPlugin()
        counter_plugin = CounterPlugin()
        
        agent.register_plugin(hello_plugin)
        agent.register_plugin(counter_plugin)
        print(f"   已注册插件: {[p['name'] for p in agent.list_plugins()]}")
        
        print("\n2. 执行插件任务...")
        
        # 执行 Hello 任务
        print("\n   执行任务: greet:John")
        agent.execute_task("greet:John")
        
        # 执行计数任务
        print("   执行任务: count:1")
        agent.execute_task("count:1")
        
        print("   执行任务: count:2")
        agent.execute_task("count:2")
        
        print("   执行任务: greet:Alice")
        agent.execute_task("greet:Alice")
        
        print("\n3. 查看知识图谱内容...")
        print(f"   节点数: {agent.knowledge_graph.get_node_count()}")
        print(f"   节点列表: {list(agent.knowledge_graph.nodes.keys())[:10]}")
        
        print("\n4. 查看指标...")
        print(f"   运行时间: {agent.metrics.get_uptime():.2f}s")
        print(f"   导出指标: {len(agent.metrics.export())} 项")
        
        print("\n5. 健康检查...")
        health = agent.enhanced_health_check()
        print(f"   总体健康: {health['overall']}")
        
        print("\n6. 插件状态...")
        counter = agent.plugin_manager.get_plugin("counter")
        print(f"   计数器插件计数: {counter.counter if counter else 'N/A'}")
        
        print("\n7. 关闭系统...")
        agent.shutdown()
        
        print("\n" + "=" * 60)
        print("示例运行完成！")
        print("=" * 60)
        
    finally:
        # 清理临时文件
        if os.path.exists(kg_path):
            os.remove(kg_path)
        if os.path.exists("eternal_self_agent.log"):
            try:
                os.remove("eternal_self_agent.log")
            except:
                pass


if __name__ == "__main__":
    main()

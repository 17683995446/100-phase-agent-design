#!/usr/bin/env python3
"""
插件系统完整示例演示
"""

import tempfile
import os
from core import EternalSelfAgent
from plugins.hello_plugin import HelloWorldPlugin
from plugins.counter_plugin import CounterPlugin
from plugins.knowledge_monitor import KnowledgeMonitorPlugin


def main():
    print("=" * 70)
    print("       第一原理轻量级永动机知识图谱智能体 - 插件系统演示")
    print("=" * 70)
    
    # 创建临时文件
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        kg_path = f.name
    
    try:
        print("\n[1/6] 初始化智能体...")
        agent = EternalSelfAgent(kg_save_path=kg_path, loop_delay=0.001)
        
        print("\n[2/6] 注册插件...")
        # 注册 HelloWorld 插件
        hello_plugin = HelloWorldPlugin()
        success = agent.register_plugin(hello_plugin)
        print(f"  - HelloWorld 插件注册: {'✓ 成功' if success else '✗ 失败'}")
        
        # 注册 Counter 插件
        counter_plugin = CounterPlugin()
        success = agent.register_plugin(counter_plugin)
        print(f"  - Counter 插件注册: {'✓ 成功' if success else '✗ 失败'}")
        
        # 注册 KnowledgeMonitor 插件
        monitor_plugin = KnowledgeMonitorPlugin()
        success = agent.register_plugin(monitor_plugin)
        print(f"  - KnowledgeMonitor 插件注册: {'✓ 成功' if success else '✗ 失败'}")
        
        # 列出所有插件
        plugins = agent.list_plugins()
        print(f"\n  已注册的插件: {len(plugins)} 个")
        for p in plugins:
            print(f"    - {p['name']} v{p['version']}: {p['description']}")
        
        print("\n[3/6] 执行 Hello 任务...")
        agent.execute_task("greet:Alice")
        agent.execute_task("greet:Bob")
        
        print("\n[4/6] 执行计数任务...")
        for i in range(1, 4):
            agent.execute_task(f"count:{i}")
        
        print("\n[5/6] 获取监控统计...")
        stats = monitor_plugin.get_statistics()
        print(f"  - 监控到的节点数: {stats['node_count']}")
        print(f"  - 监控到的边数: {stats['edge_count']}")
        print(f"  - 最新节点: {stats['last_nodes']}")
        
        print("\n[6/6] 查看系统指标...")
        metrics = agent.get_metrics()
        print(f"  - 运行时间: {metrics['uptime']:.2f}秒")
        print(f"  - 指标数量: {len(metrics['metrics'])}")
        
        print("\n健康检查:")
        health = agent.enhanced_health_check()
        print(f"  - 系统存活: {health['system_alive']}")
        print(f"  - 知识图谱: {health['knowledge_graph']}")
        print(f"  - 任务队列: {health['task_queue']}")
        print(f"  - 总体健康: {health['overall']}")
        
        print("\n知识图谱状态:")
        print(f"  - 节点数量: {agent.knowledge_graph.get_node_count()}")
        print(f"  - 边数量: {agent.knowledge_graph.get_edge_count()}")
        
        print("\n关闭系统...")
        agent.shutdown()
        
        print("\n" + "=" * 70)
        print("演示完成！所有功能正常工作！")
        print("=" * 70)
        
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

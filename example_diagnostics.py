#!/usr/bin/env python3
"""
系统诊断工具使用示例
"""

import os
import tempfile
from core import (
    EternalSelfAgent,
    SystemDiagnostics,
    DiagnosticResult,
    diagnose_agent
)


def example_basic_diagnostics():
    """基本诊断功能示例"""
    print("=" * 70)
    print("基本系统诊断示例")
    print("=" * 70)
    
    # 创建诊断工具
    diagnostic = SystemDiagnostics()
    
    # 运行所有内置检查
    print("\n运行所有诊断检查...")
    results = diagnostic.run_all_checks()
    
    print(f"\n检查完成，共 {len(results)} 个检查")
    
    # 显示摘要
    summary = diagnostic.get_summary()
    print(f"\n摘要:")
    print(f"  健康: {summary['healthy']}")
    print(f"  警告: {summary['warning']}")
    print(f"  错误: {summary['error']}")
    print(f"  总体状态: {summary['overall_status'].upper()}")
    
    # 显示完整报告
    print("\n" + diagnostic.generate_report())


def example_agent_diagnostics():
    """智能体诊断示例"""
    print("\n" + "=" * 70)
    print("智能体诊断示例")
    print("=" * 70)
    
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        kg_path = f.name
    
    try:
        # 创建智能体
        print("\n创建智能体...")
        agent = EternalSelfAgent(kg_save_path=kg_path, loop_delay=0.001)
        
        # 添加一些数据
        print("添加一些知识...")
        for i in range(5):
            agent.knowledge_graph.add_node(f"node_{i}")
        agent.knowledge_graph.add_edge("node_0", "node_1", "related", 0.8)
        agent.knowledge_graph.add_edge("node_1", "node_2", "related", 0.7)
        agent.knowledge_graph.add_edge("node_2", "node_3", "related", 0.6)
        
        # 添加一些任务
        print("添加一些任务...")
        for i in range(3):
            agent.task_queue.add(f"task_{i}")
        
        # 运行诊断
        print("\n运行智能体诊断...")
        diag_result = diagnose_agent(agent)
        
        # 显示报告
        print("\n诊断报告:")
        print(diag_result["report"])
        
        # 关闭智能体
        agent.shutdown()
    finally:
        if os.path.exists(kg_path):
            os.remove(kg_path)


def example_custom_checks():
    """自定义检查示例"""
    print("\n" + "=" * 70)
    print("自定义检查示例")
    print("=" * 70)
    
    diagnostic = SystemDiagnostics()
    
    # 添加自定义检查
    def custom_check():
        return DiagnosticResult(
            component="custom_check",
            status="healthy",
            message="自定义检查通过",
            details={"test": "value"}
        )
    
    print("\n注册自定义检查...")
    diagnostic.register_check("custom", custom_check)
    
    # 运行检查
    results = diagnostic.run_all_checks()
    print(f"\n运行了 {len(results)} 个检查，包括自定义检查")
    
    # 检查自定义检查是否执行
    custom_found = any(r.component == "custom_check" for r in results)
    print(f"\n自定义检查执行: {'是' if custom_found else '否'}")


def main():
    print("\n" + "=" * 70)
    print("    第一原理轻量级永动机知识图谱智能体")
    print("    系统诊断工具使用示例")
    print("=" * 70 + "\n")
    
    example_basic_diagnostics()
    example_agent_diagnostics()
    example_custom_checks()
    
    print("\n" + "=" * 70)
    print("示例执行完成！")
    print("=" * 70)


if __name__ == "__main__":
    main()

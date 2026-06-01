#!/usr/bin/env python3
import sys
import os
import time
import tempfile
import gc
import random
import signal
sys.path.insert(0, '/workspace')

from core import EternalSelfAgent


def test_high_load_task_queue(agent, task_count=1000):
    """高负载任务队列测试"""
    print(f"[高负载测试] 添加 {task_count} 个任务...")
    
    added_count = 0
    start_time = time.time()
    
    for i in range(task_count):
        success = agent.task_queue.add(f"load_task_{i}")
        if success:
            added_count += 1
    
    elapsed = time.time() - start_time
    
    print(f"  ✓ 添加了 {added_count}/{task_count} 个任务")
    print(f"  ✓ 队列大小: {agent.task_queue.size()}")
    print(f"  ✓ 耗时: {elapsed:.4f}秒")
    
    return added_count


def test_knowledge_expansion(agent, node_count=500, edge_count=1000):
    """知识扩展测试"""
    print(f"[知识扩展测试] 添加 {node_count} 个节点和 {edge_count} 条边...")
    
    start_time = time.time()
    
    # 添加节点
    for i in range(node_count):
        agent.knowledge_graph.add_node(f"node_{i}")
    
    # 添加边
    for i in range(edge_count):
        source = f"node_{random.randint(0, node_count-1)}"
        target = f"node_{random.randint(0, node_count-1)}"
        weight = random.random()
        agent.knowledge_graph.add_edge(source, target, f"rel_{i}", weight)
    
    elapsed = time.time() - start_time
    
    print(f"  ✓ 节点数: {agent.knowledge_graph.get_node_count()}")
    print(f"  ✓ 边数: {agent.knowledge_graph.get_edge_count()}")
    print(f"  ✓ 耗时: {elapsed:.4f}秒")


def test_concurrent_task_execution(agent, task_count=200):
    """连续任务执行测试"""
    print(f"[任务执行测试] 执行 {task_count} 个任务...")
    
    start_time = time.time()
    
    for i in range(task_count):
        agent.execute_task(f"exec_task_{i}")
    
    elapsed = time.time() - start_time
    avg_time = elapsed / task_count if task_count > 0 else 0
    
    print(f"  ✓ 执行了 {agent.tasks_executed} 个任务")
    print(f"  ✓ 平均任务时间: {avg_time:.6f}秒")
    print(f"  ✓ 总耗时: {elapsed:.4f}秒")


def test_memory_usage_monitoring(agent, iterations=5):
    """内存使用监控测试"""
    print("[内存监控测试]")
    
    memory_usage_samples = []
    
    for i in range(iterations):
        # 执行一些任务
        for j in range(50):
            agent.execute_task(f"mem_task_{i}_{j}")
        
        # 强制GC
        gc.collect()
        
        memory = agent._get_memory_usage()
        memory_usage_samples.append(memory)
        print(f"  迭代 {i+1}: {memory:.2f}MB")
    
    # 计算内存增长
    if len(memory_usage_samples) > 1:
        memory_growth = memory_usage_samples[-1] - memory_usage_samples[0]
        print(f"  ✓ 内存增长: {memory_growth:.2f}MB")
        
        if memory_growth > 10:
            print("  ⚠  内存增长较大，可能存在泄漏")
        else:
            print("  ✓ 内存使用稳定")


def simulate_long_running(agent, duration_seconds=5):
    """模拟长时间运行"""
    print(f"[长时间运行模拟] 运行 {duration_seconds} 秒...")
    
    start_time = time.time()
    cycles = 0
    
    while time.time() - start_time < duration_seconds:
        # 运行一个短循环
        for i in range(5):
            agent.health_check()
            if not agent.task_queue.is_empty():
                task = agent.get_current_task()
                if task:
                    agent.execute_task(task)
        
        # 空闲时添加一些任务
        if agent.task_queue.is_empty():
            agent.task_queue.add(f"idle_task_{cycles}")
        
        cycles += 1
        time.sleep(0.01)
    
    print(f"  ✓ 运行了 {cycles} 个周期")


def run_stress_test():
    """运行完整压力测试"""
    print("=" * 60)
    print("第9阶段 - 系统集成与压力测试")
    print("=" * 60)
    
    temp_dir = tempfile.mkdtemp()
    config_path = os.path.join(temp_dir, "config.json")
    
    try:
        agent = EternalSelfAgent(config_path=config_path, loop_delay=0)
        
        print("\n" + "=" * 60)
        print("测试开始")
        print("=" * 60)
        
        # 1. 高负载任务队列测试
        test_high_load_task_queue(agent, task_count=1000)
        
        # 2. 知识扩展测试
        test_knowledge_expansion(agent, node_count=200, edge_count=400)
        
        # 3. 任务执行测试
        test_concurrent_task_execution(agent, task_count=200)
        
        # 4. 内存监控测试
        test_memory_usage_monitoring(agent, iterations=5)
        
        # 5. 长时间运行模拟
        simulate_long_running(agent, duration_seconds=3)
        
        # 打印最终状态报告
        agent.print_status_report()
        
        # 验证系统仍然存活
        assert agent.system_alive, "系统应该保持存活"
        
        print("\n" + "=" * 60)
        print("所有压力测试通过！")
        print("=" * 60)
        
        agent.shutdown()
        
    finally:
        try:
            import shutil
            shutil.rmtree(temp_dir)
        except Exception:
            pass


if __name__ == "__main__":
    # 设置信号处理器
    def signal_handler(sig, frame):
        print("\n\n接收到中断信号，正在停止测试...")
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    
    run_stress_test()
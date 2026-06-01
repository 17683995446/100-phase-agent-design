#!/usr/bin/env python3
import sys
import os
import time
import tempfile
import gc
sys.path.insert(0, '/workspace')

from core import EternalSelfAgent


def benchmark_task_execution(task_count=1000):
    """基准测试：任务执行性能"""
    print("=" * 60)
    print(f"基准测试：任务执行 ({task_count} 个任务)")
    print("=" * 60)
    
    temp_dir = tempfile.mkdtemp()
    config_path = os.path.join(temp_dir, "config.json")
    
    try:
        agent = EternalSelfAgent(
            config_path=config_path,
            loop_delay=0  # 无延迟，快速测试
        )
        
        # 预热
        print("\n[预热中...]")
        for i in range(10):
            agent.execute_task(f"warmup_task_{i}")
        
        print("\n[正式测试中...]")
        gc.collect()
        gc.disable()  # 禁用GC来准确测量
        start_time = time.time()
        start_memory = agent._get_memory_usage()
        
        # 执行测试
        for i in range(task_count):
            agent.execute_task(f"test_task_{i}")
        
        elapsed = time.time() - start_time
        end_memory = agent._get_memory_usage()
        gc.enable()
        
        avg_task_time = elapsed / task_count
        
        print("\n" + "=" * 60)
        print("测试结果")
        print("=" * 60)
        print(f"总任务数: {task_count}")
        print(f"总执行时间: {elapsed:.4f}秒")
        print(f"平均任务时间: {avg_task_time:.6f}秒")
        print(f"内存变化: {(end_memory - start_memory):.2f}MB")
        print(f"节点数: {agent.knowledge_graph.get_node_count()}")
        print(f"边数: {agent.knowledge_graph.get_edge_count()}")
        
        agent.shutdown()
        
        return {
            "task_count": task_count,
            "total_time": elapsed,
            "avg_task_time": avg_task_time,
            "memory_change": end_memory - start_memory,
            "node_count": agent.knowledge_graph.get_node_count(),
            "edge_count": agent.knowledge_graph.get_edge_count()
        }
        
    finally:
        try:
            import shutil
            shutil.rmtree(temp_dir)
        except Exception:
            pass


def benchmark_knowledge_evolution():
    """基准测试：知识进化性能"""
    print("\n" + "=" * 60)
    print("基准测试：知识进化")
    print("=" * 60)
    
    temp_dir = tempfile.mkdtemp()
    config_path = os.path.join(temp_dir, "config.json")
    
    try:
        agent = EternalSelfAgent(
            config_path=config_path,
            evolve_step=50
        )
        
        print("\n[测试知识进化...]")
        start_time = time.time()
        
        # 执行多次，触发知识进化
        for i in range(200):
            agent.execute_task(f"evo_task_{i}")
        
        elapsed = time.time() - start_time
        
        print("\n" + "=" * 60)
        print("测试结果")
        print("=" * 60)
        print(f"进化次数: {agent.evolution_count}")
        print(f"总执行时间: {elapsed:.4f}秒")
        print(f"执行任务数: {agent.tasks_executed}")
        
        agent.shutdown()
        
        return {
            "evolution_count": agent.evolution_count,
            "total_time": elapsed,
            "tasks_executed": agent.tasks_executed
        }
        
    finally:
        try:
            import shutil
            shutil.rmtree(temp_dir)
        except Exception:
            pass


def benchmark_memory_leak_check(iterations=5):
    """基准测试：内存泄漏检查"""
    print("\n" + "=" * 60)
    print("基准测试：内存泄漏检查")
    print("=" * 60)
    
    temp_dir = tempfile.mkdtemp()
    config_path = os.path.join(temp_dir, "config.json")
    
    try:
        agent = EternalSelfAgent(config_path=config_path)
        memory_samples = []
        
        for i in range(iterations):
            print(f"\n[迭代 {i+1}/{iterations}]")
            
            # 执行一些任务
            for j in range(100):
                agent.execute_task(f"memory_test_task_{i}_{j}")
            
            # 强制GC并采样
            gc.collect()
            memory = agent._get_memory_usage()
            memory_samples.append(memory)
            print(f"  - 内存使用: {memory:.2f}MB")
        
        # 分析内存变化
        memory_growth = memory_samples[-1] - memory_samples[0]
        
        print("\n" + "=" * 60)
        print("测试结果")
        print("=" * 60)
        print(f"内存增长: {memory_growth:.2f}MB")
        print(f"内存样本: {memory_samples}")
        
        agent.shutdown()
        
        return {
            "memory_samples": memory_samples,
            "memory_growth": memory_growth
        }
        
    finally:
        try:
            import shutil
            shutil.rmtree(temp_dir)
        except Exception:
            pass


def run_full_benchmark():
    """运行完整基准测试"""
    print("=" * 60)
    print("第9阶段 - 系统性能基准测试")
    print("=" * 60)
    
    results = {}
    
    # 1. 任务执行基准测试
    results["task_execution"] = benchmark_task_execution(task_count=1000)
    
    # 2. 知识进化基准测试
    results["knowledge_evolution"] = benchmark_knowledge_evolution()
    
    # 3. 内存泄漏检查
    results["memory_leak_check"] = benchmark_memory_leak_check(iterations=5)
    
    # 总结报告
    print("\n" + "=" * 60)
    print("基准测试总结")
    print("=" * 60)
    
    avg_task_time = results["task_execution"]["avg_task_time"]
    memory_growth = results["memory_leak_check"]["memory_growth"]
    
    print(f"✓ 任务执行平均时间: {avg_task_time:.6f}秒")
    print(f"✓ 内存增长: {memory_growth:.2f}MB")
    
    # 简单评估
    if avg_task_time < 0.01:
        print("✓ 性能优秀！")
    elif avg_task_time < 0.1:
        print("✓ 性能良好")
    else:
        print("⚠ 需要优化")
    
    if memory_growth < 5:
        print("✓ 无明显内存泄漏")
    else:
        print("⚠ 可能存在内存泄漏")
    
    print("=" * 60)
    
    return results


if __name__ == "__main__":
    run_full_benchmark()
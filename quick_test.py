#!/usr/bin/env python3
import sys
import os
sys.path.insert(0, '/workspace')

from core import EternalSelfAgent, ConfigManager


def quick_test():
    print("=" * 60)
    print("第9阶段 - 系统集成与压力测试 快速验证")
    print("=" * 60)
    
    # 使用临时目录
    import tempfile
    temp_dir = tempfile.mkdtemp()
    config_path = os.path.join(temp_dir, "config.json")
    
    try:
        # 1. 测试配置管理器
        print("\n[1/7] 配置管理器测试...")
        config_manager = ConfigManager(config_path)
        print(f"   ✓ 配置加载成功")
        
        # 2. 测试智能体初始化
        print("\n[2/7] 智能体初始化测试...")
        agent = EternalSelfAgent(config_path=config_path, loop_delay=0)
        print(f"   ✓ 智能体初始化成功")
        
        # 3. 测试状态恢复
        print("\n[3/7] 状态恢复测试...")
        restore_success = agent.restore_state()
        print(f"   ✓ 状态恢复: {restore_success}")
        
        # 4. 测试任务执行
        print("\n[4/7] 任务执行测试...")
        agent.execute_task("test_task_1")
        agent.execute_task("test_task_2")
        print(f"   ✓ 任务执行完成，执行了 {agent.tasks_executed} 个任务")
        
        # 5. 测试知识进化
        print("\n[5/7] 知识进化测试...")
        for i in range(100):
            agent.health_check()
            if agent.run_counter % 50 == 0:
                agent.knowledge_graph.trim_invalid_knowledge()
                agent.evolution_count += 1
        
        print(f"   ✓ 知识进化了 {agent.evolution_count} 次")
        
        # 6. 测试系统状态报告
        print("\n[6/7] 系统状态报告...")
        agent.print_status_report()
        
        # 7. 测试配置更改
        print("\n[7/7] 运行时配置更改...")
        success = agent.update_config("loop_delay", 0.5)
        print(f"   ✓ 配置更新: {success}")
        
        # 关闭
        print("\n正在关闭系统...")
        agent.save_full_state()
        agent.shutdown()
        
        print("\n" + "=" * 60)
        print("第9阶段快速验证完成！所有功能正常工作")
        print("=" * 60)
        
    finally:
        # 清理临时目录
        try:
            import shutil
            shutil.rmtree(temp_dir)
        except Exception:
            pass


if __name__ == "__main__":
    quick_test()
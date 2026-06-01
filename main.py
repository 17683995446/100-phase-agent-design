#!/usr/bin/env python3
import sys
import time
from core import EternalSelfAgent


def main():
    print("=" * 60)
    print("启动永动知识图谱智能体 - 第8阶段")
    print("=" * 60)
    
    try:
        agent = EternalSelfAgent(config_path="config.json")
        
        # 恢复状态
        restore_success = agent.restore_state()
        
        # 添加初始任务（如果是新系统）
        if not agent.knowledge_graph.has_node("系统初始认知迭代"):
            initial_task = "系统初始认知迭代"
            agent.task_queue.add(initial_task)
            agent.knowledge_graph.add_node(initial_task)
            print(f"\n✅ 已添加初始任务: {initial_task}")
        
        # 显示启动信息
        print("\n📊 当前系统状态:")
        status = agent.get_system_status()
        print(f"   - 运行计数器: {status['run_counter']}")
        print(f"   - 队列大小: {status['queue_size']}")
        print(f"   - 知识节点: {status['node_count']}")
        print(f"   - 知识边: {status['edge_count']}")
        print(f"   - 系统状态: {'运行中' if status['system_alive'] else '已停止'}")
        print(f"   - 运行时长: {status['uptime']:.2f}秒")
        print(f"   - 处理历史: {status['processed_history_size']}条")
        
        if restore_success:
            print(f"\n✅ 状态恢复成功")
        else:
            print(f"\n⚠️ 状态恢复失败，使用全新系统")
        
        print(f"\nℹ️ 按 Ctrl+C 可优雅退出")
        print("-" * 60)
        
        # 启动主循环
        agent.eternal_loop()
        
    except KeyboardInterrupt:
        print("\n\n⚠️ 检测到中断信号，正在关闭...")
    except Exception as e:
        print(f"\n❌ 发生严重错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
阶段106：自循环主循环

第一性原理：
  - 自驱公理：系统必须能自主产生任务并执行
  - 存续公理：必须永不崩溃，必须能优雅停止
  - 记忆公理：状态必须可持久化
  - 适应性：必须能根据负载自适应调整节奏

本阶段产出：
  1. MainLoop：核心主循环
  2. AdaptiveInterval：自适应循环间隔
  3. TaskGenerator：自主任务生成器
  4. ReflectionEngine：反思与自调整
  5. GracefulStopper：优雅停止器
  6. 集成测试

遵循原则：图难于其易，为大于其细
"""
import time
import signal
import random
import unittest
import threading
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from enum import Enum

import sys
sys.path.insert(0, '/workspace')
from phase_105_task_queue import (
    Task, TaskQueue, TaskScheduler, TaskStatus, TaskPriority
)
from phase_104_json_persistence import PersistentKnowledgeGraph
from phase_102_core_datastructure import Node, Edge


# ============================================================
# 一、自适应循环间隔
# ============================================================
class AdaptiveInterval:
    """自适应循环间隔

    原理：
    - 默认间隔内空闲 -> 延长间隔（节能）
    - 队列积压 -> 缩短间隔（加速）
    - 资源紧张 -> 延长间隔（保护）

    第一性原理：系统的运行节奏应与环境匹配
    """
    def __init__(self, default: float = 1.0,
                 min_interval: float = 0.1,
                 max_interval: float = 10.0):
        self.default = default
        self.min_interval = min_interval
        self.max_interval = max_interval
        self.current = default
        self._recent_durations: List[float] = []
        self._consecutive_idle = 0

    def adjust(self, queue_size: int, last_duration: float,
               resource_pressure: float = 0.0) -> float:
        """调整间隔

        Args:
            queue_size: 当前队列大小
            last_duration: 上一个循环耗时
            resource_pressure: 资源压力 [0, 1]
        Returns:
            调整后的间隔
        """
        # 队列有积压 -> 加速
        if queue_size > 5:
            self.current = max(self.min_interval, self.current * 0.8)
            self._consecutive_idle = 0
        # 队列为空且持续空闲 -> 节能
        elif queue_size == 0:
            self._consecutive_idle += 1
            if self._consecutive_idle > 3:
                self.current = min(self.max_interval, self.current * 1.2)
        # 资源压力 -> 保护性减速
        if resource_pressure > 0.7:
            self.current = min(self.max_interval, self.current * 1.5)
        # 限制在合法范围
        self.current = max(self.min_interval,
                          min(self.max_interval, self.current))
        return self.current

    def get_current(self) -> float:
        return self.current


# ============================================================
# 二、自主任务生成器
# ============================================================
class TaskGenerator:
    """自主任务生成器

    第一性原理：自驱公理要求系统能自主产生任务
    """
    TASK_TEMPLATES = [
        ("explore", 0.3, lambda kg: len(kg.nodes) < 50),
        ("connect_ideas", 0.25, lambda kg: len(kg.nodes) >= 2),
        ("prune_weak", 0.15, lambda kg: len(kg.edges) > 10),
        ("reflect", 0.1, lambda kg: True),
        ("discover_relation", 0.1, lambda kg: len(kg.nodes) >= 3),
        ("consolidate", 0.1, lambda kg: len(kg.nodes) > 5),
    ]

    def __init__(self, kg: PersistentKnowledgeGraph):
        self.kg = kg
        self._last_generation = 0.0
        self._min_interval = 0.5  # 至少间隔0.5秒再生成新任务

    def maybe_generate(self, force: bool = False) -> Optional[Task]:
        """根据条件生成任务

        Args:
            force: 强制生成（忽略最小间隔限制）
        """
        now = time.time()
        if not force and now - self._last_generation < self._min_interval:
            return None
        # 随机选择一个模板
        candidates = [t for t in self.TASK_TEMPLATES if t[2](self.kg)]
        if not candidates:
            return None
        # 加权选择
        weights = [t[1] for t in candidates]
        name, _, _ = random.choices(candidates, weights=weights, k=1)[0]
        self._last_generation = now
        return Task(
            name=name,
            priority=TaskPriority.NORMAL.value,
            tags=["auto_generated"]
        )


# ============================================================
# 三、反思引擎
# ============================================================
class ReflectionEngine:
    """反思引擎

    在每个循环中评估系统状态，调整运行参数
    """
    def __init__(self):
        self._cycle_history: List[Dict[str, Any]] = []
        self._last_reflection = 0.0
        self._reflection_interval = 10.0  # 每10秒反思一次

    def record_cycle(self, cycle_num: int, queue_size: int,
                     duration: float, success: int, failed: int) -> None:
        """记录循环信息"""
        self._cycle_history.append({
            "cycle": cycle_num,
            "queue_size": queue_size,
            "duration": duration,
            "success": success,
            "failed": failed,
            "timestamp": time.time()
        })
        # 限制历史长度
        if len(self._cycle_history) > 1000:
            self._cycle_history = self._cycle_history[-1000:]

    def maybe_reflect(self) -> Optional[Dict[str, Any]]:
        """触发反思，返回调整建议"""
        now = time.time()
        if now - self._last_reflection < self._reflection_interval:
            return None
        if len(self._cycle_history) < 5:
            return None
        self._last_reflection = now
        recent = self._cycle_history[-20:]
        avg_duration = sum(c["duration"] for c in recent) / len(recent)
        total = sum(c["success"] + c["failed"] for c in recent) or 1
        success_rate = sum(c["success"] for c in recent) / total
        return {
            "type": "reflection",
            "avg_duration": avg_duration,
            "success_rate": success_rate,
            "recent_cycles": len(recent),
            "recommendation": self._make_recommendation(avg_duration, success_rate)
        }

    def _make_recommendation(self, avg_duration: float,
                             success_rate: float) -> str:
        if success_rate < 0.5:
            return "需要降低负载或修复任务处理器"
        if avg_duration > 5.0:
            return "任务处理过慢，建议优化或拆分"
        if success_rate > 0.95 and avg_duration < 0.5:
            return "系统运行良好，可适当增加负载"
        return "系统运行正常"


# ============================================================
# 四、优雅停止器
# ============================================================
class GracefulStopper:
    """优雅停止器

    第一性原理：存续公理 - 系统停止时不能丢数据
    """
    def __init__(self):
        self._stop_requested = False
        self._stop_reason = ""
        self._registered_handlers: List[callable] = []

    def request_stop(self, reason: str = "user_request") -> None:
        """请求停止"""
        self._stop_requested = True
        self._stop_reason = reason

    def is_stop_requested(self) -> bool:
        return self._stop_requested

    def get_stop_reason(self) -> str:
        return self._stop_reason

    def register_cleanup(self, handler: callable) -> None:
        """注册清理回调"""
        self._registered_handlers.append(handler)

    def run_cleanup(self) -> None:
        """执行清理回调"""
        for handler in self._registered_handlers:
            try:
                handler()
            except Exception:
                pass


# ============================================================
# 五、主循环
# ============================================================
class MainLoop:
    """主循环 - 系统的心脏

    第一性原理：
    - 自驱公理：自动产生任务
    - 存续公理：永不崩溃
    - 适应性：根据状态调整节奏
    """
    def __init__(self, kg: PersistentKnowledgeGraph,
                 queue: Optional[TaskQueue] = None,
                 scheduler: Optional[TaskScheduler] = None):
        self.kg = kg
        self.queue = queue or TaskQueue(max_size=50)
        self.scheduler = scheduler or TaskScheduler(self.queue)
        self.interval = AdaptiveInterval(default=1.0)
        self.generator = TaskGenerator(kg)
        self.reflection = ReflectionEngine()
        self.stopper = GracefulStopper()
        self.cycle_count = 0
        self._start_time = None
        self._save_interval = 10  # 每10个循环保存一次
        self._last_save_cycle = 0
        self._register_default_handlers()

    def _register_default_handlers(self):
        """注册默认任务处理器"""
        self.scheduler.register_handler("explore", self._handle_explore)
        self.scheduler.register_handler("connect_ideas", self._handle_connect)
        self.scheduler.register_handler("prune_weak", self._handle_prune)
        self.scheduler.register_handler("reflect", self._handle_reflect)
        self.scheduler.register_handler("discover_relation",
                                        self._handle_discover)
        self.scheduler.register_handler("consolidate", self._handle_consolidate)

    def _handle_explore(self) -> str:
        """探索：添加新节点"""
        node_id = f"n_{self.cycle_count}_{int(time.time()*1000) % 10000}"
        content = f"知识发现 @ cycle {self.cycle_count}"
        self.kg.add_node(Node(content=content, node_id=node_id,
                              label="discovery"))
        return f"added {node_id}"

    def _handle_connect(self) -> str:
        """连接：在随机两节点间建立关系"""
        nodes = [n for n in self.kg.nodes.values() if n.is_active()]
        if len(nodes) < 2:
            return "skip: not enough nodes"
        a, b = random.sample(nodes, 2)
        edge = Edge(
            from_id=a.node_id, to_id=b.node_id,
            relation=random.choice(["related_to", "supports", "implies"]),
            weight=random.uniform(0.5, 0.9),
            edge_id=f"e_{self.cycle_count}_{int(time.time()*1000) % 10000}"
        )
        self.kg.add_edge(edge)
        return f"connected {a.node_id}->{b.node_id}"

    def _handle_prune(self) -> str:
        """清理：删除弱关系"""
        count = self.kg.prune_weak_edges(threshold=0.1)
        return f"pruned {count} weak edges"

    def _handle_reflect(self) -> str:
        """反思：评估并调整"""
        stats = self.kg.get_statistics()
        return f"reflected: {stats['active_nodes']}n/{stats['active_edges']}e"

    def _handle_discover(self) -> str:
        """发现关系：通过现有节点组合推理"""
        nodes = [n for n in self.kg.nodes.values() if n.is_active()]
        if len(nodes) < 3:
            return "skip: not enough nodes"
        a, b, c = random.sample(nodes, 3)
        # 创建 a->c 推理边
        edge = Edge(
            from_id=a.node_id, to_id=c.node_id,
            relation="inferred",
            weight=0.3,
            edge_id=f"inf_{self.cycle_count}_{int(time.time()*1000) % 10000}"
        )
        self.kg.add_edge(edge)
        return f"inferred {a.node_id}->{c.node_id}"

    def _handle_consolidate(self) -> str:
        """整合：强化高频访问节点"""
        active = [n for n in self.kg.nodes.values() if n.is_active()]
        if not active:
            return "skip"
        # 强化最老的前3个节点
        active.sort(key=lambda n: n.created_at)
        for n in active[:3]:
            n.weight = min(1.0, n.weight + 0.01)
        return f"reinforced {min(3, len(active))} nodes"

    def run_cycle(self) -> Dict[str, Any]:
        """运行一个循环"""
        cycle_start = time.time()
        self.cycle_count += 1

        # 1. 自动生成任务
        # 当队列空或不足时立即生成
        if self.queue.size() < 3:
            new_task = self.generator.maybe_generate(force=True)
            if new_task:
                self.scheduler.submit(new_task)

        # 2. 执行一个任务
        success_before = self.scheduler._stats["succeeded"]
        failed_before = self.scheduler._stats["failed"]
        self.scheduler.run_one()
        success_delta = self.scheduler._stats["succeeded"] - success_before
        failed_delta = self.scheduler._stats["failed"] - failed_before

        # 3. 自适应调整间隔
        duration = time.time() - cycle_start
        self.interval.adjust(self.queue.size(), duration)

        # 4. 定期保存
        if self.cycle_count - self._last_save_cycle >= self._save_interval:
            self.kg.save()
            self._last_save_cycle = self.cycle_count

        # 5. 反思
        self.reflection.record_cycle(
            self.cycle_count, self.queue.size(),
            duration, success_delta, failed_delta
        )

        return {
            "cycle": self.cycle_count,
            "queue_size": self.queue.size(),
            "duration": duration,
            "next_interval": self.interval.get_current(),
            "success_delta": success_delta,
            "failed_delta": failed_delta,
        }

    def run(self, max_cycles: Optional[int] = None) -> None:
        """主循环入口

        Args:
            max_cycles: 最大循环次数，None表示无限
        """
        self._start_time = time.time()
        self.kg.load()  # 启动时尝试加载

        try:
            while not self.stopper.is_stop_requested():
                if max_cycles and self.cycle_count >= max_cycles:
                    break
                try:
                    self.run_cycle()
                except Exception:
                    # 主循环本身的异常也不应导致退出
                    pass
                time.sleep(self.interval.get_current())
        except KeyboardInterrupt:
            self.stopper.request_stop("keyboard_interrupt")
        finally:
            self._shutdown()

    def _shutdown(self) -> None:
        """关闭时的清理"""
        self.kg.save()  # 最后保存一次
        self.stopper.run_cleanup()


# ============================================================
# 六、单元测试
# ============================================================
class TestAdaptiveInterval(unittest.TestCase):
    """自适应间隔测试"""
    def test_initial(self):
        ai = AdaptiveInterval(default=1.0)
        self.assertEqual(ai.get_current(), 1.0)

    def test_accelerate_on_load(self):
        ai = AdaptiveInterval(default=1.0)
        for _ in range(3):
            ai.adjust(queue_size=10, last_duration=0.01)
        self.assertLess(ai.get_current(), 1.0)

    def test_decelerate_on_idle(self):
        ai = AdaptiveInterval(default=1.0)
        for _ in range(10):
            ai.adjust(queue_size=0, last_duration=0.01)
        self.assertGreater(ai.get_current(), 1.0)

    def test_resource_pressure(self):
        ai = AdaptiveInterval(default=1.0)
        for _ in range(3):
            ai.adjust(queue_size=0, last_duration=0.01, resource_pressure=0.9)
        self.assertGreater(ai.get_current(), 1.0)


class TestMainLoop(unittest.TestCase):
    """主循环测试"""
    def test_cycle_runs(self):
        import tempfile
        import os
        with tempfile.TemporaryDirectory() as tmpdir:
            kg = PersistentKnowledgeGraph(
                os.path.join(tmpdir, "kg.json"))
            loop = MainLoop(kg)
            for _ in range(20):
                result = loop.run_cycle()
                self.assertIn("cycle", result)
                self.assertGreaterEqual(result["queue_size"], 0)
            stats = loop.kg.get_statistics()
            self.assertGreater(stats["total_nodes"], 0)

    def test_graceful_stop(self):
        import tempfile
        import os
        with tempfile.TemporaryDirectory() as tmpdir:
            kg = PersistentKnowledgeGraph(
                os.path.join(tmpdir, "kg.json"))
            loop = MainLoop(kg)
            for _ in range(5):
                loop.run_cycle()
            loop.stopper.request_stop("test")
            self.assertTrue(loop.stopper.is_stop_requested())


# ============================================================
# 七、阶段106演示
# ============================================================
def run_phase_106():
    """运行阶段106"""
    print("=" * 70)
    print("阶段106：自循环主循环")
    print("=" * 70)
    print()
    print("【执行单元测试】")
    print("-" * 70)
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    suite.addTests(loader.loadTestsFromTestCase(TestAdaptiveInterval))
    suite.addTests(loader.loadTestsFromTestCase(TestMainLoop))
    runner = unittest.TextTestRunner(verbosity=1)
    result = runner.run(suite)
    print()
    print("-" * 70)
    print("【主循环运行演示 - 50个循环】")
    print("-" * 70)
    import tempfile
    import os
    with tempfile.TemporaryDirectory() as tmpdir:
        kg = PersistentKnowledgeGraph(os.path.join(tmpdir, "demo_kg.json"))
        loop = MainLoop(kg)
        snapshots = []
        for i in range(50):
            r = loop.run_cycle()
            if (i+1) % 10 == 0:
                snapshots.append(r)
                stats = loop.kg.get_statistics()
                print(f"  第{i+1:3d}循环: 队列={r['queue_size']:2d}, "
                      f"耗时={r['duration']*1000:5.1f}ms, "
                      f"间隔={r['next_interval']:.2f}s, "
                      f"图谱={stats['active_nodes']}n/{stats['active_edges']}e")
        # 触发反思
        reflection = loop.reflection.maybe_reflect()
        if reflection:
            print()
            print("  🪞 反思结果:")
            print(f"     平均耗时: {reflection['avg_duration']*1000:.1f}ms")
            print(f"     成功率:   {reflection['success_rate']*100:.1f}%")
            print(f"     建议:     {reflection['recommendation']}")
    print()
    print("=" * 70)
    if result.wasSuccessful():
        print("✅ 阶段106完成：自循环主循环已实现，所有测试通过！")
    else:
        print("❌ 阶段106失败")
    print("=" * 70)
    print()
    print("【下阶段预告】阶段107：异常隔离与自愈")
    print("  - 全局异常捕获")
    print("  - 任务级隔离")
    print("  - 熔断器模式")
    print("  - 自愈策略")
    print()
    return result.wasSuccessful()


if __name__ == "__main__":
    run_phase_106()

#!/usr/bin/env python3
"""
阶段105：任务队列与调度器

第一性原理：
  - 自驱公理要求系统能自主产生任务
  - 任务必须有优先级，否则会饿死重要任务
  - 队列必须有背压，否则会内存爆炸

本阶段产出：
  1. Task类：任务定义与生命周期
  2. TaskQueue：优先级队列+背压
  3. TaskScheduler：状态机+调度策略
  4. 单元测试

遵循原则：图难于其易，为大于其细
"""
import time
import uuid
import unittest
import threading
from typing import Dict, List, Any, Optional, Callable
from enum import Enum
from dataclasses import dataclass, field
from collections import deque
import heapq


# ============================================================
# 一、任务状态机
# ============================================================
class TaskStatus(Enum):
    """任务生命周期状态"""
    PENDING = "pending"        # 待执行
    READY = "ready"            # 就绪
    RUNNING = "running"        # 执行中
    PAUSED = "paused"          # 暂停
    COMPLETED = "completed"    # 完成
    FAILED = "failed"          # 失败
    CANCELLED = "cancelled"    # 取消
    TIMEOUT = "timeout"        # 超时


class TaskPriority(Enum):
    """任务优先级（数字越小越优先）"""
    CRITICAL = 0   # 紧急（如：异常处理）
    HIGH = 2       # 高（如：用户请求）
    NORMAL = 5     # 普通（如：默认任务）
    LOW = 8        # 低（如：清理任务）
    BACKGROUND = 10  # 后台（如：统计）


# ============================================================
# 二、任务类
# ============================================================
@dataclass
class Task:
    """任务定义"""
    name: str
    handler: Optional[Callable] = None
    args: tuple = field(default_factory=tuple)
    kwargs: Dict[str, Any] = field(default_factory=dict)
    task_id: str = field(default_factory=lambda: f"t_{uuid.uuid4().hex[:8]}")
    priority: int = TaskPriority.NORMAL.value
    status: str = TaskStatus.PENDING.value
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    finished_at: Optional[float] = None
    timeout_sec: float = 30.0
    retry_count: int = 0
    max_retries: int = 3
    error_message: str = ""
    result: Any = None
    tags: List[str] = field(default_factory=list)

    def __lt__(self, other):
        """支持heapq比较"""
        if self.priority != other.priority:
            return self.priority < other.priority
        return self.created_at < other.created_at

    def duration_sec(self) -> Optional[float]:
        if self.started_at and self.finished_at:
            return self.finished_at - self.started_at
        return None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "name": self.name,
            "priority": self.priority,
            "status": self.status,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "retry_count": self.retry_count,
            "error_message": self.error_message,
            "tags": self.tags,
            "duration_sec": self.duration_sec(),
        }


# ============================================================
# 三、任务队列
# ============================================================
class TaskQueue:
    """任务队列

    特性：
    - 优先级排序（数字越小越优先）
    - 背压机制（队列满时拒绝新任务）
    - 线程安全
    - 状态过滤
    """
    OVERFLOW_POLICIES = ["reject", "drop_oldest", "drop_lowest"]

    def __init__(self, max_size: int = 100,
                 overflow_policy: str = "reject"):
        self.max_size = max_size
        self.overflow_policy = overflow_policy
        self._heap: List[Task] = []
        self._lock = threading.Lock()
        self._task_map: Dict[str, Task] = {}
        self._stats = {
            "enqueued": 0,
            "dequeued": 0,
            "rejected": 0,
            "dropped": 0,
        }

    def enqueue(self, task: Task) -> bool:
        """入队

        Returns: True if success, False if rejected/dropped
        """
        with self._lock:
            if len(self._heap) >= self.max_size:
                return self._handle_overflow(task)
            heapq.heappush(self._heap, task)
            self._task_map[task.task_id] = task
            self._stats["enqueued"] += 1
            return True

    def _handle_overflow(self, task: Task) -> bool:
        """处理队列溢出"""
        if self.overflow_policy == "reject":
            self._stats["rejected"] += 1
            return False
        elif self.overflow_policy == "drop_oldest":
            # 弹出堆顶（最旧的，因为同优先级按时间排序）
            if self._heap:
                old = heapq.heappop(self._heap)
                self._task_map.pop(old.task_id, None)
                self._stats["dropped"] += 1
            heapq.heappush(self._heap, task)
            self._task_map[task.task_id] = task
            self._stats["enqueued"] += 1
            return True
        elif self.overflow_policy == "drop_lowest":
            # 弹出堆底（最低优先级）
            if self._heap:
                # 找最低优先级
                idx = max(range(len(self._heap)),
                          key=lambda i: self._heap[i].priority)
                low = self._heap.pop(idx)
                self._task_map.pop(low.task_id, None)
                heapq.heapify(self._heap)
                self._stats["dropped"] += 1
            heapq.heappush(self._heap, task)
            self._task_map[task.task_id] = task
            self._stats["enqueued"] += 1
            return True
        return False

    def dequeue(self) -> Optional[Task]:
        """出队（按优先级）"""
        with self._lock:
            while self._heap:
                task = heapq.heappop(self._heap)
                if task.status in (TaskStatus.PENDING.value,
                                   TaskStatus.READY.value):
                    self._stats["dequeued"] += 1
                    return task
                # 跳过已完成/失败的
                self._task_map.pop(task.task_id, None)
            return None

    def peek(self) -> Optional[Task]:
        """查看队首但不出队"""
        with self._lock:
            return self._heap[0] if self._heap else None

    def size(self) -> int:
        with self._lock:
            return len(self._heap)

    def get_by_id(self, task_id: str) -> Optional[Task]:
        return self._task_map.get(task_id)

    def get_stats(self) -> Dict[str, int]:
        with self._lock:
            return dict(self._stats)

    def clear(self) -> int:
        with self._lock:
            count = len(self._heap)
            self._heap.clear()
            self._task_map.clear()
            return count


# ============================================================
# 四、任务调度器
# ============================================================
class TaskScheduler:
    """任务调度器

    负责：
    - 任务状态机推进
    - 任务执行（含超时）
    - 重试逻辑
    - 状态统计
    """
    def __init__(self, queue: TaskQueue):
        self.queue = queue
        self.completed: List[Task] = []
        self.failed: List[Task] = []
        self._handlers: Dict[str, Callable] = {}
        self._stats = {
            "executed": 0,
            "succeeded": 0,
            "failed": 0,
            "retries": 0,
            "timeouts": 0,
        }

    def register_handler(self, name: str, handler: Callable) -> None:
        """注册任务处理器"""
        self._handlers[name] = handler

    def submit(self, task: Task) -> bool:
        """提交任务到队列"""
        return self.queue.enqueue(task)

    def run_one(self, timeout: bool = True) -> Optional[Task]:
        """执行一个任务

        内部循环处理重试，确保一次调用后任务要么完成要么真正失败
        Returns: 执行完的任务（成功或最终失败）
        """
        task = self.queue.dequeue()
        if not task:
            return None

        # 内部循环处理重试
        while task.retry_count <= task.max_retries:
            task.status = TaskStatus.RUNNING.value
            task.started_at = time.time()
            self._stats["executed"] += 1

            handler = task.handler or self._handlers.get(task.name)
            if handler is None:
                task.status = TaskStatus.FAILED.value
                task.error_message = f"No handler for {task.name}"
                task.finished_at = time.time()
                self.failed.append(task)
                self._stats["failed"] += 1
                return task

            try:
                task.result = handler(*task.args, **task.kwargs)
                task.status = TaskStatus.COMPLETED.value
                task.finished_at = time.time()
                self.completed.append(task)
                self._stats["succeeded"] += 1
                return task
            except Exception as e:
                task.error_message = str(e)
                task.finished_at = time.time()
                self._stats["failed"] += 1
                # 重试逻辑
                if task.retry_count < task.max_retries:
                    task.retry_count += 1
                    self._stats["retries"] += 1
                    task.status = TaskStatus.PENDING.value
                    # 继续循环，再次执行
                else:
                    task.status = TaskStatus.FAILED.value
                    self.failed.append(task)
                    return task
        return task

    def run_batch(self, max_tasks: int = 10) -> int:
        """批量执行任务"""
        count = 0
        for _ in range(max_tasks):
            task = self.run_one()
            if task is None:
                break
            count += 1
        return count

    def get_stats(self) -> Dict[str, int]:
        return dict(self._stats)

    def get_recent_completed(self, n: int = 10) -> List[Task]:
        return self.completed[-n:]


# ============================================================
# 五、单元测试
# ============================================================
class TestTask(unittest.TestCase):
    """任务类测试"""
    def test_creation(self):
        t = Task(name="test")
        self.assertEqual(t.name, "test")
        self.assertEqual(t.status, TaskStatus.PENDING.value)
        self.assertGreater(t.created_at, 0)

    def test_priority_ordering(self):
        t1 = Task(name="a", priority=TaskPriority.HIGH.value)
        t2 = Task(name="b", priority=TaskPriority.LOW.value)
        self.assertTrue(t1 < t2)


class TestTaskQueue(unittest.TestCase):
    """任务队列测试"""
    def test_enqueue_dequeue(self):
        q = TaskQueue(max_size=10)
        t = Task(name="x")
        self.assertTrue(q.enqueue(t))
        got = q.dequeue()
        self.assertEqual(got.task_id, t.task_id)

    def test_priority_ordering(self):
        q = TaskQueue(max_size=10)
        low = Task(name="low", priority=9)
        high = Task(name="high", priority=1)
        mid = Task(name="mid", priority=5)
        q.enqueue(low)
        q.enqueue(high)
        q.enqueue(mid)
        # 应该按优先级顺序出队
        self.assertEqual(q.dequeue().name, "high")
        self.assertEqual(q.dequeue().name, "mid")
        self.assertEqual(q.dequeue().name, "low")

    def test_backpressure_reject(self):
        q = TaskQueue(max_size=2, overflow_policy="reject")
        self.assertTrue(q.enqueue(Task(name="a")))
        self.assertTrue(q.enqueue(Task(name="b")))
        self.assertFalse(q.enqueue(Task(name="c")))
        self.assertEqual(q.get_stats()["rejected"], 1)

    def test_backpressure_drop_oldest(self):
        q = TaskQueue(max_size=2, overflow_policy="drop_oldest")
        q.enqueue(Task(name="a", priority=5))
        q.enqueue(Task(name="b", priority=5))
        # 第三个任务加入时应丢弃最旧的
        q.enqueue(Task(name="c", priority=5))
        self.assertEqual(q.size(), 2)

    def test_backpressure_drop_lowest(self):
        q = TaskQueue(max_size=2, overflow_policy="drop_lowest")
        q.enqueue(Task(name="a", priority=5))
        q.enqueue(Task(name="b", priority=2))  # 较低优先级
        # 新任务优先级1，最低优先级b应被丢弃
        q.enqueue(Task(name="c", priority=1))
        self.assertEqual(q.size(), 2)
        # b应该被丢弃
        first = q.dequeue()
        self.assertNotEqual(first.name, "b")

    def test_thread_safety(self):
        q = TaskQueue(max_size=1000)
        def producer():
            for i in range(100):
                q.enqueue(Task(name=f"t{i}"))
        threads = [threading.Thread(target=producer) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(q.size(), 500)


class TestTaskScheduler(unittest.TestCase):
    """任务调度器测试"""
    def test_simple_execution(self):
        queue = TaskQueue()
        scheduler = TaskScheduler(queue)
        scheduler.register_handler("add", lambda a, b: a + b)
        scheduler.submit(Task(name="add", args=(2, 3)))
        task = scheduler.run_one()
        self.assertEqual(task.status, TaskStatus.COMPLETED.value)
        self.assertEqual(task.result, 5)

    def test_no_handler(self):
        queue = TaskQueue()
        scheduler = TaskScheduler(queue)
        scheduler.submit(Task(name="unknown"))
        task = scheduler.run_one()
        self.assertEqual(task.status, TaskStatus.FAILED.value)

    def test_retry_logic(self):
        queue = TaskQueue()
        scheduler = TaskScheduler(queue)
        call_count = [0]
        def flaky():
            call_count[0] += 1
            if call_count[0] < 3:
                raise ValueError("transient")
            return "ok"
        task = Task(name="flaky", max_retries=5)
        task.handler = flaky
        queue.enqueue(task)
        result = scheduler.run_one()
        self.assertEqual(result.status, TaskStatus.COMPLETED.value)
        self.assertEqual(call_count[0], 3)
        self.assertEqual(scheduler.get_stats()["retries"], 2)

    def test_batch_run(self):
        queue = TaskQueue()
        scheduler = TaskScheduler(queue)
        scheduler.register_handler("noop", lambda: None)
        for i in range(5):
            scheduler.submit(Task(name="noop"))
        count = scheduler.run_batch(max_tasks=10)
        self.assertEqual(count, 5)
        self.assertEqual(scheduler.get_stats()["succeeded"], 5)


# ============================================================
# 六、阶段105演示
# ============================================================
def run_phase_105():
    """运行阶段105"""
    print("=" * 70)
    print("阶段105：任务队列与调度器")
    print("=" * 70)
    print()
    print("【执行单元测试】")
    print("-" * 70)
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    suite.addTests(loader.loadTestsFromTestCase(TestTask))
    suite.addTests(loader.loadTestsFromTestCase(TestTaskQueue))
    suite.addTests(loader.loadTestsFromTestCase(TestTaskScheduler))
    runner = unittest.TextTestRunner(verbosity=1)
    result = runner.run(suite)
    print()
    print("-" * 70)
    print("【任务调度演示】")
    print("-" * 70)
    queue = TaskQueue(max_size=10)
    scheduler = TaskScheduler(queue)

    # 注册处理器
    scheduler.register_handler("explore", lambda: "探索知识")
    scheduler.register_handler("connect", lambda: "建立连接")
    scheduler.register_handler("prune", lambda: "清理知识")
    scheduler.register_handler("reflect", lambda: "反思学习")
    scheduler.register_handler("flaky",
                               lambda: (_ for _ in ()).throw(RuntimeError("模拟异常")))

    # 提交不同优先级的任务
    scheduler.submit(Task(name="explore", priority=TaskPriority.NORMAL.value))
    scheduler.submit(Task(name="critical_task", priority=TaskPriority.CRITICAL.value))
    scheduler.submit(Task(name="background", priority=TaskPriority.BACKGROUND.value))
    scheduler.submit(Task(name="high", priority=TaskPriority.HIGH.value))
    scheduler.submit(Task(name="flaky", max_retries=2))

    print(f"  📊 队列大小: {queue.size()}")
    print(f"  📊 队首任务: {queue.peek().name}")
    print()
    print("  🔄 顺序执行:")
    for i in range(6):
        task = scheduler.run_one()
        if task:
            print(f"     [{i+1}] {task.name} -> {task.status}"
                  f" (重试{task.retry_count}次)")
    print()
    stats = scheduler.get_stats()
    print(f"  📊 调度器统计: {stats}")
    print(f"  📊 队列统计:   {queue.get_stats()}")
    print()
    print("=" * 70)
    if result.wasSuccessful():
        print("✅ 阶段105完成：任务队列与调度器已实现，所有测试通过！")
    else:
        print("❌ 阶段105失败")
    print("=" * 70)
    print()
    print("【下阶段预告】阶段106：自循环主循环")
    print("  - 任务自动生成")
    print("  - 异常隔离")
    print("  - 自适应循环间隔")
    print("  - 优雅停止")
    print()
    return result.wasSuccessful()


if __name__ == "__main__":
    run_phase_105()

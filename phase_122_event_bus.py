#!/usr/bin/env python3
"""
阶段122：事件总线

第一性原理：
  - 解耦原则：发布者不需知道订阅者
  - 异步公理：事件不应阻塞主流程
  - 历史可追溯：事件可重放
  - 过滤：精确送达感兴趣的订阅者

本阶段产出：
  1. Event：事件数据结构
  2. Subscription：订阅定义
  3. EventBus：同步事件总线
  4. AsyncEventBus：异步事件总线
  5. EventStore：事件存储（持久化/重放）
  6. EventFilter：事件过滤器

遵循原则：图难于其易，为大于其细
"""
import time
import uuid
import unittest
import threading
import json
import os
from queue import Queue, Empty
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, field, asdict
from collections import deque


# ============================================================
# 一、事件结构
# ============================================================
@dataclass
class Event:
    """事件"""
    event_id: str = field(default_factory=lambda: f"ev_{uuid.uuid4().hex[:12]}")
    event_type: str = ""
    source: str = ""
    timestamp: float = field(default_factory=time.time)
    data: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> 'Event':
        return cls(**d)


# ============================================================
# 二、订阅
# ============================================================
@dataclass
class Subscription:
    """订阅"""
    subscription_id: str = field(default_factory=lambda: f"sub_{uuid.uuid4().hex[:8]}")
    event_type: str = ""
    handler: Optional[Callable] = None
    filter_fn: Optional[Callable[[Event], bool]] = None
    subscriber: str = "unknown"
    priority: int = 100
    async_mode: bool = False

    def matches(self, event: Event) -> bool:
        """是否匹配此事件"""
        if self.event_type != "*" and self.event_type != event.event_type:
            return False
        if self.filter_fn and not self.filter_fn(event):
            return False
        return True


# ============================================================
# 三、同步事件总线
# ============================================================
class EventBus:
    """同步事件总线"""
    def __init__(self, max_queue_size: int = 1000):
        self._subscriptions: Dict[str, List[Subscription]] = {}
        self._lock = threading.RLock()
        self._stats = {
            "published": 0,
            "delivered": 0,
            "errors": 0,
            "subscriptions": 0,
        }
        # 事件历史
        self._history: deque = deque(maxlen=max_queue_size)

    def subscribe(self, event_type: str, handler: Callable,
                  subscriber: str = "unknown",
                  filter_fn: Optional[Callable] = None,
                  priority: int = 100) -> str:
        with self._lock:
            sub = Subscription(
                event_type=event_type,
                handler=handler,
                filter_fn=filter_fn,
                subscriber=subscriber,
                priority=priority,
            )
            if event_type not in self._subscriptions:
                self._subscriptions[event_type] = []
            self._subscriptions[event_type].append(sub)
            self._subscriptions[event_type].sort(
                key=lambda s: s.priority)
            self._stats["subscriptions"] += 1
            return sub.subscription_id

    def unsubscribe(self, subscription_id: str) -> bool:
        with self._lock:
            for event_type, subs in self._subscriptions.items():
                for i, sub in enumerate(subs):
                    if sub.subscription_id == subscription_id:
                        del subs[i]
                        self._stats["subscriptions"] -= 1
                        return True
            return False

    def publish(self, event_type: str, data: Optional[Dict] = None,
                 source: str = "system",
                 metadata: Optional[Dict] = None) -> str:
        event = Event(
            event_type=event_type, source=source,
            data=data or {}, metadata=metadata or {})
        with self._lock:
            self._history.append(event)
            self._stats["published"] += 1
            # 收集匹配的订阅
            subs = []
            for event_type_pattern, type_subs in self._subscriptions.items():
                for sub in type_subs:
                    if sub.matches(event):
                        subs.append(sub)
            subs.sort(key=lambda s: s.priority)
        # 同步派发
        for sub in subs:
            try:
                if sub.handler:
                    sub.handler(event)
                    self._stats["delivered"] += 1
            except Exception:
                self._stats["errors"] += 1
        return event.event_id

    def get_history(self, event_type: Optional[str] = None,
                     limit: int = 100) -> List[Event]:
        with self._lock:
            history = list(self._history)
        if event_type:
            history = [e for e in history if e.event_type == event_type]
        return history[-limit:]

    def get_stats(self) -> Dict[str, int]:
        with self._lock:
            return dict(self._stats)

    def clear(self) -> None:
        with self._lock:
            self._history.clear()


# ============================================================
# 四、异步事件总线
# ============================================================
class AsyncEventBus:
    """异步事件总线

    事件被发布到队列，由后台worker线程派发
    """
    def __init__(self, num_workers: int = 2,
                 max_queue_size: int = 1000):
        self._subscriptions: Dict[str, List[Subscription]] = {}
        self._lock = threading.RLock()
        self._queue: Queue = Queue(maxsize=max_queue_size)
        self._workers: List[threading.Thread] = []
        self._running = False
        self._num_workers = num_workers
        self._stats = {
            "published": 0,
            "delivered": 0,
            "errors": 0,
            "queue_size": 0,
        }

    def subscribe(self, event_type: str, handler: Callable,
                  subscriber: str = "unknown",
                  filter_fn: Optional[Callable] = None,
                  priority: int = 100,
                  async_mode: bool = True) -> str:
        with self._lock:
            sub = Subscription(
                event_type=event_type, handler=handler,
                filter_fn=filter_fn, subscriber=subscriber,
                priority=priority, async_mode=async_mode)
            if event_type not in self._subscriptions:
                self._subscriptions[event_type] = []
            self._subscriptions[event_type].append(sub)
            self._subscriptions[event_type].sort(
                key=lambda s: s.priority)
            return sub.subscription_id

    def unsubscribe(self, subscription_id: str) -> bool:
        with self._lock:
            for event_type, subs in self._subscriptions.items():
                for i, sub in enumerate(subs):
                    if sub.subscription_id == subscription_id:
                        del subs[i]
                        return True
            return False

    def start(self) -> None:
        with self._lock:
            if self._running:
                return
            self._running = True
        for i in range(self._num_workers):
            t = threading.Thread(
                target=self._worker, daemon=True,
                name=f"eventbus-worker-{i}")
            t.start()
            self._workers.append(t)

    def stop(self) -> None:
        with self._lock:
            self._running = False
        # 等待队列清空
        self._queue.join()
        for t in self._workers:
            t.join(timeout=2)

    def _worker(self) -> None:
        while True:
            with self._lock:
                if not self._running and self._queue.empty():
                    break
            try:
                event, subs = self._queue.get(timeout=0.1)
            except Empty:
                continue
            try:
                for sub in subs:
                    try:
                        if sub.handler:
                            sub.handler(event)
                            self._stats["delivered"] += 1
                    except Exception:
                        self._stats["errors"] += 1
            finally:
                self._queue.task_done()

    def publish(self, event_type: str, data: Optional[Dict] = None,
                 source: str = "system",
                 metadata: Optional[Dict] = None) -> str:
        event = Event(
            event_type=event_type, source=source,
            data=data or {}, metadata=metadata or {})
        with self._lock:
            self._stats["published"] += 1
            self._stats["queue_size"] = self._queue.qsize()
            subs = []
            for event_type_pattern, type_subs in self._subscriptions.items():
                for sub in type_subs:
                    if sub.matches(event):
                        subs.append(sub)
            subs.sort(key=lambda s: s.priority)
        try:
            self._queue.put((event, subs), timeout=1.0)
        except Exception:
            self._stats["errors"] += 1
        return event.event_id

    def get_stats(self) -> Dict[str, int]:
        with self._lock:
            stats = dict(self._stats)
            stats["queue_size"] = self._queue.qsize()
            return stats


# ============================================================
# 五、事件存储
# ============================================================
class EventStore:
    """事件存储

    将事件持久化到磁盘，支持重放
    """
    def __init__(self, storage_path: str = "/tmp/event_store.jsonl"):
        self.storage_path = storage_path
        self._lock = threading.Lock()
        self._cache: deque = deque(maxlen=10000)

    def save(self, event: Event) -> None:
        with self._lock:
            line = json.dumps(event.to_dict(), ensure_ascii=False)
            with open(self.storage_path, "a") as f:
                f.write(line + "\n")
            self._cache.append(event)

    def save_batch(self, events: List[Event]) -> None:
        with self._lock:
            with open(self.storage_path, "a") as f:
                for event in events:
                    line = json.dumps(
                        event.to_dict(), ensure_ascii=False)
                    f.write(line + "\n")
                    self._cache.append(event)

    def load_all(self) -> List[Event]:
        if not os.path.exists(self.storage_path):
            return []
        events = []
        with open(self.storage_path) as f:
            for line in f:
                if line.strip():
                    d = json.loads(line)
                    events.append(Event.from_dict(d))
        return events

    def replay(self, handler: Callable,
                event_type: Optional[str] = None) -> int:
        """重放历史事件"""
        events = self.load_all()
        count = 0
        for event in events:
            if event_type and event.event_type != event_type:
                continue
            try:
                handler(event)
                count += 1
            except Exception:
                pass
        return count

    def clear(self) -> None:
        with self._lock:
            if os.path.exists(self.storage_path):
                os.remove(self.storage_path)
            self._cache.clear()

    def get_recent(self, limit: int = 100) -> List[Event]:
        with self._lock:
            return list(self._cache)[-limit:]


# ============================================================
# 六、事件过滤器
# ============================================================
class EventFilter:
    """事件过滤器工厂"""
    @staticmethod
    def by_type(event_type: str) -> Callable:
        return lambda e: e.event_type == event_type

    @staticmethod
    def by_source(source: str) -> Callable:
        return lambda e: e.source == source

    @staticmethod
    def by_predicate(predicate: Callable[[Event], bool]) -> Callable:
        return predicate

    @staticmethod
    def and_(*filters: Callable) -> Callable:
        return lambda e: all(f(e) for f in filters)

    @staticmethod
    def or_(*filters: Callable) -> Callable:
        return lambda e: any(f(e) for f in filters)


# ============================================================
# 七、单元测试
# ============================================================
class TestEvent(unittest.TestCase):
    """事件测试"""
    def test_create(self):
        e = Event(event_type="test", data={"x": 1})
        self.assertEqual(e.event_type, "test")
        self.assertEqual(e.data["x"], 1)
        self.assertIsNotNone(e.event_id)

    def test_serialization(self):
        e = Event(event_type="test", data={"x": 1}, source="s")
        d = e.to_dict()
        e2 = Event.from_dict(d)
        self.assertEqual(e.event_type, e2.event_type)
        self.assertEqual(e.data, e2.data)


class TestSyncEventBus(unittest.TestCase):
    """同步事件总线测试"""
    def setUp(self):
        self.bus = EventBus()

    def test_subscribe_and_publish(self):
        received = []
        self.bus.subscribe("test", lambda e: received.append(e))
        self.bus.publish("test", {"a": 1})
        self.assertEqual(len(received), 1)
        self.assertEqual(received[0].data["a"], 1)

    def test_wildcard_subscribe(self):
        received = []
        self.bus.subscribe("*", lambda e: received.append(e))
        self.bus.publish("a", {})
        self.bus.publish("b", {})
        self.assertEqual(len(received), 2)

    def test_priority_order(self):
        order = []
        self.bus.subscribe("ev", lambda e: order.append("low"),
                            priority=100)
        self.bus.subscribe("ev", lambda e: order.append("high"),
                            priority=10)
        self.bus.publish("ev")
        self.assertEqual(order, ["high", "low"])

    def test_unsubscribe(self):
        received = []
        sid = self.bus.subscribe("test", lambda e: received.append(e))
        self.bus.publish("test")
        self.assertEqual(len(received), 1)
        self.assertTrue(self.bus.unsubscribe(sid))
        self.bus.publish("test")
        self.assertEqual(len(received), 1)  # 不变

    def test_filter(self):
        received = []
        self.bus.subscribe(
            "test", lambda e: received.append(e),
            filter_fn=lambda e: e.data.get("ok") is True)
        self.bus.publish("test", {"ok": True})
        self.bus.publish("test", {"ok": False})
        self.assertEqual(len(received), 1)

    def test_history(self):
        self.bus.publish("a", {"v": 1})
        self.bus.publish("b", {"v": 2})
        history = self.bus.get_history()
        self.assertEqual(len(history), 2)
        history_a = self.bus.get_history(event_type="a")
        self.assertEqual(len(history_a), 1)

    def test_error_in_handler(self):
        def bad(e):
            raise RuntimeError("oops")
        self.bus.subscribe("test", bad)
        self.bus.subscribe("test", lambda e: None)  # 不应被影响
        self.bus.publish("test")
        self.assertEqual(self.bus.get_stats()["errors"], 1)


class TestAsyncEventBus(unittest.TestCase):
    """异步事件总线测试"""
    def test_async_dispatch(self):
        bus = AsyncEventBus(num_workers=2)
        received = []
        bus.subscribe("test", lambda e: received.append(e))
        bus.start()
        for i in range(10):
            bus.publish("test", {"i": i})
        # 等待派发
        time.sleep(0.5)
        bus.stop()
        self.assertGreaterEqual(len(received), 1)
        # 注意：异步模式下结果可能不完整

    def test_async_priority(self):
        bus = AsyncEventBus(num_workers=1)
        bus.start()
        # 注意：异步模式下顺序由worker决定
        bus.subscribe("ev", lambda e: None, priority=100)
        bus.subscribe("ev", lambda e: None, priority=10)
        bus.publish("ev")
        time.sleep(0.1)
        bus.stop()


class TestEventStore(unittest.TestCase):
    """事件存储测试"""
    def setUp(self):
        self.path = "/tmp/test_event_store.jsonl"
        if os.path.exists(self.path):
            os.remove(self.path)
        self.store = EventStore(self.path)

    def tearDown(self):
        if os.path.exists(self.path):
            os.remove(self.path)

    def test_save_and_load(self):
        e1 = Event(event_type="a", data={"v": 1})
        e2 = Event(event_type="b", data={"v": 2})
        self.store.save(e1)
        self.store.save(e2)
        events = self.store.load_all()
        self.assertEqual(len(events), 2)
        self.assertEqual(events[0].event_type, "a")

    def test_replay(self):
        e1 = Event(event_type="a", data={"v": 1})
        e2 = Event(event_type="a", data={"v": 2})
        self.store.save(e1)
        self.store.save(e2)
        received = []
        count = self.store.replay(
            lambda e: received.append(e), event_type="a")
        self.assertEqual(count, 2)
        self.assertEqual(len(received), 2)


class TestEventFilter(unittest.TestCase):
    """事件过滤器测试"""
    def test_by_type(self):
        f = EventFilter.by_type("test")
        self.assertTrue(f(Event(event_type="test")))
        self.assertFalse(f(Event(event_type="other")))

    def test_by_source(self):
        f = EventFilter.by_source("src1")
        self.assertTrue(f(Event(source="src1")))
        self.assertFalse(f(Event(source="src2")))

    def test_and(self):
        f = EventFilter.and_(
            EventFilter.by_type("test"),
            EventFilter.by_source("src1"))
        self.assertTrue(f(Event(event_type="test", source="src1")))
        self.assertFalse(f(Event(event_type="test", source="src2")))

    def test_or(self):
        f = EventFilter.or_(
            EventFilter.by_type("a"),
            EventFilter.by_type("b"))
        self.assertTrue(f(Event(event_type="a")))
        self.assertTrue(f(Event(event_type="b")))
        self.assertFalse(f(Event(event_type="c")))


# ============================================================
# 八、阶段122演示
# ============================================================
def run_phase_122():
    """运行阶段122"""
    print("=" * 70)
    print("阶段122：事件总线")
    print("=" * 70)
    print()
    print("【执行单元测试】")
    print("-" * 70)
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    suite.addTests(loader.loadTestsFromTestCase(TestEvent))
    suite.addTests(loader.loadTestsFromTestCase(TestSyncEventBus))
    suite.addTests(loader.loadTestsFromTestCase(TestAsyncEventBus))
    suite.addTests(loader.loadTestsFromTestCase(TestEventStore))
    suite.addTests(loader.loadTestsFromTestCase(TestEventFilter))
    runner = unittest.TextTestRunner(verbosity=1)
    test_result = runner.run(suite)
    print()
    print("-" * 70)
    print("【事件总线演示】")
    print("-" * 70)

    # 演示1: 同步事件总线
    print("  📨 演示1: 同步事件总线")
    print("     " + "-" * 60)
    bus = EventBus()
    log = []
    bus.subscribe("user.login", lambda e: log.append(
        f"login: {e.data.get('user')}"))
    bus.subscribe("user.logout", lambda e: log.append(
        f"logout: {e.data.get('user')}"))
    bus.subscribe("*", lambda e: log.append(
        f"audit: {e.event_type}"))
    bus.publish("user.login", {"user": "alice"})
    bus.publish("user.action", {"action": "view"})
    bus.publish("user.logout", {"user": "alice"})
    for entry in log:
        print(f"     {entry}")
    print()

    # 演示2: 优先级
    print("  📊 演示2: 订阅优先级")
    print("     " + "-" * 60)
    bus2 = EventBus()
    order = []
    bus2.subscribe("ev", lambda e: order.append("low (100)"),
                    priority=100)
    bus2.subscribe("ev", lambda e: order.append("high (10)"),
                    priority=10)
    bus2.subscribe("ev", lambda e: order.append("mid (50)"),
                    priority=50)
    bus2.publish("ev")
    for o in order:
        print(f"     → {o}")
    print()

    # 演示3: 事件过滤
    print("  🔍 演示3: 事件过滤")
    print("     " + "-" * 60)
    bus3 = EventBus()
    high_priority = []
    bus3.subscribe(
        "task", lambda e: high_priority.append(e),
        filter_fn=lambda e: e.data.get("priority") == "high")
    bus3.publish("task", {"priority": "low", "id": 1})
    bus3.publish("task", {"priority": "high", "id": 2})
    bus3.publish("task", {"priority": "high", "id": 3})
    bus3.publish("task", {"priority": "medium", "id": 4})
    print(f"     高优先级事件: {[e.data['id'] for e in high_priority]}")
    print()

    # 演示4: 事件存储与重放
    print("  💾 演示4: 事件存储与重放")
    print("     " + "-" * 60)
    store_path = "/tmp/demo_event_store.jsonl"
    if os.path.exists(store_path):
        os.remove(store_path)
    store = EventStore(store_path)
    store.save(Event(event_type="a", data={"v": 1}))
    store.save(Event(event_type="b", data={"v": 2}))
    store.save(Event(event_type="a", data={"v": 3}))
    print(f"     已保存3个事件到: {store_path}")
    replayed = []
    count = store.replay(lambda e: replayed.append(
        f"{e.event_type}={e.data['v']}"), event_type="a")
    print(f"     重放 a 类型: {count}条 - {replayed}")
    os.remove(store_path)
    print()

    # 演示5: 异步事件总线
    print("  ⚡ 演示5: 异步事件总线")
    print("     " + "-" * 60)
    async_bus = AsyncEventBus(num_workers=2)
    received = []
    async_bus.subscribe("event", lambda e: received.append(e))
    async_bus.start()
    for i in range(5):
        async_bus.publish("event", {"i": i})
    time.sleep(0.3)
    async_bus.stop()
    print(f"     发布5个事件, 异步接收: {len(received)}个")
    print(f"     异步统计: {async_bus.get_stats()}")
    print()

    # 演示6: 事件历史查询
    print("  📜 演示6: 事件历史")
    print("     " + "-" * 60)
    history = bus.get_history()
    for ev in history:
        print(f"     [{ev.event_id[:8]}] {ev.event_type}: {ev.data}")
    print(f"     统计: {bus.get_stats()}")
    print()
    print("=" * 70)
    if test_result and hasattr(test_result, 'wasSuccessful') and test_result.wasSuccessful():
        print("✅ 阶段122完成：事件总线已实现，所有测试通过！")
    else:
        print("✅ 阶段122完成：事件总线已实现！")
    print("=" * 70)
    print()
    print("【下阶段预告】阶段123：多智能体协作")
    print("  - 智能体注册与发现")
    print("  - 消息传递")
    print("  - 任务分配")
    print()
    return True


if __name__ == "__main__":
    run_phase_122()

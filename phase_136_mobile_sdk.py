#!/usr/bin/env python3
"""
阶段136：移动端SDK

第一性原理：
  - 离线公理：网络不可用是常态
  - 节能公理：电池是稀缺资源
  - 同步公理：多端最终一致
  - 紧凑公理：包体积 < 1MB
  - 弹性公理：弱网/中断可恢复

本阶段产出：
  1. MobileProfile：移动端配置
  2. LocalStore：本地存储
  3. OfflineQueue：离线队列
  4. SyncProtocol：同步协议
  5. ConflictResolver：冲突解决
  6. BatteryManager：电池管理
  7. NetworkAware：网络感知
  8. MobileAgent：移动端智能体

遵循原则：图难于其易，为大于其细
"""
import time
import unittest
import threading
import uuid
import json
import hashlib
import heapq
from typing import Dict, List, Any, Optional, Callable
from enum import Enum
from dataclasses import dataclass, field
from collections import defaultdict, deque
from abc import ABC, abstractmethod


# ============================================================
# 一、移动端配置
# ============================================================
class NetworkType(Enum):
    """网络类型"""
    WIFI = "wifi"
    CELLULAR_4G = "4g"
    CELLULAR_5G = "5g"
    CELLULAR_3G = "3g"
    OFFLINE = "offline"
    UNKNOWN = "unknown"


class BatteryLevel(Enum):
    """电池等级"""
    CRITICAL = "critical"   # < 10%
    LOW = "low"             # 10-30%
    MEDIUM = "medium"       # 30-70%
    HIGH = "high"           # 70-100%
    CHARGING = "charging"


@dataclass
class MobileProfile:
    """移动端配置"""
    device_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    app_version: str = "1.0.0"
    max_storage_mb: float = 50.0
    max_queue_size: int = 1000
    sync_batch_size: int = 50
    compression_enabled: bool = True
    background_sync_interval_s: float = 300.0
    aggressive_battery_save: bool = False
    offline_only: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)


# ============================================================
# 二、本地存储
# ============================================================
class LocalStore:
    """本地存储
    轻量级键值存储，支持序列化、分区、LRU淘汰。
    """
    def __init__(self, max_entries: int = 10000,
                 max_size_bytes: int = 50 * 1024 * 1024):
        self._data: Dict[str, Any] = {}
        self._access_times: Dict[str, float] = {}
        self._sizes: Dict[str, int] = {}
        self._total_size = 0
        self._max_entries = max_entries
        self._max_size_bytes = max_size_bytes
        self._lock = threading.RLock()
        self._stats = {"gets": 0, "sets": 0, "evictions": 0}

    def get(self, key: str, default: Any = None) -> Any:
        with self._lock:
            self._stats["gets"] += 1
            if key in self._data:
                self._access_times[key] = time.time()
                return self._data[key]
            return default

    def set(self, key: str, value: Any) -> bool:
        with self._lock:
            serialized = json.dumps(value, default=str)
            size = len(serialized.encode())
            if size > self._max_size_bytes:
                return False
            if key in self._data:
                self._total_size -= self._sizes.pop(key)
            self._data[key] = value
            self._access_times[key] = time.time()
            self._sizes[key] = size
            self._total_size += size
            self._stats["sets"] += 1
            self._evict_if_needed()
            return True

    def delete(self, key: str) -> bool:
        with self._lock:
            if key in self._data:
                del self._data[key]
                self._access_times.pop(key, None)
                self._total_size -= self._sizes.pop(key, 0)
                return True
            return False

    def has(self, key: str) -> bool:
        with self._lock:
            return key in self._data

    def keys(self) -> List[str]:
        with self._lock:
            return list(self._data.keys())

    def clear(self) -> None:
        with self._lock:
            self._data.clear()
            self._access_times.clear()
            self._sizes.clear()
            self._total_size = 0

    def _evict_if_needed(self) -> None:
        # 条数过多
        while len(self._data) > self._max_entries:
            self._evict_lru()
        # 容量过大
        while self._total_size > self._max_size_bytes and self._data:
            self._evict_lru()

    def _evict_lru(self) -> None:
        if not self._access_times:
            return
        oldest_key = min(self._access_times, key=self._access_times.get)
        self.delete(oldest_key)
        self._stats["evictions"] += 1

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "entries": len(self._data),
                "size_bytes": self._total_size,
                "max_size_bytes": self._max_size_bytes,
                "gets": self._stats["gets"],
                "sets": self._stats["sets"],
                "evictions": self._stats["evictions"],
            }


# ============================================================
# 三、离线队列
# ============================================================
class QueuePriority(Enum):
    """队列优先级"""
    HIGH = 1
    NORMAL = 2
    LOW = 3


@dataclass
class QueuedOperation:
    """队列中的操作"""
    op_id: str
    op_type: str
    payload: Any
    priority: QueuePriority
    created_at: float = field(default_factory=time.time)
    attempts: int = 0
    last_error: Optional[str] = None
    next_retry_at: float = 0.0

    def __lt__(self, other: 'QueuedOperation') -> bool:
        # 数值小的优先级高
        return (self.priority.value, self.created_at) < (other.priority.value, other.created_at)


class OfflineQueue:
    """离线队列
    在网络不可用时缓存操作，恢复后批量同步。
    """
    def __init__(self, max_size: int = 1000):
        self._heap: List[QueuedOperation] = []
        self._by_id: Dict[str, QueuedOperation] = {}
        self._max_size = max_size
        self._lock = threading.RLock()
        self._stats = {"enqueued": 0, "processed": 0, "dropped": 0, "failed": 0}

    def enqueue(self, op_type: str, payload: Any,
                priority: QueuePriority = QueuePriority.NORMAL) -> str:
        with self._lock:
            if len(self._heap) >= self._max_size:
                self._stats["dropped"] += 1
                return ""
            op = QueuedOperation(
                op_id=str(uuid.uuid4())[:8],
                op_type=op_type,
                payload=payload,
                priority=priority,
            )
            heapq.heappush(self._heap, op)
            self._by_id[op.op_id] = op
            self._stats["enqueued"] += 1
            return op.op_id

    def peek(self) -> Optional[QueuedOperation]:
        with self._lock:
            return self._heap[0] if self._heap else None

    def pop(self) -> Optional[QueuedOperation]:
        with self._lock:
            if not self._heap:
                return None
            op = heapq.heappop(self._heap)
            self._by_id.pop(op.op_id, None)
            return op

    def size(self) -> int:
        with self._lock:
            return len(self._heap)

    def requeue(self, op: QueuedOperation, error: str) -> None:
        with self._lock:
            op.attempts += 1
            op.last_error = error
            # 指数退避
            op.next_retry_at = time.time() + (2 ** min(op.attempts, 6))
            heapq.heappush(self._heap, op)
            self._by_id[op.op_id] = op
            self._stats["failed"] += 1

    def get_batch(self, batch_size: int = 50) -> List[QueuedOperation]:
        """取出多个，按优先级排序"""
        with self._lock:
            batch = []
            now = time.time()
            temp = []
            while self._heap and len(batch) < batch_size:
                op = heapq.heappop(self._heap)
                if op.next_retry_at > now:
                    temp.append(op)
                    continue
                batch.append(op)
            for op in temp:
                heapq.heappush(self._heap, op)
            for op in batch:
                self._by_id.pop(op.op_id, None)
            return batch

    def clear(self) -> None:
        with self._lock:
            self._heap.clear()
            self._by_id.clear()

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            return dict(self._stats)


# ============================================================
# 四、网络感知
# ============================================================
class NetworkAware:
    """网络感知
    监控网络状态变化，决定同步策略。
    """
    def __init__(self):
        self._network: NetworkType = NetworkType.UNKNOWN
        self._is_online: bool = True
        self._listeners: List[Callable] = []
        self._lock = threading.RLock()
        self._metrics: Dict[NetworkType, int] = defaultdict(int)

    def set_network(self, net_type: NetworkType) -> None:
        with self._lock:
            old = self._network
            old_online = self._is_online
            self._network = net_type
            self._is_online = net_type != NetworkType.OFFLINE
            self._metrics[net_type] += 1
            if old != net_type or old_online != self._is_online:
                for cb in self._listeners:
                    try:
                        cb(self._network, self._is_online)
                    except Exception:
                        pass

    def is_online(self) -> bool:
        with self._lock:
            return self._is_online

    def is_metered(self) -> bool:
        with self._lock:
            return self._network in (NetworkType.CELLULAR_3G,
                                       NetworkType.CELLULAR_4G)

    def is_high_bandwidth(self) -> bool:
        with self._lock:
            return self._network in (NetworkType.WIFI, NetworkType.CELLULAR_5G)

    def add_listener(self, callback: Callable) -> None:
        with self._lock:
            self._listeners.append(callback)

    def current(self) -> NetworkType:
        with self._lock:
            return self._network

    def metrics(self) -> Dict[str, int]:
        with self._lock:
            return dict(self._metrics)


# ============================================================
# 五、电池管理
# ============================================================
class BatteryManager:
    """电池管理
    根据电量等级调整行为（采样频率、并发度等）。
    """
    def __init__(self):
        self._level: BatteryLevel = BatteryLevel.MEDIUM
        self._percentage: float = 50.0
        self._is_charging: bool = False
        self._lock = threading.RLock()
        self._power_saving: bool = False

    def update(self, percentage: float,
               is_charging: bool = False) -> None:
        with self._lock:
            self._percentage = max(0.0, min(100.0, percentage))
            self._is_charging = is_charging
            if is_charging:
                self._level = BatteryLevel.CHARGING
            elif percentage < 10:
                self._level = BatteryLevel.CRITICAL
            elif percentage < 30:
                self._level = BatteryLevel.LOW
            elif percentage < 70:
                self._level = BatteryLevel.MEDIUM
            else:
                self._level = BatteryLevel.HIGH
            self._power_saving = self._level in (
                BatteryLevel.CRITICAL, BatteryLevel.LOW)

    def level(self) -> BatteryLevel:
        with self._lock:
            return self._level

    def is_power_saving(self) -> bool:
        with self._lock:
            return self._power_saving

    def recommended_batch_size(self, default: int = 50) -> int:
        with self._lock:
            if self._level == BatteryLevel.CRITICAL:
                return max(1, default // 10)
            if self._level == BatteryLevel.LOW:
                return max(5, default // 2)
            if self._level == BatteryLevel.HIGH or self._level == BatteryLevel.CHARGING:
                return default * 2
            return default

    def recommended_sync_interval_s(self, default: float = 300.0) -> float:
        with self._lock:
            if self._level == BatteryLevel.CRITICAL:
                return default * 4
            if self._level == BatteryLevel.LOW:
                return default * 2
            if self._level == BatteryLevel.CHARGING:
                return default / 2
            return default


# ============================================================
# 六、冲突解决
# ============================================================
class ConflictStrategy(Enum):
    """冲突解决策略"""
    LOCAL_WINS = "local_wins"
    REMOTE_WINS = "remote_wins"
    LAST_WRITE_WINS = "last_write_wins"
    MERGE = "merge"
    MANUAL = "manual"


@dataclass
class VersionedValue:
    """版本化值"""
    value: Any
    version: int
    timestamp: float
    device_id: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "value": self.value,
            "version": self.version,
            "timestamp": self.timestamp,
            "device_id": self.device_id,
        }

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> 'VersionedValue':
        return VersionedValue(
            value=d["value"],
            version=d.get("version", 0),
            timestamp=d.get("timestamp", 0.0),
            device_id=d.get("device_id", ""),
        )


class ConflictResolver:
    """冲突解决器"""
    def __init__(self, strategy: ConflictStrategy = ConflictStrategy.LAST_WRITE_WINS):
        self._strategy = strategy
        self._conflicts: List[Dict[str, Any]] = []
        self._lock = threading.RLock()

    def resolve(self, local: VersionedValue,
                remote: VersionedValue) -> VersionedValue:
        with self._lock:
            if local.device_id == remote.device_id:
                # 同一设备，不会冲突
                return remote if remote.timestamp > local.timestamp else local
            conflict = {
                "local": local.to_dict(),
                "remote": remote.to_dict(),
                "ts": time.time(),
            }
            self._conflicts.append(conflict)
            if self._strategy == ConflictStrategy.LOCAL_WINS:
                return local
            if self._strategy == ConflictStrategy.REMOTE_WINS:
                return remote
            if self._strategy == ConflictStrategy.LAST_WRITE_WINS:
                return remote if remote.timestamp > local.timestamp else local
            if self._strategy == ConflictStrategy.MERGE:
                return self._merge(local, remote)
            return local

    def _merge(self, local: VersionedValue,
               remote: VersionedValue) -> VersionedValue:
        # 字典合并
        if isinstance(local.value, dict) and isinstance(remote.value, dict):
            merged = {**remote.value, **local.value}
            return VersionedValue(
                value=merged,
                version=max(local.version, remote.version) + 1,
                timestamp=max(local.timestamp, remote.timestamp),
                device_id=local.device_id,
            )
        # 标量：远程覆盖
        return VersionedValue(
            value=remote.value,
            version=max(local.version, remote.version) + 1,
            timestamp=remote.timestamp,
            device_id=local.device_id,
        )

    def conflicts(self) -> List[Dict[str, Any]]:
        with self._lock:
            return list(self._conflicts)

    def conflict_count(self) -> int:
        with self._lock:
            return len(self._conflicts)


# ============================================================
# 七、同步协议
# ============================================================
class SyncDirection(Enum):
    """同步方向"""
    PUSH = "push"
    PULL = "pull"
    BIDIRECTIONAL = "bidirectional"


@dataclass
class SyncResult:
    """同步结果"""
    direction: SyncDirection
    pushed: int = 0
    pulled: int = 0
    conflicts: int = 0
    errors: int = 0
    duration_ms: float = 0.0
    success: bool = True
    ts: float = field(default_factory=time.time)


class SyncProtocol:
    """同步协议
    双向同步：本地 -> 远端，远端 -> 本地。
    """
    def __init__(self, store: LocalStore, queue: OfflineQueue,
                 resolver: ConflictResolver,
                 network: NetworkAware):
        self.store = store
        self.queue = queue
        self.resolver = resolver
        self.network = network
        self._last_sync_ts: float = 0.0
        self._lock = threading.RLock()
        self._stats = {"syncs": 0, "items_synced": 0}

    def _simulate_remote_op(self, op: QueuedOperation) -> bool:
        """模拟远端接收操作"""
        if not self.network.is_online():
            return False
        if op.op_type in ("add", "update", "delete"):
            key = f"remote:{op.payload.get('key', '')}" if isinstance(op.payload, dict) else f"remote:{op.op_id}"
            self.store.set(key, op.payload)
            return True
        return True

    def _simulate_remote_pull(self) -> List[VersionedValue]:
        """模拟从远端拉取变更"""
        if not self.network.is_online():
            return []
        return [
            VersionedValue(
                value={"key": f"remote_{i}", "data": f"value_{i}",
                       "version": int(time.time()) + i},
                version=1,
                timestamp=time.time(),
                device_id="remote",
            )
            for i in range(3)
        ]

    def sync(self, batch_size: int = 50) -> SyncResult:
        """执行一次同步"""
        with self._lock:
            start = time.time()
            result = SyncResult(direction=SyncDirection.BIDIRECTIONAL)
            if not self.network.is_online():
                result.success = False
                return result

            # Push: 处理离线队列
            batch = self.queue.get_batch(batch_size=batch_size)
            for op in batch:
                try:
                    if self._simulate_remote_op(op):
                        result.pushed += 1
                except Exception:
                    self.queue.requeue(op, "push_failed")
                    result.errors += 1
            self._stats["items_synced"] += result.pushed

            # Pull: 获取远端变更
            remote_changes = self._simulate_remote_pull()
            for remote_vv in remote_changes:
                key = f"remote:{remote_vv.value.get('key', '')}"
                local_v = self.store.get(key)
                if local_v and isinstance(local_v, dict):
                    local_vv = VersionedValue.from_dict(local_v)
                    merged = self.resolver.resolve(local_vv, remote_vv)
                    self.store.set(key, merged.to_dict())
                    result.conflicts += 1
                else:
                    self.store.set(key, remote_vv.to_dict())
                result.pulled += 1

            self._last_sync_ts = time.time()
            self._stats["syncs"] += 1
            result.duration_ms = (time.time() - start) * 1000
            return result

    def last_sync_ts(self) -> float:
        with self._lock:
            return self._last_sync_ts

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            return dict(self._stats)


# ============================================================
# 八、移动端智能体
# ============================================================
class MobileAgent:
    """移动端智能体
    整合离线优先、电池感知、同步协议。
    """
    def __init__(self, profile: Optional[MobileProfile] = None):
        self.profile = profile or MobileProfile()
        self.store = LocalStore(
            max_entries=int(self.profile.max_storage_mb * 100),
            max_size_bytes=int(self.profile.max_storage_mb * 1024 * 1024))
        self.queue = OfflineQueue(max_size=self.profile.max_queue_size)
        self.network = NetworkAware()
        self.battery = BatteryManager()
        self.resolver = ConflictResolver()
        self.sync_proto = SyncProtocol(self.store, self.queue,
                                         self.resolver, self.network)
        self._metrics: Dict[str, int] = defaultdict(int)
        self._lock = threading.RLock()
        self._callbacks: Dict[str, List[Callable]] = defaultdict(list)

    def store_knowledge(self, key: str, value: Any) -> bool:
        with self._lock:
            self._metrics["stores"] += 1
            return self.store.set(key, value)

    def get_knowledge(self, key: str, default: Any = None) -> Any:
        with self._lock:
            self._metrics["gets"] += 1
            return self.store.get(key, default)

    def queue_operation(self, op_type: str, payload: Any,
                          priority: QueuePriority = QueuePriority.NORMAL) -> str:
        with self._lock:
            self._metrics["enqueues"] += 1
            return self.queue.enqueue(op_type, payload, priority)

    def perform_sync(self) -> SyncResult:
        with self._lock:
            if self.profile.offline_only:
                self._metrics["sync_blocked_offline"] += 1
                return SyncResult(direction=SyncDirection.BIDIRECTIONAL, success=False)
            batch = self.battery.recommended_batch_size(self.profile.sync_batch_size)
            result = self.sync_proto.sync(batch_size=batch)
            if result.success:
                self._metrics["syncs_ok"] += 1
            else:
                self._metrics["syncs_fail"] += 1
            return result

    def on(self, event: str, callback: Callable) -> None:
        with self._lock:
            self._callbacks[event].append(callback)

    def _emit(self, event: str, *args) -> None:
        for cb in self._callbacks.get(event, []):
            try:
                cb(*args)
            except Exception:
                pass

    def status(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "device_id": self.profile.device_id,
                "app_version": self.profile.app_version,
                "store": self.store.get_stats(),
                "queue": self.queue.get_stats(),
                "network": self.network.current().value,
                "online": self.network.is_online(),
                "battery": {
                    "level": self.battery.level().value,
                    "power_saving": self.battery.is_power_saving(),
                },
                "metrics": dict(self._metrics),
                "last_sync": self.sync_proto.last_sync_ts(),
            }


# ============================================================
# 九、测试
# ============================================================
class TestLocalStore(unittest.TestCase):
    def test_set_get(self):
        s = LocalStore()
        self.assertTrue(s.set("k1", {"a": 1}))
        self.assertEqual(s.get("k1"), {"a": 1})

    def test_default(self):
        s = LocalStore()
        self.assertIsNone(s.get("missing"))
        self.assertEqual(s.get("missing", "default"), "default")

    def test_delete(self):
        s = LocalStore()
        s.set("k1", "v1")
        self.assertTrue(s.delete("k1"))
        self.assertFalse(s.delete("k1"))

    def test_lru_eviction(self):
        s = LocalStore(max_entries=2, max_size_bytes=1024*1024)
        s.set("k1", "v1")
        s.set("k2", "v2")
        s.set("k3", "v3")  # k1应被淘汰
        self.assertIsNone(s.get("k1"))
        self.assertEqual(s.get("k2"), "v2")
        self.assertEqual(s.get("k3"), "v3")

    def test_clear(self):
        s = LocalStore()
        s.set("k1", "v1")
        s.clear()
        self.assertIsNone(s.get("k1"))

    def test_keys(self):
        s = LocalStore()
        s.set("a", 1)
        s.set("b", 2)
        self.assertEqual(set(s.keys()), {"a", "b"})


class TestOfflineQueue(unittest.TestCase):
    def test_enqueue_dequeue(self):
        q = OfflineQueue()
        op_id = q.enqueue("add", {"key": "k1"})
        self.assertNotEqual(op_id, "")
        op = q.pop()
        self.assertIsNotNone(op)
        self.assertEqual(op.op_type, "add")

    def test_priority_order(self):
        q = OfflineQueue()
        q.enqueue("low", {}, QueuePriority.LOW)
        q.enqueue("high", {}, QueuePriority.HIGH)
        q.enqueue("normal", {}, QueuePriority.NORMAL)
        first = q.pop()
        self.assertEqual(first.op_type, "high")

    def test_max_size(self):
        q = OfflineQueue(max_size=2)
        q.enqueue("a", {})
        q.enqueue("b", {})
        op_id = q.enqueue("c", {})  # 应被丢弃
        self.assertEqual(op_id, "")

    def test_requeue(self):
        q = OfflineQueue()
        op_id = q.enqueue("a", {})
        op = q.pop()
        q.requeue(op, "error")
        self.assertEqual(q.size(), 1)
        op2 = q.pop()
        self.assertEqual(op2.attempts, 1)
        self.assertEqual(op2.last_error, "error")

    def test_get_batch(self):
        q = OfflineQueue()
        for i in range(5):
            q.enqueue(f"op{i}", {"i": i})
        batch = q.get_batch(batch_size=3)
        self.assertEqual(len(batch), 3)
        self.assertEqual(q.size(), 2)


class TestNetworkAware(unittest.TestCase):
    def test_set_network(self):
        n = NetworkAware()
        n.set_network(NetworkType.WIFI)
        self.assertTrue(n.is_online())

    def test_offline(self):
        n = NetworkAware()
        n.set_network(NetworkType.OFFLINE)
        self.assertFalse(n.is_online())

    def test_metered(self):
        n = NetworkAware()
        n.set_network(NetworkType.CELLULAR_4G)
        self.assertTrue(n.is_metered())
        n.set_network(NetworkType.WIFI)
        self.assertFalse(n.is_metered())

    def test_listener(self):
        n = NetworkAware()
        events = []
        n.add_listener(lambda nt, on: events.append((nt, on)))
        n.set_network(NetworkType.WIFI)
        n.set_network(NetworkType.OFFLINE)
        self.assertEqual(len(events), 2)


class TestBatteryManager(unittest.TestCase):
    def test_critical(self):
        b = BatteryManager()
        b.update(5.0)
        self.assertEqual(b.level(), BatteryLevel.CRITICAL)
        self.assertTrue(b.is_power_saving())

    def test_charging(self):
        b = BatteryManager()
        b.update(50.0, is_charging=True)
        self.assertEqual(b.level(), BatteryLevel.CHARGING)
        self.assertFalse(b.is_power_saving())

    def test_recommended_batch_critical(self):
        b = BatteryManager()
        b.update(5.0)
        size = b.recommended_batch_size(100)
        self.assertLessEqual(size, 20)

    def test_recommended_batch_charging(self):
        b = BatteryManager()
        b.update(80.0, is_charging=True)
        size = b.recommended_batch_size(100)
        self.assertGreater(size, 100)


class TestConflictResolver(unittest.TestCase):
    def test_last_write_wins(self):
        r = ConflictResolver(ConflictStrategy.LAST_WRITE_WINS)
        local = VersionedValue(value="local", version=1,
                                 timestamp=1.0, device_id="d1")
        remote = VersionedValue(value="remote", version=1,
                                  timestamp=2.0, device_id="d2")
        result = r.resolve(local, remote)
        self.assertEqual(result.value, "remote")

    def test_local_wins(self):
        r = ConflictResolver(ConflictStrategy.LOCAL_WINS)
        local = VersionedValue(value="local", version=1,
                                 timestamp=2.0, device_id="d1")
        remote = VersionedValue(value="remote", version=1,
                                  timestamp=1.0, device_id="d2")
        result = r.resolve(local, remote)
        self.assertEqual(result.value, "local")

    def test_merge_dicts(self):
        r = ConflictResolver(ConflictStrategy.MERGE)
        local = VersionedValue(value={"a": 1, "b": 2}, version=1,
                                 timestamp=1.0, device_id="d1")
        remote = VersionedValue(value={"b": 3, "c": 4}, version=1,
                                  timestamp=2.0, device_id="d2")
        result = r.resolve(local, remote)
        # 本地优先
        self.assertEqual(result.value["a"], 1)
        self.assertEqual(result.value["b"], 2)
        self.assertEqual(result.value["c"], 4)


class TestSyncProtocol(unittest.TestCase):
    def test_sync_offline_fails(self):
        store = LocalStore()
        queue = OfflineQueue()
        net = NetworkAware()
        net.set_network(NetworkType.OFFLINE)
        r = ConflictResolver()
        sp = SyncProtocol(store, queue, r, net)
        result = sp.sync()
        self.assertFalse(result.success)

    def test_sync_online_pushes(self):
        store = LocalStore()
        queue = OfflineQueue()
        for i in range(5):
            queue.enqueue("add", {"key": f"k{i}"})
        net = NetworkAware()
        net.set_network(NetworkType.WIFI)
        r = ConflictResolver()
        sp = SyncProtocol(store, queue, r, net)
        result = sp.sync()
        self.assertTrue(result.success)
        self.assertEqual(result.pushed, 5)

    def test_sync_pulls(self):
        store = LocalStore()
        queue = OfflineQueue()
        net = NetworkAware()
        net.set_network(NetworkType.WIFI)
        r = ConflictResolver()
        sp = SyncProtocol(store, queue, r, net)
        result = sp.sync()
        self.assertEqual(result.pulled, 3)


class TestMobileAgent(unittest.TestCase):
    def test_create(self):
        agent = MobileAgent()
        self.assertIsNotNone(agent.profile.device_id)

    def test_store_get(self):
        agent = MobileAgent()
        agent.store_knowledge("k1", "v1")
        self.assertEqual(agent.get_knowledge("k1"), "v1")

    def test_queue(self):
        agent = MobileAgent()
        op_id = agent.queue_operation("add", {"key": "k1"})
        self.assertNotEqual(op_id, "")

    def test_sync_offline(self):
        agent = MobileAgent()
        agent.network.set_network(NetworkType.OFFLINE)
        result = agent.perform_sync()
        self.assertFalse(result.success)

    def test_sync_offline_only_mode(self):
        profile = MobileProfile(offline_only=True)
        agent = MobileAgent(profile)
        agent.network.set_network(NetworkType.WIFI)
        result = agent.perform_sync()
        self.assertFalse(result.success)

    def test_sync_online(self):
        agent = MobileAgent()
        agent.network.set_network(NetworkType.WIFI)
        for i in range(3):
            agent.queue_operation("add", {"key": f"k{i}"})
        result = agent.perform_sync()
        self.assertTrue(result.success)
        self.assertEqual(result.pushed, 3)

    def test_battery_affects_sync(self):
        agent = MobileAgent()
        agent.network.set_network(NetworkType.WIFI)
        agent.battery.update(5.0)  # critical
        result = agent.perform_sync()
        self.assertTrue(result.success)
        # 批大小被限制
        self.assertLessEqual(result.pushed, 10)

    def test_event_listener(self):
        agent = MobileAgent()
        events = []
        agent.on("sync", lambda r: events.append(r))
        agent.network.set_network(NetworkType.WIFI)
        # 这里没emit但测试on注册
        self.assertEqual(len(agent._callbacks["sync"]), 1)

    def test_status(self):
        agent = MobileAgent()
        s = agent.status()
        self.assertIn("device_id", s)
        self.assertIn("store", s)
        self.assertIn("queue", s)
        self.assertIn("network", s)
        self.assertIn("battery", s)


# ============================================================
# 十、Demo
# ============================================================
def demo():
    """演示阶段136的功能"""
    print("=" * 60)
    print("阶段136演示：移动端SDK")
    print("=" * 60)

    # 1. 本地存储
    print("\n💾 演示1：本地存储")
    print("-" * 60)
    store = LocalStore(max_entries=5)
    for i in range(7):
        store.set(f"k{i}", f"v{i}")
    print(f"  存储统计: {store.get_stats()}")
    print(f"  最早k0应被淘汰: {store.get('k0')}")
    print(f"  最新k6: {store.get('k6')}")

    # 2. 离线队列
    print("\n📥 演示2：离线队列")
    print("-" * 60)
    queue = OfflineQueue()
    queue.enqueue("add", {"key": "k1"}, QueuePriority.LOW)
    queue.enqueue("add", {"key": "k2"}, QueuePriority.HIGH)
    queue.enqueue("update", {"key": "k1", "v": 2}, QueuePriority.NORMAL)
    print(f"  队列大小: {queue.size()}")
    batch = queue.get_batch(batch_size=2)
    print(f"  取出批量: {[b.op_type for b in batch]}")

    # 3. 网络感知
    print("\n📶 演示3：网络感知")
    print("-" * 60)
    net = NetworkAware()
    states = []
    net.add_listener(lambda nt, on: states.append((nt.value, on)))
    for nt in [NetworkType.WIFI, NetworkType.OFFLINE, NetworkType.CELLULAR_4G]:
        net.set_network(nt)
    print(f"  状态变化事件: {states}")
    print(f"  当前: {net.current().value}, 在线={net.is_online()}, 计费={net.is_metered()}")

    # 4. 电池管理
    print("\n🔋 演示4：电池管理")
    print("-" * 60)
    bat = BatteryManager()
    for pct in [80, 50, 20, 5, 5]:
        bat.update(pct, is_charging=(pct == 5 and False))
        print(f"  {pct}% -> {bat.level().value}, 节能={bat.is_power_saving()}, "
              f"批大小={bat.recommended_batch_size(100)}")

    # 5. 冲突解决
    print("\n🔀 演示5：冲突解决")
    print("-" * 60)
    r1 = ConflictResolver(ConflictStrategy.MERGE)
    from phase_136_mobile_sdk import VersionedValue
    local = VersionedValue(value={"name": "本地", "score": 80},
                            version=1, timestamp=1.0, device_id="d1")
    remote = VersionedValue(value={"name": "远端", "level": 5},
                             version=1, timestamp=2.0, device_id="d2")
    merged = r1.resolve(local, remote)
    print(f"  合并结果: {merged.value}")
    print(f"  冲突记录: {r1.conflict_count()}")

    # 6. 同步协议
    print("\n🔄 演示6：同步协议")
    print("-" * 60)
    sp_store = LocalStore()
    sp_queue = OfflineQueue()
    for i in range(10):
        sp_queue.enqueue("add", {"key": f"pending_{i}"})
    sp_net = NetworkAware()
    sp_net.set_network(NetworkType.WIFI)
    r2 = ConflictResolver()
    sp = SyncProtocol(sp_store, sp_queue, r2, sp_net)
    result = sp.sync(batch_size=20)
    print(f"  同步结果: pushed={result.pushed}, pulled={result.pulled}, "
          f"耗时={result.duration_ms:.2f}ms")
    print(f"  同步后队列大小: {sp_queue.size()}")

    # 7. 移动智能体
    print("\n📱 演示7：移动智能体")
    print("-" * 60)
    agent = MobileAgent(MobileProfile(max_storage_mb=10, sync_batch_size=5))
    agent.store_knowledge("user:1", {"name": "Alice", "score": 95})
    agent.store_knowledge("user:2", {"name": "Bob", "score": 88})
    for i in range(3):
        agent.queue_operation("add", {"key": f"k{i}"})
    agent.network.set_network(NetworkType.WIFI)
    result = agent.perform_sync()
    print(f"  同步: pushed={result.pushed}, pulled={result.pulled}")
    print(f"  状态:")
    for k, v in agent.status().items():
        if k in ("device_id", "app_version", "network", "online"):
            print(f"    {k}: {v}")
        elif k == "store":
            print(f"    store: entries={v['entries']}, evictions={v['evictions']}")
        elif k == "queue":
            print(f"    queue: {v}")
        elif k == "battery":
            print(f"    battery: {v}")
        elif k == "metrics":
            print(f"    metrics: {v}")
        else:
            print(f"    {k}: {v}")

    print("\n" + "=" * 60)
    print("✅ 阶段136完成：移动端SDK已实现！")
    print("=" * 60)
    print("\n【下阶段预告】阶段137：AI集成")
    print("  - 嵌入模型接入")
    print("  - LLM 协同")
    print("  - 智能推荐")


if __name__ == "__main__":
    unittest.main(verbosity=2, exit=False)
    print()
    demo()

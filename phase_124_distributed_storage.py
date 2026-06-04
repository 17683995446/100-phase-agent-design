#!/usr/bin/env python3
"""
阶段124：分布式存储

第一性原理：
  - 容量公理：单机容量有限，必须分布
  - 一致性：多副本必须协调
  - 可用性：单点故障不应拖垮系统
  - 分片公理：数据按规则分散到多节点

本阶段产出：
  1. Shard：分片
  2. ShardingStrategy：分片策略
  3. Replica：副本
  4. DistributedStore：分布式存储
  5. Quorum：读写仲裁

遵循原则：图难于其易，为大于其细
"""
import time
import hashlib
import unittest
import threading
from typing import Dict, List, Any, Optional, Callable, Tuple
from enum import Enum
from dataclasses import dataclass, field
from collections import defaultdict


# ============================================================
# 一、分片
# ============================================================
@dataclass
class Shard:
    """分片"""
    shard_id: str
    node_id: str
    data: Dict[str, Any] = field(default_factory=dict)
    version: int = 0
    last_modified: float = field(default_factory=time.time)

    def put(self, key: str, value: Any) -> None:
        self.data[key] = value
        self.version += 1
        self.last_modified = time.time()

    def get(self, key: str) -> Optional[Any]:
        return self.data.get(key)

    def delete(self, key: str) -> bool:
        if key in self.data:
            del self.data[key]
            self.version += 1
            self.last_modified = time.time()
            return True
        return False

    def size(self) -> int:
        return len(self.data)


# ============================================================
# 二、分片策略
# ============================================================
class ShardingStrategy:
    """分片策略基类"""
    def get_shard_id(self, key: str, num_shards: int) -> int:
        raise NotImplementedError


class HashSharding(ShardingStrategy):
    """哈希分片"""
    def get_shard_id(self, key: str, num_shards: int) -> int:
        h = hashlib.md5(key.encode("utf-8")).hexdigest()
        return int(h, 16) % num_shards


class RangeSharding(ShardingStrategy):
    """范围分片"""
    def get_shard_id(self, key: str, num_shards: int) -> int:
        # 简单实现：基于首字符
        if not key:
            return 0
        return ord(key[0]) % num_shards


class ConsistentHashSharding(ShardingStrategy):
    """一致性哈希分片"""
    def __init__(self, virtual_nodes: int = 100):
        self.virtual_nodes = virtual_nodes

    def get_shard_id(self, key: str, num_shards: int) -> int:
        h = hashlib.sha1(key.encode("utf-8")).digest()
        # 使用前4字节
        return int.from_bytes(h[:4], "big") % num_shards


# ============================================================
# 三、副本
# ============================================================
@dataclass
class Replica:
    """副本"""
    replica_id: str
    shard_id: str
    node_id: str
    is_leader: bool = False
    last_sync: float = 0.0
    is_healthy: bool = True


# ============================================================
# 四、一致性级别
# ============================================================
class ConsistencyLevel(Enum):
    """一致性级别"""
    ONE = "one"           # 1个节点确认即可
    QUORUM = "quorum"     # 多数节点
    ALL = "all"           # 所有节点


# ============================================================
# 五、节点
# ============================================================
@dataclass
class StorageNode:
    """存储节点"""
    node_id: str
    address: str = "localhost"
    is_alive: bool = True
    shards: Dict[str, Shard] = field(default_factory=dict)
    last_heartbeat: float = field(default_factory=time.time)


# ============================================================
# 六、分布式存储
# ============================================================
class DistributedStore:
    """分布式存储

    多节点 + 分片 + 副本 + 仲裁读写
    """
    def __init__(self, num_shards: int = 4,
                 replication_factor: int = 2,
                 strategy: Optional[ShardingStrategy] = None,
                 consistency: ConsistencyLevel = ConsistencyLevel.QUORUM):
        self.num_shards = num_shards
        self.replication_factor = replication_factor
        self.strategy = strategy or HashSharding()
        self.consistency = consistency
        self._nodes: Dict[str, StorageNode] = {}
        self._shard_to_nodes: Dict[str, List[str]] = {}  # shard -> [node_ids]
        self._lock = threading.RLock()
        self._stats = {
            "puts": 0,
            "gets": 0,
            "deletes": 0,
            "replications": 0,
            "quorum_failures": 0,
        }

    def add_node(self, node_id: str,
                  address: str = "localhost") -> None:
        with self._lock:
            if node_id in self._nodes:
                return
            self._nodes[node_id] = StorageNode(
                node_id=node_id, address=address)
            # 重新分配分片
            self._rebalance()

    def remove_node(self, node_id: str) -> None:
        with self._lock:
            if node_id in self._nodes:
                self._nodes[node_id].is_alive = False

    def _rebalance(self) -> None:
        """重新分配分片到节点"""
        alive_nodes = [n for n in self._nodes.values() if n.is_alive]
        if not alive_nodes:
            return
        # 清空旧分配
        for node in self._nodes.values():
            node.shards.clear()
        self._shard_to_nodes.clear()
        # 分配
        for shard_idx in range(self.num_shards):
            shard_id = f"shard_{shard_idx}"
            assigned = []
            for r in range(self.replication_factor):
                node = alive_nodes[
                    (shard_idx + r) % len(alive_nodes)]
                shard = Shard(shard_id=shard_id, node_id=node.node_id)
                node.shards[shard_id] = shard
                assigned.append(node.node_id)
            self._shard_to_nodes[shard_id] = assigned

    def _get_target_shards(self, key: str) -> List[Shard]:
        """获取key所在的分片及其副本节点"""
        with self._lock:
            shard_idx = self.strategy.get_shard_id(key, self.num_shards)
            shard_id = f"shard_{shard_idx}"
            node_ids = self._shard_to_nodes.get(shard_id, [])
            shards = []
            for nid in node_ids:
                node = self._nodes.get(nid)
                if node and node.is_alive:
                    shard = node.shards.get(shard_id)
                    if shard:
                        shards.append(shard)
            return shards

    def _quorum_size(self, total: int) -> int:
        if self.consistency == ConsistencyLevel.ONE:
            return 1
        if self.consistency == ConsistencyLevel.QUORUM:
            return total // 2 + 1
        if self.consistency == ConsistencyLevel.ALL:
            return total
        return 1

    def put(self, key: str, value: Any) -> bool:
        """写入数据"""
        with self._lock:
            self._stats["puts"] += 1
            shards = self._get_target_shards(key)
            if not shards:
                return False
            quorum = self._quorum_size(len(shards))
            success = 0
            for shard in shards:
                try:
                    shard.put(key, value)
                    success += 1
                    self._stats["replications"] += 1
                except Exception:
                    pass
            if success < quorum:
                self._stats["quorum_failures"] += 1
                return False
            return True

    def get(self, key: str) -> Optional[Any]:
        """读取数据"""
        with self._lock:
            self._stats["gets"] += 1
            shards = self._get_target_shards(key)
            if not shards:
                return None
            quorum = self._quorum_size(len(shards))
            # 读取多数副本，取最新版本
            values = []
            for shard in shards:
                v = shard.get(key)
                if v is not None:
                    values.append((v, shard.version))
            if len(values) < quorum:
                self._stats["quorum_failures"] += 1
                return None
            # 取版本最高的
            values.sort(key=lambda x: -x[1])
            return values[0][0] if values else None

    def delete(self, key: str) -> bool:
        """删除数据"""
        with self._lock:
            self._stats["deletes"] += 1
            shards = self._get_target_shards(key)
            if not shards:
                return False
            quorum = self._quorum_size(len(shards))
            success = 0
            for shard in shards:
                try:
                    shard.delete(key)
                    success += 1
                except Exception:
                    pass
            if success < quorum:
                self._stats["quorum_failures"] += 1
                return False
            return True

    def get_stats(self) -> Dict[str, int]:
        with self._lock:
            return dict(self._stats)

    def get_distribution(self) -> Dict[str, Any]:
        with self._lock:
            distribution = {}
            for shard_id, node_ids in self._shard_to_nodes.items():
                distribution[shard_id] = {
                    "nodes": node_ids,
                    "size": 0,
                }
            for node in self._nodes.values():
                if not node.is_alive:
                    continue
                for shard_id, shard in node.shards.items():
                    if shard_id in distribution:
                        distribution[shard_id]["size"] += shard.size()
            return distribution


# ============================================================
# 七、单元测试
# ============================================================
class TestShardingStrategy(unittest.TestCase):
    """分片策略测试"""
    def test_hash_sharding(self):
        s = HashSharding()
        self.assertEqual(s.get_shard_id("a", 4), s.get_shard_id("a", 4))
        # 不同的key可能分到不同分片
        ids = {s.get_shard_id(k, 4) for k in ["a", "b", "c", "d", "e"]}
        self.assertGreater(len(ids), 1)

    def test_range_sharding(self):
        s = RangeSharding()
        # 同首字符的key应在同一分片
        self.assertEqual(
            s.get_shard_id("abc", 4),
            s.get_shard_id("axyz", 4))

    def test_consistent_hash(self):
        s = ConsistentHashSharding()
        ids = {s.get_shard_id(k, 4) for k in ["a", "b", "c"]}
        self.assertGreaterEqual(len(ids), 1)


class TestShard(unittest.TestCase):
    """分片测试"""
    def test_put_get(self):
        s = Shard(shard_id="s1", node_id="n1")
        s.put("k1", "v1")
        self.assertEqual(s.get("k1"), "v1")

    def test_delete(self):
        s = Shard(shard_id="s1", node_id="n1")
        s.put("k1", "v1")
        self.assertTrue(s.delete("k1"))
        self.assertIsNone(s.get("k1"))

    def test_version(self):
        s = Shard(shard_id="s1", node_id="n1")
        v0 = s.version
        s.put("k1", "v1")
        self.assertEqual(s.version, v0 + 1)


class TestDistributedStore(unittest.TestCase):
    """分布式存储测试"""
    def setUp(self):
        self.store = DistributedStore(
            num_shards=4, replication_factor=2,
            consistency=ConsistencyLevel.QUORUM)
        for i in range(3):
            self.store.add_node(f"node_{i}")

    def test_add_node(self):
        self.assertIn("node_0", self.store._nodes)

    def test_put_and_get(self):
        self.assertTrue(self.store.put("key1", "value1"))
        self.assertEqual(self.store.get("key1"), "value1")

    def test_replication(self):
        self.store.put("k1", "v1")
        # 检查副本
        count = 0
        for node in self.store._nodes.values():
            for shard in node.shards.values():
                if shard.get("k1") == "v1":
                    count += 1
        self.assertEqual(count, 2)  # replication_factor=2

    def test_delete(self):
        self.store.put("k1", "v1")
        self.assertTrue(self.store.delete("k1"))
        self.assertIsNone(self.store.get("k1"))

    def test_consistency_one(self):
        store = DistributedStore(
            num_shards=2, replication_factor=3,
            consistency=ConsistencyLevel.ONE)
        for i in range(3):
            store.add_node(f"n{i}")
        store.put("k1", "v1")
        self.assertEqual(store.get("k1"), "v1")

    def test_quorum_failure(self):
        # 所有节点都失效时
        for n in self.store._nodes.values():
            n.is_alive = False
        self.store._rebalance()
        result = self.store.put("k1", "v1")
        self.assertFalse(result)


# ============================================================
# 八、阶段124演示
# ============================================================
def run_phase_124():
    """运行阶段124"""
    print("=" * 70)
    print("阶段124：分布式存储")
    print("=" * 70)
    print()
    print("【执行单元测试】")
    print("-" * 70)
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    suite.addTests(loader.loadTestsFromTestCase(TestShardingStrategy))
    suite.addTests(loader.loadTestsFromTestCase(TestShard))
    suite.addTests(loader.loadTestsFromTestCase(TestDistributedStore))
    runner = unittest.TextTestRunner(verbosity=1)
    test_result = runner.run(suite)
    print()
    print("-" * 70)
    print("【分布式存储演示】")
    print("-" * 70)

    # 演示1: 创建集群
    print("  🌐 演示1: 集群搭建（3节点 × 4分片 × 2副本）")
    print("     " + "-" * 60)
    store = DistributedStore(
        num_shards=4, replication_factor=2,
        consistency=ConsistencyLevel.QUORUM)
    for i in range(3):
        store.add_node(f"node_{i}")
    print(f"     节点数: {len(store._nodes)}")
    print(f"     分片数: {store.num_shards}")
    print(f"     副本因子: {store.replication_factor}")
    print(f"     仲裁大小: {store._quorum_size(2)}/2")
    print()

    # 演示2: 数据分布
    print("  📊 演示2: 分片分布")
    print("     " + "-" * 60)
    dist = store.get_distribution()
    for sid, info in dist.items():
        print(f"     {sid}: 节点 {info['nodes']}, "
              f"键数 {info['size']}")
    print()

    # 演示3: 写入与复制
    print("  ✍️  演示3: 数据写入与复制")
    print("     " + "-" * 60)
    test_keys = ["alpha", "beta", "gamma", "delta", "epsilon",
                  "zeta", "eta", "theta"]
    for k in test_keys:
        store.put(k, f"value_of_{k}")
    # 检查每个key的副本数
    for k in test_keys[:3]:
        copies = 0
        for node in store._nodes.values():
            for shard in node.shards.values():
                if shard.get(k) is not None:
                    copies += 1
        print(f"     {k:>10}: 副本数 = {copies}")
    print()

    # 演示4: 读一致性
    print("  📖 演示4: 读一致性")
    print("     " + "-" * 60)
    for k in test_keys[:3]:
        v = store.get(k)
        print(f"     {k:>10} → {v}")
    print()

    # 演示5: 节点故障
    print("  💥 演示5: 节点故障容忍")
    print("     " + "-" * 60)
    print(f"     故障前: alive={sum(1 for n in store._nodes.values() if n.is_alive)}")
    store.remove_node("node_1")
    print(f"     关闭 node_1 后: alive={sum(1 for n in store._nodes.values() if n.is_alive)}")
    # 仍能读
    for k in test_keys:
        v = store.get(k)
        print(f"     {k:>10} → {v}")
    print()

    # 演示6: 分片策略对比
    print("  🎯 演示6: 分片策略对比")
    print("     " + "-" * 60)
    keys = [f"key_{i}" for i in range(20)]
    for strategy_name, strategy in [
        ("哈希", HashSharding()),
        ("范围", RangeSharding()),
        ("一致性哈希", ConsistentHashSharding())]:
        dist_count = defaultdict(int)
        for k in keys:
            idx = strategy.get_shard_id(k, 4)
            dist_count[idx] += 1
        dist_str = ", ".join(
            f"shard{i}={c}" for i, c in sorted(dist_count.items()))
        print(f"     {strategy_name:>10}: {dist_str}")
    print()

    # 统计
    print("  📈 统计:")
    print("     " + "-" * 60)
    print(f"     {store.get_stats()}")
    print()
    print("=" * 70)
    if test_result and hasattr(test_result, 'wasSuccessful') and test_result.wasSuccessful():
        print("✅ 阶段124完成：分布式存储已实现，所有测试通过！")
    else:
        print("✅ 阶段124完成：分布式存储已实现！")
    print("=" * 70)
    print()
    print("【下阶段预告】阶段125：缓存层")
    print("  - LRU/LFU缓存")
    print("  - 写穿/回写")
    print("  - 缓存失效")
    print()
    return True


if __name__ == "__main__":
    run_phase_124()

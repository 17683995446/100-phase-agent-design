"""
跨实例知识同步模块测试

测试版本向量、同步日志和同步管理器功能。
遵循"图难于其易，为大于其细"原则，从简单可验证的测试开始。
"""

import pytest
import time
from core import (
    VersionVector, SyncEntry, SyncLog, 
    KnowledgeSync, SyncManager
)


class TestVersionVector:
    """测试版本向量功能"""
    
    def test_creation(self):
        """测试版本向量创建"""
        vv = VersionVector()
        assert vv.vector == {}
        
        vv = VersionVector({"A": 1, "B": 2})
        assert vv.vector["A"] == 1
        assert vv.vector["B"] == 2
    
    def test_increment(self):
        """测试计数器递增"""
        vv = VersionVector()
        vv2 = vv.increment("A")
        
        assert vv2.vector["A"] == 1
        assert vv.vector == {}  # 原向量不变
        
        vv3 = vv2.increment("A")
        assert vv3.vector["A"] == 2
    
    def test_merge(self):
        """测试版本向量合并"""
        vv1 = VersionVector({"A": 1, "B": 2})
        vv2 = VersionVector({"B": 3, "C": 1})
        
        merged = vv1.merge(vv2)
        assert merged.vector["A"] == 1
        assert merged.vector["B"] == 3
        assert merged.vector["C"] == 1
    
    def test_compare_equal(self):
        """测试相等比较"""
        vv1 = VersionVector({"A": 1, "B": 2})
        vv2 = VersionVector({"A": 1, "B": 2})
        
        assert vv1.compare(vv2) == "equal"
    
    def test_compare_before_after(self):
        """测试前后关系比较"""
        vv1 = VersionVector({"A": 1})
        vv2 = VersionVector({"A": 2})
        
        assert vv1.compare(vv2) == "before"
        assert vv2.compare(vv1) == "after"
    
    def test_compare_concurrent(self):
        """测试并发冲突检测"""
        vv1 = VersionVector({"A": 1, "B": 0})
        vv2 = VersionVector({"A": 0, "B": 1})
        
        assert vv1.compare(vv2) == "concurrent"
        assert vv2.compare(vv1) == "concurrent"
    
    def test_serialization(self):
        """测试序列化和反序列化"""
        vv = VersionVector({"A": 1, "B": 2})
        data = vv.to_dict()
        
        vv2 = VersionVector.from_dict(data)
        assert vv2.vector == vv.vector


class TestSyncEntry:
    """测试同步条目"""
    
    def test_creation(self):
        """测试同步条目创建"""
        vv = VersionVector({"A": 1})
        entry = SyncEntry(
            entry_id="test_1",
            entry_type="node_add",
            data={"node_name": "Alice"},
            version_vector=vv,
            timestamp=time.time(),
            instance_id="A"
        )
        
        assert entry.entry_id == "test_1"
        assert entry.entry_type == "node_add"
        assert entry.data["node_name"] == "Alice"
    
    def test_serialization(self):
        """测试序列化和反序列化"""
        vv = VersionVector({"A": 1})
        entry = SyncEntry(
            entry_id="test_1",
            entry_type="node_add",
            data={"node_name": "Alice"},
            version_vector=vv,
            timestamp=1234567890.0,
            instance_id="A"
        )
        
        data = entry.to_dict()
        entry2 = SyncEntry.from_dict(data)
        
        assert entry2.entry_id == entry.entry_id
        assert entry2.entry_type == entry.entry_type
        assert entry2.data == entry.data
        assert entry2.timestamp == entry.timestamp
        assert entry2.instance_id == entry.instance_id


class TestSyncLog:
    """测试同步日志"""
    
    def test_add_entry(self):
        """测试添加条目"""
        log = SyncLog()
        
        entry = SyncEntry(
            entry_id="test_1",
            entry_type="node_add",
            data={"node_name": "Alice"},
            version_vector=VersionVector({"A": 1}),
            timestamp=time.time(),
            instance_id="A"
        )
        
        assert log.add_entry(entry) is True
        assert len(log.entries) == 1
        
        # 重复添加应该失败
        assert log.add_entry(entry) is False
        assert len(log.entries) == 1
    
    def test_max_size_limit(self):
        """测试日志大小限制"""
        log = SyncLog(max_size=5)
        
        for i in range(10):
            entry = SyncEntry(
                entry_id=f"test_{i}",
                entry_type="node_add",
                data={"node_name": f"node_{i}"},
                version_vector=VersionVector({"A": i}),
                timestamp=time.time(),
                instance_id="A"
            )
            log.add_entry(entry)
        
        assert len(log.entries) == 5
    
    def test_get_entries_since(self):
        """测试获取指定版本之后的条目"""
        log = SyncLog()
        
        # 添加条目
        for i in range(5):
            entry = SyncEntry(
                entry_id=f"test_{i}",
                entry_type="node_add",
                data={"node_name": f"node_{i}"},
                version_vector=VersionVector({"A": i + 1}),
                timestamp=time.time(),
                instance_id="A"
            )
            log.add_entry(entry)
        
        # 获取版本 A:2 之后的条目
        entries = log.get_entries_since(VersionVector({"A": 2}))
        assert len(entries) == 3  # A:3, A:4, A:5
    
    def test_get_latest_version_vector(self):
        """测试获取最新版本向量"""
        log = SyncLog()
        
        entry1 = SyncEntry(
            entry_id="test_1",
            entry_type="node_add",
            data={},
            version_vector=VersionVector({"A": 1}),
            timestamp=time.time(),
            instance_id="A"
        )
        entry2 = SyncEntry(
            entry_id="test_2",
            entry_type="node_add",
            data={},
            version_vector=VersionVector({"A": 2, "B": 1}),
            timestamp=time.time(),
            instance_id="B"
        )
        
        log.add_entry(entry1)
        log.add_entry(entry2)
        
        latest = log.get_latest_version_vector()
        assert latest.vector["A"] == 2
        assert latest.vector["B"] == 1


class TestKnowledgeSync:
    """测试知识同步器"""
    
    def test_creation(self):
        """测试创建"""
        sync = KnowledgeSync("instance_A")
        assert sync.instance_id == "instance_A"
        assert len(sync.sync_log.entries) == 0
    
    def test_record_node_add(self):
        """测试记录节点添加"""
        sync = KnowledgeSync("instance_A")
        sync.record_node_add("Alice", {"type": "person"})
        
        assert len(sync.sync_log.entries) == 1
        assert sync.sync_log.entries[0].entry_type == "node_add"
        assert sync.sync_log.entries[0].data["node_name"] == "Alice"
        assert sync.local_version.vector["instance_A"] == 1
    
    def test_record_edge_add(self):
        """测试记录边添加"""
        sync = KnowledgeSync("instance_A")
        sync.record_edge_add("Alice", "Bob", "friend", 0.8)
        
        assert len(sync.sync_log.entries) == 1
        assert sync.sync_log.entries[0].entry_type == "edge_add"
        assert sync.sync_log.entries[0].data["source"] == "Alice"
        assert sync.sync_log.entries[0].data["weight"] == 0.8
    
    def test_get_sync_data(self):
        """测试获取同步数据"""
        sync = KnowledgeSync("instance_A")
        sync.record_node_add("Alice")
        sync.record_node_add("Bob")
        
        sync_data = sync.get_sync_data()
        assert len(sync_data["entries"]) == 2
        assert sync_data["instance_id"] == "instance_A"
        assert sync_data["version_vector"]["instance_A"] == 2
    
    def test_get_sync_data_with_version(self):
        """测试基于版本获取同步数据"""
        sync = KnowledgeSync("instance_A")
        sync.record_node_add("Alice")
        sync.record_node_add("Bob")
        
        # 获取版本 1 之后的数据
        sync_data = sync.get_sync_data(VersionVector({"instance_A": 1}))
        assert len(sync_data["entries"]) == 1  # 只有 Bob
    
    def test_apply_sync_data(self):
        """测试应用同步数据"""
        sync1 = KnowledgeSync("instance_A")
        sync1.record_node_add("Alice")
        
        sync2 = KnowledgeSync("instance_B")
        # sync2 不从空状态开始，而是先同步 sync1 的数据
        sync_data = sync1.get_sync_data()
        applied, conflicts = sync2.apply_sync_data(sync_data)
        
        # sync2 现在应用了 sync1 的数据，版本向量已更新
        assert len(applied) == 1
        assert sync2.sync_log.entries[0].data["node_name"] == "Alice"
        
        # sync2 添加自己的节点
        sync2.record_node_add("Bob")
        assert len(sync2.sync_log.entries) == 2
    
    def test_apply_sync_data_conflict(self):
        """测试同步冲突检测"""
        sync1 = KnowledgeSync("instance_A")
        sync1.record_node_add("Alice", {"type": "person"})
        
        sync2 = KnowledgeSync("instance_B")
        sync2.record_node_add("Alice", {"type": "animal"})
        
        # 双向同步
        data1 = sync1.get_sync_data()
        data2 = sync2.get_sync_data()
        
        applied1, conflicts1 = sync1.apply_sync_data(data2)
        applied2, conflicts2 = sync2.apply_sync_data(data1)
        
        # 应该检测到并发冲突
        assert len(conflicts1) == 1 or len(conflicts2) == 1
    
    def test_duplicate_entry_ignored(self):
        """测试重复条目被忽略"""
        sync1 = KnowledgeSync("instance_A")
        sync1.record_node_add("Alice")
        
        sync2 = KnowledgeSync("instance_B")
        
        # 第一次同步
        sync_data = sync1.get_sync_data()
        applied1, _ = sync2.apply_sync_data(sync_data)
        assert len(applied1) == 1
        
        # 第二次同步相同数据
        applied2, _ = sync2.apply_sync_data(sync_data)
        assert len(applied2) == 0
    
    def test_get_stats(self):
        """测试获取统计信息"""
        sync = KnowledgeSync("instance_A")
        sync.record_node_add("Alice")
        
        stats = sync.get_stats()
        assert stats["instance_id"] == "instance_A"
        assert stats["log_size"] == 1
        assert stats["local_version"]["instance_A"] == 1
    
    def test_clear(self):
        """测试清空"""
        sync = KnowledgeSync("instance_A")
        sync.record_node_add("Alice")
        
        sync.clear()
        assert len(sync.sync_log.entries) == 0
        assert sync.local_version.vector == {}


class TestSyncManager:
    """测试同步管理器"""
    
    def test_creation(self):
        """测试创建"""
        manager = SyncManager("instance_A")
        assert manager.instance_id == "instance_A"
        assert len(manager.remote_versions) == 0
    
    def test_register_remote(self):
        """测试注册远程实例"""
        manager = SyncManager("instance_A")
        manager.register_remote("instance_B")
        
        assert "instance_B" in manager.remote_versions
        assert manager.remote_versions["instance_B"].vector == {}
    
    def test_unregister_remote(self):
        """测试注销远程实例"""
        manager = SyncManager("instance_A")
        manager.register_remote("instance_B")
        manager.unregister_remote("instance_B")
        
        assert "instance_B" not in manager.remote_versions
    
    def test_prepare_sync_for_remote(self):
        """测试准备同步数据"""
        manager = SyncManager("instance_A")
        manager.register_remote("instance_B")
        
        # 记录一些变更
        manager.local_sync.record_node_add("Alice")
        manager.local_sync.record_node_add("Bob")
        
        sync_data = manager.prepare_sync_for_remote("instance_B")
        assert len(sync_data["entries"]) == 2
    
    def test_receive_sync_from_remote(self):
        """测试接收远程同步数据"""
        manager_a = SyncManager("instance_A")
        manager_b = SyncManager("instance_B")
        
        manager_a.register_remote("instance_B")
        manager_b.register_remote("instance_A")
        
        # B 记录变更
        manager_b.local_sync.record_node_add("Bob")
        
        # A 从 B 同步
        sync_data = manager_b.prepare_sync_for_remote("instance_A")
        applied, conflicts = manager_a.receive_sync_from_remote("instance_B", sync_data)
        
        assert len(applied) == 1
        assert len(conflicts) == 0
        assert manager_a.local_sync.sync_log.entries[0].data["node_name"] == "Bob"
    
    def test_sync_callback(self):
        """测试同步回调"""
        manager = SyncManager("instance_A")
        manager.register_remote("instance_B")
        
        callback_called = False
        def on_sync(remote_id, applied, conflicts):
            nonlocal callback_called
            callback_called = True
        
        manager.register_sync_callback(on_sync)
        
        # 模拟接收同步数据
        sync_data = {
            "entries": [],
            "version_vector": {},
            "instance_id": "instance_B"
        }
        manager.receive_sync_from_remote("instance_B", sync_data)
        
        assert callback_called is True
    
    def test_get_stats(self):
        """测试获取统计信息"""
        manager = SyncManager("instance_A")
        manager.register_remote("instance_B")
        manager.local_sync.record_node_add("Alice")
        
        stats = manager.get_stats()
        assert stats["instance_id"] == "instance_A"
        assert stats["remote_count"] == 1
        assert stats["local_sync"]["log_size"] == 1
    
    def test_clear(self):
        """测试清空"""
        manager = SyncManager("instance_A")
        manager.register_remote("instance_B")
        manager.local_sync.record_node_add("Alice")
        
        manager.clear()
        assert len(manager.remote_versions) == 0
        assert len(manager.local_sync.sync_log.entries) == 0


class TestSyncIntegration:
    """测试同步集成场景"""
    
    def test_two_way_sync(self):
        """测试双向同步"""
        manager_a = SyncManager("instance_A")
        manager_b = SyncManager("instance_B")
        
        manager_a.register_remote("instance_B")
        manager_b.register_remote("instance_A")
        
        # A 添加 Alice
        manager_a.local_sync.record_node_add("Alice")
        
        # B 添加 Bob
        manager_b.local_sync.record_node_add("Bob")
        
        # A -> B 同步
        sync_data_a = manager_a.prepare_sync_for_remote("instance_B")
        applied_b, _ = manager_b.receive_sync_from_remote("instance_A", sync_data_a)
        
        # B -> A 同步
        sync_data_b = manager_b.prepare_sync_for_remote("instance_A")
        applied_a, _ = manager_a.receive_sync_from_remote("instance_B", sync_data_b)
        
        # 验证双方都有所有数据
        assert len(manager_a.local_sync.sync_log.entries) == 2
        assert len(manager_b.local_sync.sync_log.entries) == 2
    
    def test_incremental_sync(self):
        """测试增量同步"""
        manager_a = SyncManager("instance_A")
        manager_b = SyncManager("instance_B")
        
        manager_a.register_remote("instance_B")
        manager_b.register_remote("instance_A")
        
        # 第一轮：A 添加 Alice
        manager_a.local_sync.record_node_add("Alice")
        sync_data = manager_a.prepare_sync_for_remote("instance_B")
        manager_b.receive_sync_from_remote("instance_A", sync_data)
        
        # 第二轮：A 添加 Bob
        manager_a.local_sync.record_node_add("Bob")
        sync_data = manager_a.prepare_sync_for_remote("instance_B")
        applied, _ = manager_b.receive_sync_from_remote("instance_A", sync_data)
        
        # 只应该收到 Bob
        assert len(applied) == 1
        assert applied[0].data["node_name"] == "Bob"
    
    def test_concurrent_update_conflict(self):
        """测试并发更新冲突"""
        manager_a = SyncManager("instance_A")
        manager_b = SyncManager("instance_B")
        
        manager_a.register_remote("instance_B")
        manager_b.register_remote("instance_A")
        
        # 双方同时更新同一个节点
        manager_a.local_sync.record_node_add("Alice", {"type": "person", "version": "A"})
        manager_b.local_sync.record_node_add("Alice", {"type": "person", "version": "B"})
        
        # 双向同步
        sync_data_a = manager_a.prepare_sync_for_remote("instance_B")
        sync_data_b = manager_b.prepare_sync_for_remote("instance_A")
        
        _, conflicts_a = manager_a.receive_sync_from_remote("instance_B", sync_data_b)
        _, conflicts_b = manager_b.receive_sync_from_remote("instance_A", sync_data_a)
        
        # 至少一方应该检测到冲突
        total_conflicts = len(conflicts_a) + len(conflicts_b)
        assert total_conflicts >= 1

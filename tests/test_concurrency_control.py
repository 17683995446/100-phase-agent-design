"""
并发控制和冲突解决模块测试

测试乐观锁、冲突解决策略和并发资源管理器。
遵循"图难于其易，为大于其细"原则，从简单可验证的测试开始。
"""

import pytest
import time
import threading
from core import (
    LockType, ConflictResolutionStrategy,
    OptimisticLock, LockManager,
    Conflict, ConflictResolver,
    ConcurrentResourceManager
)


class TestOptimisticLock:
    """测试乐观锁"""
    
    def test_creation(self):
        """测试创建"""
        lock = OptimisticLock("resource_1")
        assert lock.resource_id == "resource_1"
        assert lock.version == 0
        assert lock.owner is None
    
    def test_acquire_read(self):
        """测试获取读锁"""
        lock = OptimisticLock("resource_1")
        assert lock.acquire_read() is True
    
    def test_acquire_write_success(self):
        """测试成功获取写锁"""
        lock = OptimisticLock("resource_1")
        success, version = lock.acquire_write(0, "owner_1")
        
        assert success is True
        assert version == 1
        assert lock.owner == "owner_1"
    
    def test_acquire_write_version_mismatch(self):
        """测试版本不匹配时获取写锁失败"""
        lock = OptimisticLock("resource_1")
        lock.version = 5
        
        success, version = lock.acquire_write(0, "owner_1")
        
        assert success is False
        assert version == 5
    
    def test_release(self):
        """测试释放锁"""
        lock = OptimisticLock("resource_1")
        lock.acquire_write(0, "owner_1")
        
        lock.release()
        assert lock.owner is None
    
    def test_is_locked(self):
        """测试锁定状态检查"""
        lock = OptimisticLock("resource_1")
        assert lock.is_locked() is False
        
        lock.acquire_write(0, "owner_1")
        assert lock.is_locked() is True
        
        lock.release()
        assert lock.is_locked() is False


class TestLockManager:
    """测试锁管理器"""
    
    def test_creation(self):
        """测试创建"""
        manager = LockManager()
        assert len(manager.get_all_locks()) == 0
    
    def test_get_or_create_lock(self):
        """测试获取或创建锁"""
        manager = LockManager()
        lock = manager.get_or_create_lock("resource_1")
        
        assert lock.resource_id == "resource_1"
        assert lock.version == 0
    
    def test_acquire_read_lock(self):
        """测试获取读锁"""
        manager = LockManager()
        assert manager.acquire_read_lock("resource_1") is True
    
    def test_acquire_write_lock(self):
        """测试获取写锁"""
        manager = LockManager()
        success, version = manager.acquire_write_lock("resource_1", 0, "owner_1")
        
        assert success is True
        assert version == 1
    
    def test_get_version(self):
        """测试获取版本号"""
        manager = LockManager()
        assert manager.get_version("resource_1") == 0
        
        manager.acquire_write_lock("resource_1", 0, "owner_1")
        assert manager.get_version("resource_1") == 1
    
    def test_get_lock_info(self):
        """测试获取锁信息"""
        manager = LockManager()
        manager.acquire_write_lock("resource_1", 0, "owner_1")
        
        info = manager.get_lock_info("resource_1")
        assert info is not None
        assert info["resource_id"] == "resource_1"
        assert info["version"] == 1
        assert info["owner"] == "owner_1"
    
    def test_release_lock(self):
        """测试释放锁"""
        manager = LockManager()
        manager.acquire_write_lock("resource_1", 0, "owner_1")
        
        manager.release_lock("resource_1")
        info = manager.get_lock_info("resource_1")
        assert info["owner"] is None
    
    def test_clear(self):
        """测试清空"""
        manager = LockManager()
        manager.acquire_write_lock("resource_1", 0, "owner_1")
        
        manager.clear()
        assert len(manager.get_all_locks()) == 0


class TestConflict:
    """测试冲突记录"""
    
    def test_creation(self):
        """测试创建"""
        conflict = Conflict(
            resource_id="resource_1",
            local_version=1,
            remote_version=2,
            local_data="local",
            remote_data="remote",
            local_timestamp=time.time(),
            remote_timestamp=time.time()
        )
        
        assert conflict.resource_id == "resource_1"
        assert conflict.resolved is False
    
    def test_to_dict(self):
        """测试转换为字典"""
        conflict = Conflict(
            resource_id="resource_1",
            local_version=1,
            remote_version=2,
            local_data="local",
            remote_data="remote",
            local_timestamp=100.0,
            remote_timestamp=200.0,
            resolved=True,
            resolution="lww"
        )
        
        data = conflict.to_dict()
        assert data["resource_id"] == "resource_1"
        assert data["resolved"] is True
        assert data["resolution"] == "lww"


class TestConflictResolver:
    """测试冲突解决器"""
    
    def test_last_write_wins_remote(self):
        """测试最后写入者胜出 - 远程更新"""
        resolver = ConflictResolver(ConflictResolutionStrategy.LAST_WRITE_WINS)
        
        conflict = Conflict(
            resource_id="resource_1",
            local_version=1,
            remote_version=2,
            local_data="local",
            remote_data="remote",
            local_timestamp=100.0,
            remote_timestamp=200.0
        )
        
        result, strategy = resolver.resolve(conflict)
        assert result == "remote"
        assert "last_write_wins_remote" in strategy
        assert conflict.resolved is True
    
    def test_last_write_wins_local(self):
        """测试最后写入者胜出 - 本地更新"""
        resolver = ConflictResolver(ConflictResolutionStrategy.LAST_WRITE_WINS)
        
        conflict = Conflict(
            resource_id="resource_1",
            local_version=1,
            remote_version=2,
            local_data="local",
            remote_data="remote",
            local_timestamp=200.0,
            remote_timestamp=100.0
        )
        
        result, strategy = resolver.resolve(conflict)
        assert result == "local"
        assert "last_write_wins_local" in strategy
    
    def test_first_write_wins(self):
        """测试先写入者胜出"""
        resolver = ConflictResolver(ConflictResolutionStrategy.FIRST_WRITE_WINS)
        
        conflict = Conflict(
            resource_id="resource_1",
            local_version=1,
            remote_version=2,
            local_data="local",
            remote_data="remote",
            local_timestamp=100.0,
            remote_timestamp=200.0
        )
        
        result, strategy = resolver.resolve(conflict)
        assert result == "local"
        assert "first_write_wins_local" in strategy
    
    def test_custom_resolver(self):
        """测试自定义解决器"""
        resolver = ConflictResolver(ConflictResolutionStrategy.CUSTOM)
        
        def custom_resolve(conflict):
            return "merged", "custom_strategy"
        
        resolver.set_custom_resolver(custom_resolve)
        
        conflict = Conflict(
            resource_id="resource_1",
            local_version=1,
            remote_version=2,
            local_data="local",
            remote_data="remote",
            local_timestamp=100.0,
            remote_timestamp=200.0
        )
        
        result, strategy = resolver.resolve(conflict)
        assert result == "merged"
        assert strategy == "custom_strategy"
    
    def test_record_conflict(self):
        """测试记录冲突"""
        resolver = ConflictResolver()
        
        conflict = Conflict(
            resource_id="resource_1",
            local_version=1,
            remote_version=2,
            local_data="local",
            remote_data="remote",
            local_timestamp=100.0,
            remote_timestamp=200.0
        )
        
        resolver.record_conflict(conflict)
        assert len(resolver.get_conflicts()) == 1
    
    def test_get_conflict_stats(self):
        """测试获取冲突统计"""
        resolver = ConflictResolver()
        
        conflict1 = Conflict(
            resource_id="resource_1",
            local_version=1,
            remote_version=2,
            local_data="local",
            remote_data="remote",
            local_timestamp=100.0,
            remote_timestamp=200.0,
            resolved=True
        )
        
        conflict2 = Conflict(
            resource_id="resource_2",
            local_version=1,
            remote_version=2,
            local_data="local",
            remote_data="remote",
            local_timestamp=100.0,
            remote_timestamp=200.0,
            resolved=False
        )
        
        resolver.record_conflict(conflict1)
        resolver.record_conflict(conflict2)
        
        stats = resolver.get_conflict_stats()
        assert stats["total"] == 2
        assert stats["resolved"] == 1
        assert stats["unresolved"] == 1


class TestConcurrentResourceManager:
    """测试并发资源管理器"""
    
    def test_creation(self):
        """测试创建"""
        manager = ConcurrentResourceManager()
        assert manager.get_stats()["resources"] == 0
    
    def test_read_resource(self):
        """测试读取资源"""
        manager = ConcurrentResourceManager()
        
        # 读取不存在的资源
        success, data, version = manager.read_resource("resource_1")
        assert success is True
        assert data is None
        assert version == 0
    
    def test_write_resource(self):
        """测试写入资源"""
        manager = ConcurrentResourceManager()
        
        success, version, error = manager.write_resource(
            "resource_1", {"key": "value"}, 0, "owner_1"
        )
        
        assert success is True
        assert version == 1
        assert error is None
    
    def test_write_resource_version_conflict(self):
        """测试写入时版本冲突"""
        manager = ConcurrentResourceManager()
        
        # 第一次写入
        manager.write_resource("resource_1", {"key": "value1"}, 0, "owner_1")
        
        # 使用旧版本号写入
        success, version, error = manager.write_resource(
            "resource_1", {"key": "value2"}, 0, "owner_2"
        )
        
        assert success is False
        assert error == "version_conflict"
    
    def test_compare_and_swap_success(self):
        """测试比较并交换成功"""
        manager = ConcurrentResourceManager()
        
        # 初始写入
        manager.write_resource("resource_1", "old_value", 0, "owner_1")
        
        # CAS 操作
        success, data, version = manager.compare_and_swap(
            "resource_1", "old_value", "new_value", "owner_2"
        )
        
        assert success is True
        assert data == "new_value"
        assert version == 2
    
    def test_compare_and_swap_failure(self):
        """测试比较并交换失败"""
        manager = ConcurrentResourceManager()
        
        # 初始写入
        manager.write_resource("resource_1", "old_value", 0, "owner_1")
        
        # CAS 操作（期望值不匹配）
        success, data, version = manager.compare_and_swap(
            "resource_1", "wrong_value", "new_value", "owner_2"
        )
        
        assert success is False
        assert data == "old_value"
    
    def test_resolve_conflict(self):
        """测试解决冲突"""
        manager = ConcurrentResourceManager()
        
        # 设置本地数据
        manager.write_resource("resource_1", "local_data", 0, "owner_1")
        
        # 解决冲突
        result, strategy = manager.resolve_conflict(
            "resource_1",
            local_data="local_data",
            remote_data="remote_data",
            local_version=1,
            remote_version=2,
            local_timestamp=100.0,
            remote_timestamp=200.0
        )
        
        assert result == "remote_data"
        assert "last_write_wins" in strategy
    
    def test_delete_resource(self):
        """测试删除资源"""
        manager = ConcurrentResourceManager()
        manager.write_resource("resource_1", "value", 0, "owner_1")
        
        assert manager.delete_resource("resource_1") is True
        assert manager.delete_resource("resource_1") is False
    
    def test_get_stats(self):
        """测试获取统计"""
        manager = ConcurrentResourceManager()
        manager.write_resource("resource_1", "value1", 0, "owner_1")
        manager.write_resource("resource_2", "value2", 0, "owner_1")
        
        stats = manager.get_stats()
        assert stats["resources"] == 2
        assert stats["locks"] == 2
    
    def test_clear(self):
        """测试清空"""
        manager = ConcurrentResourceManager()
        manager.write_resource("resource_1", "value", 0, "owner_1")
        
        manager.clear()
        assert manager.get_stats()["resources"] == 0


class TestConcurrencyThreadSafety:
    """测试线程安全性"""
    
    def test_concurrent_reads(self):
        """测试并发读取"""
        manager = ConcurrentResourceManager()
        manager.write_resource("resource_1", "value", 0, "owner_1")
        
        results = []
        def read_resource():
            success, data, version = manager.read_resource("resource_1")
            results.append((success, data, version))
        
        threads = [threading.Thread(target=read_resource) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        assert len(results) == 10
        assert all(r[0] for r in results)
    
    def test_concurrent_writes(self):
        """测试并发写入 - 验证版本冲突检测"""
        manager = ConcurrentResourceManager()
        
        # 先初始化资源（版本变为 1）
        manager.write_resource("counter", 0, 0, "owner_init")
        
        successes = []
        errors = []
        def write_resource():
            # 先读取当前版本
            _, _, version = manager.read_resource("counter")
            # 模拟一些处理时间，增加竞争概率
            time.sleep(0.01)
            success, new_version, error = manager.write_resource(
                "counter", version + 1, version, "owner"
            )
            successes.append(success)
            if error:
                errors.append(error)
        
        threads = [threading.Thread(target=write_resource) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        # 验证至少有一次成功写入
        assert sum(successes) >= 1
        # 验证最终版本号 = 初始版本(1) + 成功写入次数
        _, _, final_version = manager.read_resource("counter")
        assert final_version == 1 + sum(successes)

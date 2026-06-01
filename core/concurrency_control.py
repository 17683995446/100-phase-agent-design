"""
并发控制和冲突解决模块

提供分布式环境下的乐观锁机制、冲突自动解决策略。
遵循"图难于其易，为大于其细"原则，从简单可验证的实现开始。
"""

import time
import threading
from typing import Dict, List, Optional, Set, Tuple, Callable, Any
from dataclasses import dataclass, field
from enum import Enum


class LockType(Enum):
    """锁类型"""
    READ = "read"
    WRITE = "write"


class ConflictResolutionStrategy(Enum):
    """冲突解决策略"""
    LAST_WRITE_WINS = "last_write_wins"  # 最后写入者胜出
    FIRST_WRITE_WINS = "first_write_wins"  # 先写入者胜出
    TIMESTAMP_PRIORITY = "timestamp_priority"  # 时间戳优先
    CUSTOM = "custom"  # 自定义策略


@dataclass
class OptimisticLock:
    """
    乐观锁
    
    基于版本号的乐观锁机制，适用于读多写少的场景。
    """
    resource_id: str
    version: int = 0
    last_modified: float = field(default_factory=time.time)
    owner: Optional[str] = None
    
    def acquire_read(self) -> bool:
        """获取读锁（乐观锁允许多个读）"""
        return True  # 乐观锁读操作不需要实际加锁
    
    def acquire_write(self, expected_version: int, owner: str) -> Tuple[bool, int]:
        """
        获取写锁
        
        Args:
            expected_version: 期望的版本号
            owner: 锁持有者
            
        Returns:
            (是否成功, 当前版本号)
        """
        if self.version == expected_version:
            self.version += 1
            self.last_modified = time.time()
            self.owner = owner
            return True, self.version
        return False, self.version
    
    def release(self):
        """释放锁"""
        self.owner = None
    
    def is_locked(self) -> bool:
        """检查是否被锁定"""
        return self.owner is not None


class LockManager:
    """
    锁管理器
    
    管理多个资源的乐观锁。
    """
    
    def __init__(self):
        self._locks: Dict[str, OptimisticLock] = {}
        self._lock = threading.Lock()
    
    def get_or_create_lock(self, resource_id: str) -> OptimisticLock:
        """获取或创建锁"""
        with self._lock:
            if resource_id not in self._locks:
                self._locks[resource_id] = OptimisticLock(resource_id)
            return self._locks[resource_id]
    
    def acquire_read_lock(self, resource_id: str) -> bool:
        """获取读锁"""
        lock = self.get_or_create_lock(resource_id)
        return lock.acquire_read()
    
    def acquire_write_lock(self, resource_id: str, expected_version: int,
                          owner: str) -> Tuple[bool, int]:
        """获取写锁"""
        lock = self.get_or_create_lock(resource_id)
        return lock.acquire_write(expected_version, owner)
    
    def release_lock(self, resource_id: str):
        """释放锁"""
        if resource_id in self._locks:
            self._locks[resource_id].release()
    
    def get_version(self, resource_id: str) -> int:
        """获取资源版本号"""
        lock = self.get_or_create_lock(resource_id)
        return lock.version
    
    def get_lock_info(self, resource_id: str) -> Optional[Dict[str, Any]]:
        """获取锁信息"""
        if resource_id not in self._locks:
            return None
        lock = self._locks[resource_id]
        return {
            "resource_id": lock.resource_id,
            "version": lock.version,
            "last_modified": lock.last_modified,
            "owner": lock.owner,
            "is_locked": lock.is_locked()
        }
    
    def get_all_locks(self) -> Dict[str, Dict[str, Any]]:
        """获取所有锁信息"""
        return {rid: self.get_lock_info(rid) for rid in self._locks}
    
    def clear(self):
        """清空所有锁"""
        with self._lock:
            self._locks.clear()


@dataclass
class Conflict:
    """
    冲突记录
    """
    resource_id: str
    local_version: int
    remote_version: int
    local_data: Any
    remote_data: Any
    local_timestamp: float
    remote_timestamp: float
    resolved: bool = False
    resolution: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "resource_id": self.resource_id,
            "local_version": self.local_version,
            "remote_version": self.remote_version,
            "local_data": self.local_data,
            "remote_data": self.remote_data,
            "local_timestamp": self.local_timestamp,
            "remote_timestamp": self.remote_timestamp,
            "resolved": self.resolved,
            "resolution": self.resolution
        }


class ConflictResolver:
    """
    冲突解决器
    
    提供多种冲突解决策略。
    """
    
    def __init__(self, strategy: ConflictResolutionStrategy = ConflictResolutionStrategy.LAST_WRITE_WINS):
        self.strategy = strategy
        self._custom_resolver: Optional[Callable] = None
        self._conflicts: List[Conflict] = []
    
    def set_custom_resolver(self, resolver: Callable):
        """设置自定义解决器"""
        self._custom_resolver = resolver
    
    def resolve(self, conflict: Conflict) -> Tuple[Any, str]:
        """
        解决冲突
        
        Args:
            conflict: 冲突记录
            
        Returns:
            (解决后的数据, 使用的策略)
        """
        if self.strategy == ConflictResolutionStrategy.LAST_WRITE_WINS:
            return self._last_write_wins(conflict)
        elif self.strategy == ConflictResolutionStrategy.FIRST_WRITE_WINS:
            return self._first_write_wins(conflict)
        elif self.strategy == ConflictResolutionStrategy.TIMESTAMP_PRIORITY:
            return self._timestamp_priority(conflict)
        elif self.strategy == ConflictResolutionStrategy.CUSTOM and self._custom_resolver:
            return self._custom_resolver(conflict)
        else:
            return self._last_write_wins(conflict)
    
    def _last_write_wins(self, conflict: Conflict) -> Tuple[Any, str]:
        """最后写入者胜出"""
        if conflict.remote_timestamp >= conflict.local_timestamp:
            conflict.resolved = True
            conflict.resolution = "last_write_wins_remote"
            return conflict.remote_data, "last_write_wins_remote"
        else:
            conflict.resolved = True
            conflict.resolution = "last_write_wins_local"
            return conflict.local_data, "last_write_wins_local"
    
    def _first_write_wins(self, conflict: Conflict) -> Tuple[Any, str]:
        """先写入者胜出"""
        if conflict.local_timestamp <= conflict.remote_timestamp:
            conflict.resolved = True
            conflict.resolution = "first_write_wins_local"
            return conflict.local_data, "first_write_wins_local"
        else:
            conflict.resolved = True
            conflict.resolution = "first_write_wins_remote"
            return conflict.remote_data, "first_write_wins_remote"
    
    def _timestamp_priority(self, conflict: Conflict) -> Tuple[Any, str]:
        """时间戳优先（与 LWW 相同但语义更清晰）"""
        return self._last_write_wins(conflict)
    
    def record_conflict(self, conflict: Conflict):
        """记录冲突"""
        self._conflicts.append(conflict)
    
    def get_conflicts(self, resolved_only: Optional[bool] = None) -> List[Conflict]:
        """
        获取冲突记录
        
        Args:
            resolved_only: 如果为 True 只返回已解决的，False 只返回未解决的，None 返回所有
        """
        if resolved_only is None:
            return self._conflicts.copy()
        return [c for c in self._conflicts if c.resolved == resolved_only]
    
    def get_conflict_stats(self) -> Dict[str, int]:
        """获取冲突统计"""
        total = len(self._conflicts)
        resolved = sum(1 for c in self._conflicts if c.resolved)
        return {
            "total": total,
            "resolved": resolved,
            "unresolved": total - resolved
        }
    
    def clear_conflicts(self):
        """清空冲突记录"""
        self._conflicts.clear()


class ConcurrentResourceManager:
    """
    并发资源管理器
    
    结合乐观锁和冲突解决，提供完整的并发控制。
    """
    
    def __init__(self, strategy: ConflictResolutionStrategy = ConflictResolutionStrategy.LAST_WRITE_WINS):
        self.lock_manager = LockManager()
        self.conflict_resolver = ConflictResolver(strategy)
        self._resources: Dict[str, Dict[str, Any]] = {}
        self._resource_lock = threading.Lock()
    
    def read_resource(self, resource_id: str) -> Tuple[bool, Optional[Any], int]:
        """
        读取资源
        
        Returns:
            (是否成功, 数据, 版本号)
        """
        if not self.lock_manager.acquire_read_lock(resource_id):
            return False, None, -1
        
        with self._resource_lock:
            data = self._resources.get(resource_id)
            version = self.lock_manager.get_version(resource_id)
            return True, data, version
    
    def write_resource(self, resource_id: str, data: Any, expected_version: int,
                      owner: str) -> Tuple[bool, int, Optional[str]]:
        """
        写入资源
        
        Returns:
            (是否成功, 新版本号, 错误信息)
        """
        success, new_version = self.lock_manager.acquire_write_lock(
            resource_id, expected_version, owner
        )
        
        if not success:
            return False, expected_version, "version_conflict"
        
        with self._resource_lock:
            self._resources[resource_id] = data
            return True, new_version, None
    
    def compare_and_swap(self, resource_id: str, expected_data: Any, new_data: Any,
                        owner: str) -> Tuple[bool, Any, int]:
        """
        比较并交换
        
        Returns:
            (是否成功, 当前数据, 版本号)
        """
        success, current_data, version = self.read_resource(resource_id)
        
        if not success:
            return False, None, -1
        
        if current_data != expected_data:
            return False, current_data, version
        
        success, new_version, error = self.write_resource(
            resource_id, new_data, version, owner
        )
        
        return success, new_data if success else current_data, new_version if success else version
    
    def resolve_conflict(self, resource_id: str, local_data: Any, remote_data: Any,
                        local_version: int, remote_version: int,
                        local_timestamp: float, remote_timestamp: float) -> Tuple[Any, str]:
        """
        解决资源冲突
        
        Returns:
            (解决后的数据, 策略)
        """
        conflict = Conflict(
            resource_id=resource_id,
            local_version=local_version,
            remote_version=remote_version,
            local_data=local_data,
            remote_data=remote_data,
            local_timestamp=local_timestamp,
            remote_timestamp=remote_timestamp
        )
        
        resolved_data, strategy = self.conflict_resolver.resolve(conflict)
        self.conflict_resolver.record_conflict(conflict)
        
        # 更新资源
        with self._resource_lock:
            self._resources[resource_id] = resolved_data
        
        return resolved_data, strategy
    
    def get_resource_info(self, resource_id: str) -> Optional[Dict[str, Any]]:
        """获取资源信息"""
        if resource_id not in self._resources:
            return None
        
        lock_info = self.lock_manager.get_lock_info(resource_id)
        return {
            "resource_id": resource_id,
            "data": self._resources[resource_id],
            "lock_info": lock_info
        }
    
    def get_all_resources(self) -> Dict[str, Any]:
        """获取所有资源"""
        return self._resources.copy()
    
    def delete_resource(self, resource_id: str) -> bool:
        """删除资源"""
        with self._resource_lock:
            if resource_id in self._resources:
                del self._resources[resource_id]
                self.lock_manager.release_lock(resource_id)
                return True
            return False
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "resources": len(self._resources),
            "locks": len(self.lock_manager.get_all_locks()),
            "conflicts": self.conflict_resolver.get_conflict_stats()
        }
    
    def clear(self):
        """清空所有资源"""
        with self._resource_lock:
            self._resources.clear()
            self.lock_manager.clear()
            self.conflict_resolver.clear_conflicts()

"""
跨实例知识同步模块

提供多实例间的知识同步机制，基于版本向量实现增量同步和冲突检测。
遵循"图难于其易，为大于其细"原则，从简单可验证的同步实现开始。
"""

import time
import json
from typing import Dict, List, Optional, Set, Tuple, Any
from dataclasses import dataclass, field, asdict
from .node import Node
from .edge import Edge


@dataclass
class VersionVector:
    """
    版本向量，用于追踪分布式实例的更新历史
    
    每个实例维护一个单调递增的计数器，
    通过比较版本向量可以判断数据的新旧关系和冲突。
    """
    vector: Dict[str, int] = field(default_factory=dict)
    
    def increment(self, instance_id: str) -> "VersionVector":
        """增加指定实例的计数器"""
        new_vector = VersionVector(self.vector.copy())
        new_vector.vector[instance_id] = new_vector.vector.get(instance_id, 0) + 1
        return new_vector
    
    def merge(self, other: "VersionVector") -> "VersionVector":
        """合并两个版本向量，取每个实例的最大值"""
        merged = {}
        all_instances = set(self.vector.keys()) | set(other.vector.keys())
        for instance_id in all_instances:
            merged[instance_id] = max(
                self.vector.get(instance_id, 0),
                other.vector.get(instance_id, 0)
            )
        return VersionVector(merged)
    
    def compare(self, other: "VersionVector") -> Optional[str]:
        """
        比较两个版本向量
        
        Returns:
            "before": self 在 other 之前（other 更新）
            "after": self 在 other 之后（self 更新）
            "concurrent": 并发冲突
            "equal": 相等
        """
        dominates = False
        dominated = False
        
        all_instances = set(self.vector.keys()) | set(other.vector.keys())
        
        for instance_id in all_instances:
            self_count = self.vector.get(instance_id, 0)
            other_count = other.vector.get(instance_id, 0)
            
            if self_count > other_count:
                dominates = True
            elif other_count > self_count:
                dominated = True
        
        if dominates and not dominated:
            return "after"
        elif dominated and not dominates:
            return "before"
        elif not dominates and not dominated:
            return "equal"
        else:
            return "concurrent"
    
    def to_dict(self) -> Dict[str, int]:
        """转换为字典"""
        return self.vector.copy()
    
    @classmethod
    def from_dict(cls, data: Dict[str, int]) -> "VersionVector":
        """从字典创建"""
        return cls(data.copy())
    
    def __repr__(self) -> str:
        return f"VersionVector({self.vector})"


@dataclass
class SyncEntry:
    """
    同步条目，表示一次知识变更
    """
    entry_id: str
    entry_type: str  # "node_add", "node_update", "node_delete", "edge_add", "edge_delete"
    data: Dict[str, Any]
    version_vector: VersionVector
    timestamp: float
    instance_id: str
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "entry_id": self.entry_id,
            "entry_type": self.entry_type,
            "data": self.data,
            "version_vector": self.version_vector.to_dict(),
            "timestamp": self.timestamp,
            "instance_id": self.instance_id
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SyncEntry":
        """从字典创建"""
        return cls(
            entry_id=data["entry_id"],
            entry_type=data["entry_type"],
            data=data["data"],
            version_vector=VersionVector.from_dict(data["version_vector"]),
            timestamp=data["timestamp"],
            instance_id=data["instance_id"]
        )


class SyncLog:
    """
    同步日志，记录所有变更历史
    """
    
    def __init__(self, max_size: int = 10000):
        self.entries: List[SyncEntry] = []
        self.max_size = max_size
        self._entry_ids: Set[str] = set()
    
    def add_entry(self, entry: SyncEntry) -> bool:
        """添加同步条目"""
        if entry.entry_id in self._entry_ids:
            return False
        
        self.entries.append(entry)
        self._entry_ids.add(entry.entry_id)
        
        # 限制日志大小
        if len(self.entries) > self.max_size:
            removed = self.entries.pop(0)
            self._entry_ids.discard(removed.entry_id)
        
        return True
    
    def get_entries_since(self, version_vector: VersionVector) -> List[SyncEntry]:
        """
        获取指定版本向量之后的所有条目
        """
        result = []
        for entry in self.entries:
            comparison = entry.version_vector.compare(version_vector)
            if comparison in ("after", "concurrent"):
                result.append(entry)
        return result
    
    def get_all_entries(self) -> List[SyncEntry]:
        """获取所有条目"""
        return self.entries.copy()
    
    def get_latest_version_vector(self) -> VersionVector:
        """获取最新的版本向量"""
        if not self.entries:
            return VersionVector()
        
        latest = VersionVector()
        for entry in self.entries:
            latest = latest.merge(entry.version_vector)
        return latest
    
    def clear(self):
        """清空日志"""
        self.entries.clear()
        self._entry_ids.clear()
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "entries": [entry.to_dict() for entry in self.entries],
            "max_size": self.max_size
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SyncLog":
        """从字典创建"""
        log = cls(max_size=data.get("max_size", 10000))
        for entry_data in data.get("entries", []):
            log.add_entry(SyncEntry.from_dict(entry_data))
        return log


class KnowledgeSync:
    """
    知识同步器，管理实例间的知识同步
    """
    
    def __init__(self, instance_id: str):
        """
        初始化知识同步器
        
        Args:
            instance_id: 当前实例的唯一标识
        """
        self.instance_id = instance_id
        self.sync_log = SyncLog()
        self.local_version = VersionVector()
        self._entry_counter = 0
    
    def _generate_entry_id(self) -> str:
        """生成唯一的条目 ID"""
        self._entry_counter += 1
        return f"{self.instance_id}_{int(time.time() * 1000)}_{self._entry_counter}"
    
    def record_node_add(self, node_name: str, attributes: Optional[dict] = None):
        """记录节点添加"""
        self.local_version = self.local_version.increment(self.instance_id)
        entry = SyncEntry(
            entry_id=self._generate_entry_id(),
            entry_type="node_add",
            data={"node_name": node_name, "attributes": attributes or {}},
            version_vector=VersionVector(self.local_version.vector.copy()),
            timestamp=time.time(),
            instance_id=self.instance_id
        )
        self.sync_log.add_entry(entry)
    
    def record_node_update(self, node_name: str, attributes: dict):
        """记录节点更新"""
        self.local_version = self.local_version.increment(self.instance_id)
        entry = SyncEntry(
            entry_id=self._generate_entry_id(),
            entry_type="node_update",
            data={"node_name": node_name, "attributes": attributes},
            version_vector=VersionVector(self.local_version.vector.copy()),
            timestamp=time.time(),
            instance_id=self.instance_id
        )
        self.sync_log.add_entry(entry)
    
    def record_node_delete(self, node_name: str):
        """记录节点删除"""
        self.local_version = self.local_version.increment(self.instance_id)
        entry = SyncEntry(
            entry_id=self._generate_entry_id(),
            entry_type="node_delete",
            data={"node_name": node_name},
            version_vector=VersionVector(self.local_version.vector.copy()),
            timestamp=time.time(),
            instance_id=self.instance_id
        )
        self.sync_log.add_entry(entry)
    
    def record_edge_add(self, source: str, target: str, relation: str, weight: float):
        """记录边添加"""
        self.local_version = self.local_version.increment(self.instance_id)
        entry = SyncEntry(
            entry_id=self._generate_entry_id(),
            entry_type="edge_add",
            data={
                "source": source,
                "target": target,
                "relation": relation,
                "weight": weight
            },
            version_vector=VersionVector(self.local_version.vector.copy()),
            timestamp=time.time(),
            instance_id=self.instance_id
        )
        self.sync_log.add_entry(entry)
    
    def record_edge_delete(self, source: str, target: str, relation: str):
        """记录边删除"""
        self.local_version = self.local_version.increment(self.instance_id)
        entry = SyncEntry(
            entry_id=self._generate_entry_id(),
            entry_type="edge_delete",
            data={
                "source": source,
                "target": target,
                "relation": relation
            },
            version_vector=VersionVector(self.local_version.vector.copy()),
            timestamp=time.time(),
            instance_id=self.instance_id
        )
        self.sync_log.add_entry(entry)
    
    def get_sync_data(self, remote_version: Optional[VersionVector] = None) -> Dict[str, Any]:
        """
        获取需要同步的数据
        
        Args:
            remote_version: 远程实例的版本向量，如果为 None 则返回所有数据
            
        Returns:
            包含同步条目和当前版本向量的字典
        """
        if remote_version is None:
            entries = self.sync_log.get_all_entries()
        else:
            entries = self.sync_log.get_entries_since(remote_version)
        
        return {
            "entries": [entry.to_dict() for entry in entries],
            "version_vector": self.local_version.to_dict(),
            "instance_id": self.instance_id
        }
    
    def apply_sync_data(self, sync_data: Dict[str, Any]) -> Tuple[List[SyncEntry], List[SyncEntry]]:
        """
        应用同步数据
        
        Args:
            sync_data: 从远程实例获取的同步数据
            
        Returns:
            (applied_entries, conflict_entries): 成功应用的条目和冲突的条目
        """
        applied = []
        conflicts = []
        
        for entry_data in sync_data.get("entries", []):
            entry = SyncEntry.from_dict(entry_data)
            
            # 检查是否已存在
            if entry.entry_id in self.sync_log._entry_ids:
                continue
            
            # 检查版本向量，检测冲突
            comparison = entry.version_vector.compare(self.local_version)
            
            if comparison == "before":
                # 远程数据较旧，忽略
                continue
            elif comparison == "concurrent":
                # 检测到并发冲突
                conflicts.append(entry)
            
            # 添加条目到同步日志
            self.sync_log.add_entry(entry)
            applied.append(entry)
            
            # 更新本地版本向量
            self.local_version = self.local_version.merge(entry.version_vector)
        
        return applied, conflicts
    
    def resolve_conflict(self, entry: SyncEntry, resolution: str = "latest") -> bool:
        """
        解决同步冲突
        
        Args:
            entry: 冲突的条目
            resolution: 解决策略，"latest" 表示使用时间戳最新的
            
        Returns:
            是否成功解决
        """
        # 简单策略：使用最新的条目（基于时间戳）
        if resolution == "latest":
            # 查找同一节点的所有条目
            related_entries = [
                e for e in self.sync_log.entries
                if e.entry_type == entry.entry_type and
                e.data.get("node_name") == entry.data.get("node_name")
            ]
            
            if not related_entries:
                return False
            
            # 选择时间戳最新的
            latest = max(related_entries, key=lambda e: e.timestamp)
            
            # 如果当前条目不是最新的，需要更新
            if latest.entry_id != entry.entry_id:
                # 在实际应用中，这里需要更新知识图谱
                # 为简化，我们只记录冲突已解决
                pass
            
            return True
        
        return False
    
    def get_stats(self) -> Dict[str, Any]:
        """获取同步统计信息"""
        return {
            "instance_id": self.instance_id,
            "local_version": self.local_version.to_dict(),
            "log_size": len(self.sync_log.entries),
            "max_log_size": self.sync_log.max_size
        }
    
    def clear(self):
        """清空同步状态"""
        self.sync_log.clear()
        self.local_version = VersionVector()
        self._entry_counter = 0
    
    def __repr__(self) -> str:
        return f"KnowledgeSync(instance={self.instance_id}, version={self.local_version}, entries={len(self.sync_log.entries)})"


class SyncManager:
    """
    同步管理器，管理多个实例的同步关系
    """
    
    def __init__(self, instance_id: str):
        """
        初始化同步管理器
        
        Args:
            instance_id: 当前实例的唯一标识
        """
        self.instance_id = instance_id
        self.local_sync = KnowledgeSync(instance_id)
        self.remote_versions: Dict[str, VersionVector] = {}
        self._sync_callbacks: List[Callable] = []
    
    def register_remote(self, remote_id: str, initial_version: Optional[VersionVector] = None):
        """
        注册远程实例
        
        Args:
            remote_id: 远程实例标识
            initial_version: 远程实例的初始版本向量
        """
        if initial_version is None:
            initial_version = VersionVector()
        self.remote_versions[remote_id] = initial_version
    
    def unregister_remote(self, remote_id: str):
        """注销远程实例"""
        self.remote_versions.pop(remote_id, None)
    
    def prepare_sync_for_remote(self, remote_id: str) -> Dict[str, Any]:
        """
        准备发送给远程实例的同步数据
        
        Args:
            remote_id: 远程实例标识
            
        Returns:
            同步数据字典
        """
        remote_version = self.remote_versions.get(remote_id)
        return self.local_sync.get_sync_data(remote_version)
    
    def receive_sync_from_remote(self, remote_id: str, sync_data: Dict[str, Any]) -> Tuple[List[SyncEntry], List[SyncEntry]]:
        """
        接收并应用来自远程实例的同步数据
        
        Args:
            remote_id: 远程实例标识
            sync_data: 同步数据
            
        Returns:
            (applied_entries, conflict_entries)
        """
        applied, conflicts = self.local_sync.apply_sync_data(sync_data)
        
        # 更新远程实例的版本向量
        remote_version_data = sync_data.get("version_vector", {})
        self.remote_versions[remote_id] = VersionVector.from_dict(remote_version_data)
        
        # 触发同步回调
        for callback in self._sync_callbacks:
            try:
                callback(remote_id, applied, conflicts)
            except Exception:
                pass
        
        return applied, conflicts
    
    def register_sync_callback(self, callback: Callable):
        """注册同步完成回调"""
        self._sync_callbacks.append(callback)
    
    def unregister_sync_callback(self, callback: Callable):
        """注销同步完成回调"""
        if callback in self._sync_callbacks:
            self._sync_callbacks.remove(callback)
    
    def get_all_remote_versions(self) -> Dict[str, Dict[str, int]]:
        """获取所有远程实例的版本向量"""
        return {rid: vv.to_dict() for rid, vv in self.remote_versions.items()}
    
    def get_stats(self) -> Dict[str, Any]:
        """获取同步管理器统计信息"""
        return {
            "instance_id": self.instance_id,
            "local_sync": self.local_sync.get_stats(),
            "remote_count": len(self.remote_versions),
            "remote_versions": self.get_all_remote_versions()
        }
    
    def clear(self):
        """清空同步管理器状态"""
        self.local_sync.clear()
        self.remote_versions.clear()
        self._sync_callbacks.clear()
    
    def __repr__(self) -> str:
        return f"SyncManager(instance={self.instance_id}, remotes={len(self.remote_versions)})"

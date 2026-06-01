"""
持久化存储优化模块

提供增量保存、压缩存储和高效加载机制。
遵循"图难于其易，为大于其细"原则，从简单可验证的实现开始。
"""

import json
import gzip
import os
import time
from typing import Dict, List, Optional, Set, Tuple, Any
from dataclasses import dataclass, field


@dataclass
class StorageConfig:
    """存储配置"""
    use_compression: bool = True
    compression_level: int = 6  # 1-9
    incremental_save: bool = True
    max_backup_count: int = 5
    auto_save_interval: float = 300.0  # 5 分钟
    batch_size: int = 1000


class IncrementalStorage:
    """
    增量存储管理器
    
    支持增量保存，只保存变更的数据，减少 I/O 开销。
    """
    
    def __init__(self, base_path: str, config: Optional[StorageConfig] = None):
        """
        初始化增量存储
        
        Args:
            base_path: 基础存储路径
            config: 存储配置
        """
        self.base_path = base_path
        self.config = config or StorageConfig()
        
        # 变更追踪
        self._dirty_nodes: Set[str] = set()
        self._dirty_edges: Set[Tuple[str, str, str]] = set()
        self._deleted_nodes: Set[str] = set()
        self._deleted_edges: Set[Tuple[str, str, str]] = set()
        
        # 元数据
        self._last_full_save = 0.0
        self._save_count = 0
        self._changelog: List[Dict[str, Any]] = []
        
        # 确保目录存在
        os.makedirs(os.path.dirname(base_path) or ".", exist_ok=True)
    
    def mark_node_dirty(self, node_name: str):
        """标记节点为脏"""
        self._dirty_nodes.add(node_name)
        self._deleted_nodes.discard(node_name)
    
    def mark_edge_dirty(self, source: str, target: str, relation: str):
        """标记边为脏"""
        edge_key = (source, target, relation)
        self._dirty_edges.add(edge_key)
        self._deleted_edges.discard(edge_key)
    
    def mark_node_deleted(self, node_name: str):
        """标记节点已删除"""
        self._deleted_nodes.add(node_name)
        self._dirty_nodes.discard(node_name)
    
    def mark_edge_deleted(self, source: str, target: str, relation: str):
        """标记边已删除"""
        edge_key = (source, target, relation)
        self._deleted_edges.add(edge_key)
        self._dirty_edges.discard(edge_key)
    
    def has_changes(self) -> bool:
        """检查是否有未保存的变更"""
        return bool(
            self._dirty_nodes or self._dirty_edges or
            self._deleted_nodes or self._deleted_edges
        )
    
    def get_changes_summary(self) -> Dict[str, int]:
        """获取变更摘要"""
        return {
            "dirty_nodes": len(self._dirty_nodes),
            "dirty_edges": len(self._dirty_edges),
            "deleted_nodes": len(self._deleted_nodes),
            "deleted_edges": len(self._deleted_edges),
            "total_changes": (
                len(self._dirty_nodes) + len(self._dirty_edges) +
                len(self._deleted_nodes) + len(self._deleted_edges)
            )
        }
    
    def clear_changes(self):
        """清除变更追踪"""
        self._dirty_nodes.clear()
        self._dirty_edges.clear()
        self._deleted_nodes.clear()
        self._deleted_edges.clear()
    
    def save_full(self, data: Dict[str, Any]) -> bool:
        """
        执行完整保存
        
        Args:
            data: 完整数据
            
        Returns:
            是否成功
        """
        try:
            # 创建备份
            self._create_backup()
            
            # 保存数据
            if self.config.use_compression:
                self._save_compressed(data)
            else:
                self._save_uncompressed(data)
            
            self._last_full_save = time.time()
            self._save_count += 1
            self.clear_changes()
            
            return True
        except Exception:
            return False
    
    def save_incremental(self, data: Dict[str, Any]) -> bool:
        """
        执行增量保存
        
        只保存变更的数据。
        
        Args:
            data: 完整数据（用于提取变更部分）
            
        Returns:
            是否成功
        """
        if not self.has_changes():
            return True  # 没有变更，无需保存
        
        try:
            # 构建增量数据
            incremental_data = {
                "type": "incremental",
                "timestamp": time.time(),
                "nodes": {},
                "edges": [],
                "deleted_nodes": list(self._deleted_nodes),
                "deleted_edges": [
                    {"source": s, "target": t, "relation": r}
                    for s, t, r in self._deleted_edges
                ]
            }
            
            # 提取变更的节点
            nodes = data.get("nodes", {})
            for node_name in self._dirty_nodes:
                if node_name in nodes:
                    incremental_data["nodes"][node_name] = nodes[node_name]
            
            # 提取变更的边
            edges = data.get("edges", [])
            edge_set = set(
                (e.get("source"), e.get("target"), e.get("relation"))
                for e in edges
            )
            for edge_key in self._dirty_edges:
                if edge_key in edge_set:
                    # 找到对应的边数据
                    for edge in edges:
                        if (edge.get("source"), edge.get("target"), edge.get("relation")) == edge_key:
                            incremental_data["edges"].append(edge)
                            break
            
            # 保存增量数据
            incremental_path = f"{self.base_path}.inc"
            with open(incremental_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(incremental_data, ensure_ascii=False) + "\n")
            
            # 记录到变更日志
            self._changelog.append({
                "type": "incremental",
                "timestamp": time.time(),
                "changes": self.get_changes_summary()
            })
            
            self.clear_changes()
            
            # 检查是否需要执行完整保存
            if self._should_full_save():
                return self.save_full(data)
            
            return True
        except Exception:
            return False
    
    def load(self) -> Optional[Dict[str, Any]]:
        """
        加载数据
        
        先加载完整数据，然后应用增量变更。
        
        Returns:
            加载的数据
        """
        try:
            # 加载完整数据
            if self.config.use_compression and os.path.exists(f"{self.base_path}.gz"):
                data = self._load_compressed()
            elif os.path.exists(self.base_path):
                data = self._load_uncompressed()
            else:
                return None
            
            # 应用增量变更
            data = self._apply_incremental_changes(data)
            
            return data
        except Exception:
            return None
    
    def _save_compressed(self, data: Dict[str, Any]):
        """压缩保存"""
        json_data = json.dumps(data, ensure_ascii=False, indent=2)
        with gzip.open(f"{self.base_path}.gz", "wt", encoding="utf-8",
                      compresslevel=self.config.compression_level) as f:
            f.write(json_data)
    
    def _save_uncompressed(self, data: Dict[str, Any]):
        """非压缩保存"""
        with open(self.base_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    def _load_compressed(self) -> Dict[str, Any]:
        """加载压缩数据"""
        with gzip.open(f"{self.base_path}.gz", "rt", encoding="utf-8") as f:
            return json.load(f)
    
    def _load_uncompressed(self) -> Dict[str, Any]:
        """加载非压缩数据"""
        with open(self.base_path, "r", encoding="utf-8") as f:
            return json.load(f)
    
    def _apply_incremental_changes(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """应用增量变更"""
        incremental_path = f"{self.base_path}.inc"
        if not os.path.exists(incremental_path):
            return data
        
        nodes = data.get("nodes", {})
        edges = data.get("edges", [])
        
        with open(incremental_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                
                try:
                    inc_data = json.loads(line)
                    if inc_data.get("type") != "incremental":
                        continue
                    
                    # 应用节点变更
                    for node_name, node_data in inc_data.get("nodes", {}).items():
                        nodes[node_name] = node_data
                    
                    # 应用边变更
                    for edge in inc_data.get("edges", []):
                        # 删除旧边（如果存在）
                        edges = [
                            e for e in edges
                            if not (
                                e.get("source") == edge.get("source") and
                                e.get("target") == edge.get("target") and
                                e.get("relation") == edge.get("relation")
                            )
                        ]
                        edges.append(edge)
                    
                    # 应用删除
                    for node_name in inc_data.get("deleted_nodes", []):
                        nodes.pop(node_name, None)
                    
                    for edge_info in inc_data.get("deleted_edges", []):
                        edges = [
                            e for e in edges
                            if not (
                                e.get("source") == edge_info.get("source") and
                                e.get("target") == edge_info.get("target") and
                                e.get("relation") == edge_info.get("relation")
                            )
                        ]
                except json.JSONDecodeError:
                    continue
        
        data["nodes"] = nodes
        data["edges"] = edges
        return data
    
    def _create_backup(self):
        """创建备份"""
        if not os.path.exists(self.base_path):
            return
        
        # 创建带时间戳的备份
        timestamp = int(time.time())
        backup_path = f"{self.base_path}.backup.{timestamp}"
        
        try:
            import shutil
            shutil.copy2(self.base_path, backup_path)
            
            # 清理旧备份
            self._cleanup_old_backups()
        except Exception:
            pass
    
    def _cleanup_old_backups(self):
        """清理旧备份"""
        backup_files = []
        base_dir = os.path.dirname(self.base_path) or "."
        base_name = os.path.basename(self.base_path)
        
        for filename in os.listdir(base_dir):
            if filename.startswith(f"{base_name}.backup."):
                filepath = os.path.join(base_dir, filename)
                backup_files.append((filepath, os.path.getmtime(filepath)))
        
        # 按时间排序，保留最新的
        backup_files.sort(key=lambda x: x[1], reverse=True)
        
        for filepath, _ in backup_files[self.config.max_backup_count:]:
            try:
                os.remove(filepath)
            except Exception:
                pass
    
    def _should_full_save(self) -> bool:
        """检查是否应该执行完整保存"""
        # 每 10 次增量保存后执行一次完整保存
        if self._save_count % 10 == 0 and self._save_count > 0:
            return True
        
        # 超过一定时间后执行完整保存
        if time.time() - self._last_full_save > self.config.auto_save_interval:
            return True
        
        return False
    
    def compact(self, data: Dict[str, Any]) -> bool:
        """
        压缩存储
        
        执行完整保存并清理增量文件。
        
        Args:
            data: 完整数据
            
        Returns:
            是否成功
        """
        if self.save_full(data):
            # 清理增量文件
            incremental_path = f"{self.base_path}.inc"
            if os.path.exists(incremental_path):
                try:
                    os.remove(incremental_path)
                except Exception:
                    pass
            return True
        return False
    
    def get_storage_stats(self) -> Dict[str, Any]:
        """获取存储统计"""
        stats = {
            "base_path": self.base_path,
            "config": {
                "use_compression": self.config.use_compression,
                "incremental_save": self.config.incremental_save,
                "max_backup_count": self.config.max_backup_count
            },
            "save_count": self._save_count,
            "last_full_save": self._last_full_save,
            "has_changes": self.has_changes(),
            "changes_summary": self.get_changes_summary()
        }
        
        # 文件大小
        if os.path.exists(self.base_path):
            stats["file_size"] = os.path.getsize(self.base_path)
        
        if os.path.exists(f"{self.base_path}.gz"):
            stats["compressed_size"] = os.path.getsize(f"{self.base_path}.gz")
        
        incremental_path = f"{self.base_path}.inc"
        if os.path.exists(incremental_path):
            stats["incremental_size"] = os.path.getsize(incremental_path)
        
        return stats
    
    def clear(self):
        """清空存储状态"""
        self.clear_changes()
        self._last_full_save = 0.0
        self._save_count = 0
        self._changelog.clear()


class StorageOptimizer:
    """
    存储优化器
    
    提供数据压缩和去重功能。
    """
    
    @staticmethod
    def deduplicate_edges(edges: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        去重边列表
        
        保留最新的边（基于权重）。
        """
        seen = {}
        for edge in edges:
            key = (edge.get("source"), edge.get("target"), edge.get("relation"))
            if key not in seen or edge.get("weight", 0) > seen[key].get("weight", 0):
                seen[key] = edge
        
        return list(seen.values())
    
    @staticmethod
    def compress_attributes(attributes: Dict[str, Any]) -> Dict[str, Any]:
        """
        压缩属性
        
        移除空值和默认值。
        """
        compressed = {}
        for key, value in attributes.items():
            if value is not None and value != "" and value != []:
                compressed[key] = value
        return compressed
    
    @staticmethod
    def estimate_size(data: Dict[str, Any]) -> int:
        """估算数据大小（字节）"""
        return len(json.dumps(data, ensure_ascii=False).encode("utf-8"))

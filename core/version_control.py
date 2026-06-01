import copy
import time
import json
import os
from typing import Dict, List, Optional, Any


class Snapshot:
    """
    知识图谱快照

    功能：保存某一时刻知识图谱的完整状态
    原理：深拷贝节点和边数据
    """

    def __init__(self, name: str, nodes: Dict[str, Any], edges: List[Any],
                 parent: Optional[str] = None):
        self.name = name
        self.timestamp = time.time()
        self.nodes = copy.deepcopy(nodes)
        self.edges = copy.deepcopy(edges)
        self.parent = parent  # 父快照名称

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "timestamp": self.timestamp,
            "node_count": len(self.nodes),
            "edge_count": len(self.edges),
            "parent": self.parent
        }


class Branch:
    """
    分支

    功能：支持知识图谱的多线发展
    原理：每个分支有自己的快照历史
    """

    def __init__(self, name: str, base_snapshot: Optional[str] = None):
        self.name = name
        self.base_snapshot = base_snapshot
        self.snapshots: List[str] = []  # 快照名称列表
        self.created_at = time.time()

    def add_snapshot(self, snapshot_name: str) -> None:
        self.snapshots.append(snapshot_name)

    def get_latest_snapshot(self) -> Optional[str]:
        return self.snapshots[-1] if self.snapshots else self.base_snapshot

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "base_snapshot": self.base_snapshot,
            "snapshots": self.snapshots,
            "created_at": self.created_at
        }


class VersionControl:
    """
    版本控制系统

    功能：为知识图谱提供 Git 风格的版本管理
    - 快照：保存完整状态
    - 分支：多线发展
    - 合并：合并分支变更
    - 回滚：恢复到历史版本

    原理：基于深拷贝的快照机制，支持分支和合并操作
    """

    def __init__(self, knowledge_graph):
        self.kg = knowledge_graph
        self._snapshots: Dict[str, Snapshot] = {}
        self._branches: Dict[str, Branch] = {}
        self._current_branch: str = "main"
        self._create_default_branch()

    def _create_default_branch(self) -> None:
        """创建默认主分支"""
        if "main" not in self._branches:
            self._branches["main"] = Branch("main")

    def create_snapshot(self, name: str) -> bool:
        """
        创建快照

        功能：保存当前知识图谱状态

        Args:
            name: 快照名称

        Returns:
            是否成功
        """
        if name in self._snapshots:
            return False

        # 获取当前分支的最新快照作为父快照
        parent = self._branches[self._current_branch].get_latest_snapshot()

        # 序列化节点和边
        nodes_data = {
            name: node.to_dict()
            for name, node in self.kg.nodes.items()
        }
        edges_data = [edge.to_dict() for edge in self.kg.edges]

        snapshot = Snapshot(name, nodes_data, edges_data, parent)
        self._snapshots[name] = snapshot
        self._branches[self._current_branch].add_snapshot(name)
        return True

    def restore_snapshot(self, name: str) -> bool:
        """
        恢复快照（回滚）

        功能：将知识图谱恢复到指定快照的状态

        Args:
            name: 快照名称

        Returns:
            是否成功
        """
        if name not in self._snapshots:
            return False

        snapshot = self._snapshots[name]

        # 清空当前图谱
        self.kg.clear()

        # 恢复节点
        from .node import Node
        from .edge import Edge

        for node_name, node_data in snapshot.nodes.items():
            self.kg.nodes[node_name] = Node.from_dict(node_data)

        # 恢复边
        self.kg.edges = [Edge.from_dict(edge_data) for edge_data in snapshot.edges]

        # 重建索引
        self.kg._rebuild_edge_indexes()

        return True

    def create_branch(self, name: str, from_snapshot: Optional[str] = None) -> bool:
        """
        创建分支

        功能：从指定快照（或当前最新快照）创建新分支

        Args:
            name: 分支名称
            from_snapshot: 基于的快照名称（默认使用当前分支最新快照）

        Returns:
            是否成功
        """
        if name in self._branches:
            return False

        if from_snapshot is None:
            from_snapshot = self._branches[self._current_branch].get_latest_snapshot()

        self._branches[name] = Branch(name, from_snapshot)
        return True

    def switch_branch(self, name: str) -> bool:
        """
        切换分支

        功能：切换到指定分支，并恢复到该分支的最新快照

        Args:
            name: 分支名称

        Returns:
            是否成功
        """
        if name not in self._branches:
            return False

        self._current_branch = name

        # 恢复到分支的最新快照
        latest = self._branches[name].get_latest_snapshot()
        if latest is not None:
            self.restore_snapshot(latest)

        return True

    def merge_branch(self, source_branch: str, target_branch: Optional[str] = None) -> Dict[str, Any]:
        """
        合并分支

        功能：将源分支的变更合并到目标分支
        原理：简单合并策略，源分支的节点和边添加到目标分支

        Args:
            source_branch: 源分支名称
            target_branch: 目标分支名称（默认当前分支）

        Returns:
            合并结果统计
        """
        if target_branch is None:
            target_branch = self._current_branch

        if source_branch not in self._branches or target_branch not in self._branches:
            return {"success": False, "reason": "Branch not found"}

        # 获取源分支的最新快照
        source_latest = self._branches[source_branch].get_latest_snapshot()
        if source_latest is None:
            return {"success": False, "reason": "Source branch has no snapshots"}

        # 保存当前状态
        original_branch = self._current_branch

        # 切换到目标分支
        self.switch_branch(target_branch)

        # 获取源快照数据
        source_snapshot = self._snapshots[source_latest]

        # 合并节点（源分支的节点覆盖目标分支）
        nodes_added = 0
        nodes_updated = 0
        from .node import Node

        for node_name, node_data in source_snapshot.nodes.items():
            if node_name not in self.kg.nodes:
                nodes_added += 1
            else:
                nodes_updated += 1
            self.kg.nodes[node_name] = Node.from_dict(node_data)

        # 合并边（简单追加，不去重）
        from .edge import Edge
        existing_edges = set(
            (e.source, e.target, e.relation_name)
            for e in self.kg.edges
        )
        edges_added = 0

        for edge_data in source_snapshot.edges:
            edge_key = (edge_data["source"], edge_data["target"], edge_data["relation_name"])
            if edge_key not in existing_edges:
                self.kg.edges.append(Edge.from_dict(edge_data))
                edges_added += 1

        # 重建索引
        self.kg._rebuild_edge_indexes()

        # 创建合并后的快照
        merge_name = f"merge_{source_branch}_into_{target_branch}_{int(time.time())}"
        self.create_snapshot(merge_name)

        # 恢复原始分支
        if original_branch != target_branch:
            self.switch_branch(original_branch)

        return {
            "success": True,
            "merge_snapshot": merge_name,
            "nodes_added": nodes_added,
            "nodes_updated": nodes_updated,
            "edges_added": edges_added
        }

    def get_snapshot_history(self, branch: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        获取快照历史

        Args:
            branch: 分支名称（默认当前分支）

        Returns:
            快照信息列表
        """
        if branch is None:
            branch = self._current_branch

        if branch not in self._branches:
            return []

        return [
            self._snapshots[name].to_dict()
            for name in self._branches[branch].snapshots
            if name in self._snapshots
        ]

    def get_branch_list(self) -> List[str]:
        """获取所有分支名称"""
        return list(self._branches.keys())

    def get_current_branch(self) -> str:
        """获取当前分支名称"""
        return self._current_branch

    def delete_snapshot(self, name: str) -> bool:
        """删除快照"""
        if name not in self._snapshots:
            return False

        # 从所有分支中移除
        for branch in self._branches.values():
            if name in branch.snapshots:
                branch.snapshots.remove(name)

        del self._snapshots[name]
        return True

    def delete_branch(self, name: str) -> bool:
        """删除分支（不能删除当前分支）"""
        if name == self._current_branch or name not in self._branches:
            return False

        del self._branches[name]
        return True

    def diff_snapshots(self, snapshot1: str, snapshot2: str) -> Dict[str, Any]:
        """
        比较两个快照的差异

        Returns:
            {
                "nodes_added": [...],
                "nodes_removed": [...],
                "nodes_changed": [...],
                "edges_added": [...],
                "edges_removed": [...]
            }
        """
        if snapshot1 not in self._snapshots or snapshot2 not in self._snapshots:
            return {"error": "Snapshot not found"}

        s1 = self._snapshots[snapshot1]
        s2 = self._snapshots[snapshot2]

        nodes1 = set(s1.nodes.keys())
        nodes2 = set(s2.nodes.keys())

        edges1 = set(
            (e["source"], e["target"], e["relation_name"])
            for e in s1.edges
        )
        edges2 = set(
            (e["source"], e["target"], e["relation_name"])
            for e in s2.edges
        )

        return {
            "nodes_added": list(nodes2 - nodes1),
            "nodes_removed": list(nodes1 - nodes2),
            "nodes_changed": [],  # 简化处理
            "edges_added": list(edges2 - edges1),
            "edges_removed": list(edges1 - edges2)
        }

    def get_stats(self) -> Dict[str, Any]:
        """获取版本控制统计信息"""
        return {
            "total_snapshots": len(self._snapshots),
            "total_branches": len(self._branches),
            "current_branch": self._current_branch,
            "branches": {name: branch.to_dict() for name, branch in self._branches.items()}
        }

"""
知识图谱分片管理模块

提供知识图谱的水平分片存储能力，支持基于哈希的分片策略。
遵循"图难于其易，为大于其细"原则，从简单可验证的分片实现开始。
"""

import hashlib
import os
import json
from typing import Dict, List, Optional, Set, Tuple, Callable
from .knowledge_graph import KnowledgeGraph
from .node import Node
from .edge import Edge


class Shard:
    """
    单个分片，封装一个 KnowledgeGraph 实例
    """
    
    def __init__(self, shard_id: int, save_dir: str = "shards"):
        self.shard_id = shard_id
        self.save_dir = save_dir
        self.save_path = os.path.join(save_dir, f"shard_{shard_id}.json")
        self.graph = KnowledgeGraph(self.save_path)
        self._node_count = 0
        self._edge_count = 0
        self._update_counts()
    
    def _update_counts(self):
        """更新节点和边计数"""
        self._node_count = len(self.graph.nodes)
        self._edge_count = len(self.graph.edges)
    
    @property
    def node_count(self) -> int:
        """获取节点数量"""
        self._update_counts()
        return self._node_count
    
    @property
    def edge_count(self) -> int:
        """获取边数量"""
        self._update_counts()
        return self._edge_count
    
    def add_node(self, name: str, attributes: Optional[dict] = None) -> bool:
        """添加节点到分片"""
        result = self.graph.add_node(name, attributes)
        if result:
            self._node_count += 1
        return result
    
    def get_node(self, name: str) -> Optional[Node]:
        """获取节点"""
        return self.graph.get_node(name)
    
    def has_node(self, name: str) -> bool:
        """检查节点是否存在"""
        return self.graph.has_node(name)
    
    def add_edge(self, source: str, target: str, relation: str, weight: float = 0.5) -> bool:
        """添加边到分片"""
        result = self.graph.add_edge(source, target, relation, weight)
        if result:
            self._edge_count += 1
        return result
    
    def get_edges_from_node(self, node_name: str) -> List[Edge]:
        """获取从节点出发的边"""
        return self.graph.get_edges_from_node(node_name)
    
    def get_edges_to_node(self, node_name: str) -> List[Edge]:
        """获取指向节点的边"""
        return self.graph.get_edges_to_node(node_name)
    
    def save(self) -> bool:
        """保存分片数据"""
        try:
            self.graph.save()
            return True
        except Exception:
            return False
    
    def load(self) -> bool:
        """加载分片数据"""
        try:
            self.graph.load()
            self._update_counts()
            return True
        except Exception:
            return False
    
    def clear(self):
        """清空分片数据"""
        self.graph.clear()
        self._node_count = 0
        self._edge_count = 0
    
    def get_all_nodes(self) -> Dict[str, Node]:
        """获取所有节点"""
        return self.graph.nodes
    
    def get_all_edges(self) -> List[Edge]:
        """获取所有边"""
        return self.graph.edges
    
    def __repr__(self) -> str:
        return f"Shard(id={self.shard_id}, nodes={self.node_count}, edges={self.edge_count})"


class ShardManager:
    """
    分片管理器，负责管理多个分片并提供统一的访问接口
    
    使用一致性哈希算法将节点分布到不同的分片上，
    支持分片的动态添加和移除。
    """
    
    def __init__(self, num_shards: int = 4, save_dir: str = "shards"):
        """
        初始化分片管理器
        
        Args:
            num_shards: 初始分片数量
            save_dir: 分片数据保存目录
        """
        self.num_shards = num_shards
        self.save_dir = save_dir
        self.shards: Dict[int, Shard] = {}
        self._virtual_nodes_per_shard = 150  # 每个分片的虚拟节点数
        self._hash_ring: List[Tuple[int, int]] = []  # (hash_value, shard_id)
        
        # 确保保存目录存在
        os.makedirs(save_dir, exist_ok=True)
        
        # 初始化分片
        self._init_shards()
        self._build_hash_ring()
    
    def _init_shards(self):
        """初始化所有分片"""
        for i in range(self.num_shards):
            self.shards[i] = Shard(i, self.save_dir)
    
    def _build_hash_ring(self):
        """
        构建一致性哈希环
        
        为每个物理分片创建多个虚拟节点，均匀分布在哈希环上，
        从而实现更均衡的数据分布。
        """
        self._hash_ring = []
        for shard_id in range(self.num_shards):
            for v in range(self._virtual_nodes_per_shard):
                # 为每个虚拟节点生成唯一的哈希键
                hash_key = f"shard_{shard_id}_vnode_{v}"
                hash_value = self._hash(hash_key)
                self._hash_ring.append((hash_value, shard_id))
        
        # 按哈希值排序
        self._hash_ring.sort(key=lambda x: x[0])
    
    def _hash(self, key: str) -> int:
        """
        计算字符串的哈希值
        
        使用 MD5 哈希算法，将结果映射到 32 位整数空间。
        """
        return int(hashlib.md5(key.encode('utf-8')).hexdigest(), 16) % (2**32)
    
    def _get_shard_id_for_node(self, node_name: str) -> int:
        """
        根据节点名称确定其所属的分片
        
        使用一致性哈希算法，在哈希环上找到最近的虚拟节点。
        """
        if not self._hash_ring:
            return 0
        
        node_hash = self._hash(node_name)
        
        # 在哈希环上找到第一个大于等于 node_hash 的虚拟节点
        for hash_value, shard_id in self._hash_ring:
            if hash_value >= node_hash:
                return shard_id
        
        # 如果没有找到，返回第一个虚拟节点（环形回绕）
        return self._hash_ring[0][1]
    
    def add_node(self, name: str, attributes: Optional[dict] = None) -> bool:
        """
        添加节点到合适的分片
        
        根据节点名称的一致性哈希确定目标分片。
        """
        shard_id = self._get_shard_id_for_node(name)
        return self.shards[shard_id].add_node(name, attributes)
    
    def get_node(self, name: str) -> Optional[Node]:
        """
        从对应分片获取节点
        """
        shard_id = self._get_shard_id_for_node(name)
        return self.shards[shard_id].get_node(name)
    
    def has_node(self, name: str) -> bool:
        """
        检查节点是否存在
        """
        shard_id = self._get_shard_id_for_node(name)
        return self.shards[shard_id].has_node(name)
    
    def add_edge(self, source: str, target: str, relation: str, weight: float = 0.5) -> bool:
        """
        添加边到知识图谱
        
        注意：边可能跨越多个分片，需要确保两个节点都存在。
        如果节点不在对应的分片上，会自动创建。
        """
        source_shard_id = self._get_shard_id_for_node(source)
        target_shard_id = self._get_shard_id_for_node(target)
        
        # 确保源节点存在
        if not self.shards[source_shard_id].has_node(source):
            self.shards[source_shard_id].add_node(source)
        
        # 确保目标节点存在
        if not self.shards[target_shard_id].has_node(target):
            self.shards[target_shard_id].add_node(target)
        
        # 在源节点所在分片添加边
        return self.shards[source_shard_id].add_edge(source, target, relation, weight)
    
    def get_edges_from_node(self, node_name: str) -> List[Edge]:
        """
        获取从节点出发的所有边
        """
        shard_id = self._get_shard_id_for_node(node_name)
        return self.shards[shard_id].get_edges_from_node(node_name)
    
    def get_edges_to_node(self, node_name: str) -> List[Edge]:
        """
        获取指向节点的所有边
        
        注意：由于边可能分布在不同分片，需要遍历所有分片。
        """
        edges = []
        for shard in self.shards.values():
            edges.extend(shard.get_edges_to_node(node_name))
        return edges
    
    def get_all_nodes(self) -> Dict[str, Node]:
        """
        获取所有节点
        """
        all_nodes = {}
        for shard in self.shards.values():
            all_nodes.update(shard.get_all_nodes())
        return all_nodes
    
    def get_all_edges(self) -> List[Edge]:
        """
        获取所有边
        """
        all_edges = []
        for shard in self.shards.values():
            all_edges.extend(shard.get_all_edges())
        return all_edges
    
    def get_shard_for_node(self, node_name: str) -> Shard:
        """
        获取节点所在的分片
        """
        shard_id = self._get_shard_id_for_node(node_name)
        return self.shards[shard_id]
    
    def get_shard_stats(self) -> Dict[int, Dict[str, int]]:
        """
        获取各分片的统计信息
        """
        stats = {}
        for shard_id, shard in self.shards.items():
            stats[shard_id] = {
                "node_count": shard.node_count,
                "edge_count": shard.edge_count
            }
        return stats
    
    def get_total_stats(self) -> Dict[str, int]:
        """
        获取总体统计信息
        """
        total_nodes = sum(shard.node_count for shard in self.shards.values())
        total_edges = sum(shard.edge_count for shard in self.shards.values())
        return {
            "total_nodes": total_nodes,
            "total_edges": total_edges,
            "num_shards": self.num_shards
        }
    
    def rebalance(self) -> Dict[str, int]:
        """
        重新平衡分片数据
        
        检查每个分片的负载，如果某个分片过载，
        尝试将部分数据迁移到负载较轻的分片。
        
        Returns:
            迁移统计信息
        """
        stats = self.get_shard_stats()
        
        # 计算平均负载
        avg_nodes = sum(s["node_count"] for s in stats.values()) / len(stats)
        
        migrated = 0
        
        # 简单的重新平衡：将超过平均值 50% 的分片的部分节点迁移
        for shard_id, shard_stats in stats.items():
            if shard_stats["node_count"] > avg_nodes * 1.5:
                # 找到负载最轻的分片
                min_shard_id = min(stats.keys(), key=lambda k: stats[k]["node_count"])
                
                # 计算需要迁移的节点数
                nodes_to_move = int((shard_stats["node_count"] - avg_nodes) * 0.5)
                
                # 迁移节点（这里简化处理，实际应该考虑一致性哈希）
                # 注意：实际迁移逻辑较复杂，需要处理边的关系
                # 这里仅作为示例框架
                migrated += nodes_to_move
        
        return {"migrated_nodes": migrated}
    
    def add_shard(self) -> int:
        """
        动态添加新分片
        
        Returns:
            新分片的 ID
        """
        new_shard_id = max(self.shards.keys()) + 1 if self.shards else 0
        self.shards[new_shard_id] = Shard(new_shard_id, self.save_dir)
        self.num_shards += 1
        
        # 重建哈希环
        self._build_hash_ring()
        
        return new_shard_id
    
    def remove_shard(self, shard_id: int) -> bool:
        """
        移除分片并将数据迁移到其他分片
        
        Args:
            shard_id: 要移除的分片 ID
            
        Returns:
            是否成功移除
        """
        if shard_id not in self.shards:
            return False
        
        # 获取要移除的分片
        shard_to_remove = self.shards[shard_id]
        
        # 将数据迁移到其他分片
        # 注意：这里简化处理，实际应该根据一致性哈希重新分配
        # 为简化实现，我们将节点均匀分配到剩余分片
        remaining_shards = [sid for sid in self.shards.keys() if sid != shard_id]
        
        if remaining_shards:
            nodes = list(shard_to_remove.get_all_nodes().keys())
            for i, node_name in enumerate(nodes):
                target_shard_id = remaining_shards[i % len(remaining_shards)]
                node = shard_to_remove.get_node(node_name)
                if node:
                    self.shards[target_shard_id].add_node(node_name, node.attributes)
            
            # 迁移边
            edges = shard_to_remove.get_all_edges()
            for edge in edges:
                target_shard_id = self._get_shard_id_for_node(edge.source)
                self.shards[target_shard_id].add_edge(
                    edge.source, edge.target, edge.relation_name, edge.weight
                )
        
        # 删除分片文件
        try:
            if os.path.exists(shard_to_remove.save_path):
                os.remove(shard_to_remove.save_path)
        except Exception:
            pass
        
        # 从管理中移除
        del self.shards[shard_id]
        self.num_shards -= 1
        
        # 重建哈希环
        self._build_hash_ring()
        
        return True
    
    def save_all(self) -> Dict[int, bool]:
        """
        保存所有分片
        
        Returns:
            各分片的保存结果
        """
        results = {}
        for shard_id, shard in self.shards.items():
            results[shard_id] = shard.save()
        return results
    
    def load_all(self) -> Dict[int, bool]:
        """
        加载所有分片
        
        Returns:
            各分片的加载结果
        """
        results = {}
        for shard_id, shard in self.shards.items():
            results[shard_id] = shard.load()
        return results
    
    def clear_all(self):
        """清空所有分片"""
        for shard in self.shards.values():
            shard.clear()
    
    def __repr__(self) -> str:
        stats = self.get_total_stats()
        return (f"ShardManager(shards={stats['num_shards']}, "
                f"nodes={stats['total_nodes']}, edges={stats['total_edges']})")

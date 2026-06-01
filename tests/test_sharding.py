"""
分片管理模块测试

测试知识图谱分片和分区存储功能。
遵循"图难于其易，为大于其细"原则，从简单可验证的测试开始。
"""

import pytest
import tempfile
import os
import shutil
from core import Shard, ShardManager


class TestShard:
    """测试单个分片功能"""
    
    def test_shard_creation(self):
        """测试分片创建"""
        with tempfile.TemporaryDirectory() as tmpdir:
            shard = Shard(0, tmpdir)
            assert shard.shard_id == 0
            assert shard.node_count == 0
            assert shard.edge_count == 0
            assert os.path.exists(shard.save_path)
    
    def test_shard_add_node(self):
        """测试分片添加节点"""
        with tempfile.TemporaryDirectory() as tmpdir:
            shard = Shard(0, tmpdir)
            
            # 添加节点
            node = shard.add_node("Alice", {"type": "person"})
            assert node is not None
            assert node.name == "Alice"
            assert shard.node_count == 1
            
            # 添加重复节点（应该返回已存在的节点）
            node2 = shard.add_node("Alice", {"type": "person"})
            assert node2.name == "Alice"
            assert shard.node_count == 1
    
    def test_shard_get_node(self):
        """测试分片获取节点"""
        with tempfile.TemporaryDirectory() as tmpdir:
            shard = Shard(0, tmpdir)
            shard.add_node("Alice", {"type": "person", "age": 30})
            
            node = shard.get_node("Alice")
            assert node is not None
            assert node.name == "Alice"
            assert node.attributes["type"] == "person"
            assert node.attributes["age"] == 30
            
            # 获取不存在的节点
            node = shard.get_node("Bob")
            assert node is None
    
    def test_shard_has_node(self):
        """测试分片检查节点是否存在"""
        with tempfile.TemporaryDirectory() as tmpdir:
            shard = Shard(0, tmpdir)
            shard.add_node("Alice")
            
            assert shard.has_node("Alice") is True
            assert shard.has_node("Bob") is False
    
    def test_shard_add_edge(self):
        """测试分片添加边"""
        with tempfile.TemporaryDirectory() as tmpdir:
            shard = Shard(0, tmpdir)
            shard.add_node("Alice")
            shard.add_node("Bob")
            
            edge = shard.add_edge("Alice", "Bob", "friend", 0.8)
            assert edge is not None
            assert edge.source == "Alice"
            assert edge.target == "Bob"
            assert edge.relation_name == "friend"
            assert shard.edge_count == 1
    
    def test_shard_get_edges(self):
        """测试分片获取边"""
        with tempfile.TemporaryDirectory() as tmpdir:
            shard = Shard(0, tmpdir)
            shard.add_node("Alice")
            shard.add_node("Bob")
            shard.add_node("Charlie")
            
            shard.add_edge("Alice", "Bob", "friend", 0.8)
            shard.add_edge("Alice", "Charlie", "friend", 0.7)
            
            edges = shard.get_edges_from_node("Alice")
            assert len(edges) == 2
            
            edges = shard.get_edges_to_node("Bob")
            assert len(edges) == 1
            assert edges[0].source == "Alice"
    
    def test_shard_save_load(self):
        """测试分片保存和加载"""
        with tempfile.TemporaryDirectory() as tmpdir:
            shard = Shard(0, tmpdir)
            shard.add_node("Alice", {"type": "person"})
            shard.add_node("Bob", {"type": "person"})
            shard.add_edge("Alice", "Bob", "friend", 0.8)
            
            # 保存
            assert shard.save() is True
            
            # 创建新分片并加载
            shard2 = Shard(0, tmpdir)
            assert shard2.load() is True
            assert shard2.node_count == 2
            assert shard2.edge_count == 1
            assert shard2.has_node("Alice")
            assert shard2.has_node("Bob")
    
    def test_shard_clear(self):
        """测试分片清空"""
        with tempfile.TemporaryDirectory() as tmpdir:
            shard = Shard(0, tmpdir)
            shard.add_node("Alice")
            shard.add_node("Bob")
            shard.add_edge("Alice", "Bob", "friend")
            
            shard.clear()
            assert shard.node_count == 0
            assert shard.edge_count == 0
            assert shard.has_node("Alice") is False
    
    def test_shard_repr(self):
        """测试分片字符串表示"""
        with tempfile.TemporaryDirectory() as tmpdir:
            shard = Shard(0, tmpdir)
            assert repr(shard) == "Shard(id=0, nodes=0, edges=0)"
            
            shard.add_node("Alice")
            assert "Shard(id=0, nodes=1, edges=0)" == repr(shard)


class TestShardManager:
    """测试分片管理器功能"""
    
    def test_manager_creation(self):
        """测试分片管理器创建"""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = ShardManager(num_shards=4, save_dir=tmpdir)
            assert manager.num_shards == 4
            assert len(manager.shards) == 4
            assert os.path.exists(tmpdir)
    
    def test_manager_add_node(self):
        """测试分片管理器添加节点"""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = ShardManager(num_shards=4, save_dir=tmpdir)
            
            # 添加节点
            node = manager.add_node("Alice", {"type": "person"})
            assert node is not None
            assert node.name == "Alice"
            
            # 验证节点被分配到某个分片
            total_nodes = manager.get_total_stats()["total_nodes"]
            assert total_nodes == 1
            
            # 获取节点
            node2 = manager.get_node("Alice")
            assert node2 is not None
            assert node2.name == "Alice"
    
    def test_manager_add_edge(self):
        """测试分片管理器添加边"""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = ShardManager(num_shards=4, save_dir=tmpdir)
            
            manager.add_node("Alice")
            manager.add_node("Bob")
            edge = manager.add_edge("Alice", "Bob", "friend", 0.8)
            assert edge is not None
            assert edge.source == "Alice"
            assert edge.target == "Bob"
            
            total_edges = manager.get_total_stats()["total_edges"]
            assert total_edges == 1
    
    def test_manager_get_edges(self):
        """测试分片管理器获取边"""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = ShardManager(num_shards=4, save_dir=tmpdir)
            
            manager.add_node("Alice")
            manager.add_node("Bob")
            manager.add_node("Charlie")
            
            manager.add_edge("Alice", "Bob", "friend", 0.8)
            manager.add_edge("Alice", "Charlie", "friend", 0.7)
            
            edges = manager.get_edges_from_node("Alice")
            assert len(edges) == 2
            
            edges = manager.get_edges_to_node("Bob")
            assert len(edges) == 1
    
    def test_manager_cross_shard_edge(self):
        """测试跨分片边"""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = ShardManager(num_shards=4, save_dir=tmpdir)
            
            # 添加节点（可能被分配到不同分片）
            manager.add_node("Alice")
            manager.add_node("Bob")
            
            # 添加边
            manager.add_edge("Alice", "Bob", "friend", 0.8)
            
            # 验证边存在
            edges = manager.get_edges_from_node("Alice")
            assert len(edges) == 1
            assert edges[0].target == "Bob"
    
    def test_manager_get_all_nodes(self):
        """测试获取所有节点"""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = ShardManager(num_shards=4, save_dir=tmpdir)
            
            nodes = ["Alice", "Bob", "Charlie", "David", "Eve"]
            for node in nodes:
                manager.add_node(node)
            
            all_nodes = manager.get_all_nodes()
            assert len(all_nodes) == len(nodes)
            
            for node in nodes:
                assert node in all_nodes
    
    def test_manager_get_all_edges(self):
        """测试获取所有边"""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = ShardManager(num_shards=4, save_dir=tmpdir)
            
            manager.add_node("Alice")
            manager.add_node("Bob")
            manager.add_node("Charlie")
            
            manager.add_edge("Alice", "Bob", "friend")
            manager.add_edge("Bob", "Charlie", "friend")
            
            all_edges = manager.get_all_edges()
            assert len(all_edges) == 2
    
    def test_manager_shard_stats(self):
        """测试分片统计信息"""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = ShardManager(num_shards=4, save_dir=tmpdir)
            
            # 添加多个节点
            for i in range(20):
                manager.add_node(f"node_{i}")
            
            stats = manager.get_shard_stats()
            assert len(stats) == 4
            
            total_stats = manager.get_total_stats()
            assert total_stats["total_nodes"] == 20
            assert total_stats["num_shards"] == 4
    
    def test_manager_add_shard(self):
        """测试动态添加分片"""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = ShardManager(num_shards=4, save_dir=tmpdir)
            
            new_shard_id = manager.add_shard()
            assert new_shard_id == 4
            assert manager.num_shards == 5
            assert new_shard_id in manager.shards
    
    def test_manager_remove_shard(self):
        """测试移除分片"""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = ShardManager(num_shards=4, save_dir=tmpdir)
            
            # 添加节点
            for i in range(10):
                manager.add_node(f"node_{i}")
            
            # 移除分片
            result = manager.remove_shard(0)
            assert result is True
            assert manager.num_shards == 3
            assert 0 not in manager.shards
            
            # 验证数据仍然存在
            total_nodes = manager.get_total_stats()["total_nodes"]
            assert total_nodes == 10
    
    def test_manager_remove_nonexistent_shard(self):
        """测试移除不存在的分片"""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = ShardManager(num_shards=4, save_dir=tmpdir)
            
            result = manager.remove_shard(999)
            assert result is False
    
    def test_manager_save_load_all(self):
        """测试保存和加载所有分片"""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = ShardManager(num_shards=4, save_dir=tmpdir)
            
            # 添加数据
            for i in range(10):
                manager.add_node(f"node_{i}")
            manager.add_edge("node_0", "node_1", "friend")
            
            # 保存
            results = manager.save_all()
            assert all(results.values())
            
            # 创建新管理器并加载
            # 注意：加载时会自动加载已有的分片文件
            manager2 = ShardManager(num_shards=4, save_dir=tmpdir)
            results = manager2.load_all()
            assert all(results.values())
            
            # 验证节点存在（由于 KnowledgeGraph 的 add_node 会自动创建不存在的节点，
            # 边添加时可能会创建额外的节点，所以验证至少存在原始节点）
            total_nodes = manager2.get_total_stats()["total_nodes"]
            assert total_nodes >= 10
    
    def test_manager_clear_all(self):
        """测试清空所有分片"""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = ShardManager(num_shards=4, save_dir=tmpdir)
            
            for i in range(10):
                manager.add_node(f"node_{i}")
            
            manager.clear_all()
            
            total_stats = manager.get_total_stats()
            assert total_stats["total_nodes"] == 0
            assert total_stats["total_edges"] == 0
    
    def test_manager_consistent_hashing(self):
        """测试一致性哈希的稳定性"""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = ShardManager(num_shards=4, save_dir=tmpdir)
            
            # 记录节点分配
            node_assignments = {}
            for i in range(20):
                node_name = f"node_{i}"
                manager.add_node(node_name)
                shard_id = manager._get_shard_id_for_node(node_name)
                node_assignments[node_name] = shard_id
            
            # 添加新分片
            manager.add_shard()
            
            # 验证大部分节点仍然映射到相同的分片（一致性哈希特性）
            consistent_count = 0
            for node_name, old_shard_id in node_assignments.items():
                new_shard_id = manager._get_shard_id_for_node(node_name)
                if new_shard_id == old_shard_id:
                    consistent_count += 1
            
            # 至少 50% 的节点应该保持相同的映射
            assert consistent_count >= len(node_assignments) * 0.5
    
    def test_manager_data_distribution(self):
        """测试数据分布均衡性"""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = ShardManager(num_shards=4, save_dir=tmpdir)
            
            # 添加大量节点
            for i in range(100):
                manager.add_node(f"node_{i}")
            
            stats = manager.get_shard_stats()
            node_counts = [s["node_count"] for s in stats.values()]
            
            # 检查分布是否相对均衡（最大差异不超过平均值的 50%）
            avg = sum(node_counts) / len(node_counts)
            max_diff = max(abs(count - avg) for count in node_counts)
            assert max_diff <= avg * 0.5
    
    def test_manager_repr(self):
        """测试分片管理器字符串表示"""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = ShardManager(num_shards=4, save_dir=tmpdir)
            manager.add_node("Alice")
            
            repr_str = repr(manager)
            assert "ShardManager" in repr_str
            assert "shards=4" in repr_str
            assert "nodes=1" in repr_str

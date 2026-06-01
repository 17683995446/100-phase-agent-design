"""
持久化存储优化模块测试

测试增量保存、压缩存储和数据加载功能。
遵循"图难于其易，为大于其细"原则，从简单可验证的测试开始。
"""

import pytest
import tempfile
import os
import time
from core import StorageConfig, IncrementalStorage, StorageOptimizer


class TestStorageConfig:
    """测试存储配置"""
    
    def test_default_config(self):
        """测试默认配置"""
        config = StorageConfig()
        assert config.use_compression is True
        assert config.compression_level == 6
        assert config.incremental_save is True
        assert config.max_backup_count == 5
        assert config.batch_size == 1000
    
    def test_custom_config(self):
        """测试自定义配置"""
        config = StorageConfig(
            use_compression=False,
            compression_level=9,
            max_backup_count=10
        )
        assert config.use_compression is False
        assert config.compression_level == 9
        assert config.max_backup_count == 10


class TestIncrementalStorage:
    """测试增量存储"""
    
    def test_creation(self):
        """测试创建"""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "test.json")
            storage = IncrementalStorage(path)
            assert storage.base_path == path
            assert storage.has_changes() is False
    
    def test_mark_node_dirty(self):
        """测试标记节点脏"""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "test.json")
            storage = IncrementalStorage(path)
            
            storage.mark_node_dirty("Alice")
            assert storage.has_changes() is True
            assert "Alice" in storage._dirty_nodes
    
    def test_mark_node_deleted(self):
        """测试标记节点删除"""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "test.json")
            storage = IncrementalStorage(path)
            
            storage.mark_node_dirty("Alice")
            storage.mark_node_deleted("Alice")
            
            assert "Alice" not in storage._dirty_nodes
            assert "Alice" in storage._deleted_nodes
    
    def test_get_changes_summary(self):
        """测试获取变更摘要"""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "test.json")
            storage = IncrementalStorage(path)
            
            storage.mark_node_dirty("Alice")
            storage.mark_node_dirty("Bob")
            storage.mark_edge_dirty("Alice", "Bob", "friend")
            
            summary = storage.get_changes_summary()
            assert summary["dirty_nodes"] == 2
            assert summary["dirty_edges"] == 1
            assert summary["total_changes"] == 3
    
    def test_save_full_uncompressed(self):
        """测试完整保存（非压缩）"""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "test.json")
            config = StorageConfig(use_compression=False)
            storage = IncrementalStorage(path, config)
            
            data = {
                "nodes": {
                    "Alice": {"type": "person"},
                    "Bob": {"type": "person"}
                },
                "edges": [
                    {"source": "Alice", "target": "Bob", "relation": "friend", "weight": 0.8}
                ]
            }
            
            assert storage.save_full(data) is True
            assert os.path.exists(path)
    
    def test_save_full_compressed(self):
        """测试完整保存（压缩）"""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "test.json")
            config = StorageConfig(use_compression=True)
            storage = IncrementalStorage(path, config)
            
            data = {
                "nodes": {"Alice": {"type": "person"}},
                "edges": []
            }
            
            assert storage.save_full(data) is True
            assert os.path.exists(f"{path}.gz")
    
    def test_load_uncompressed(self):
        """测试加载非压缩数据"""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "test.json")
            config = StorageConfig(use_compression=False)
            storage = IncrementalStorage(path, config)
            
            data = {
                "nodes": {"Alice": {"type": "person"}},
                "edges": []
            }
            
            storage.save_full(data)
            loaded = storage.load()
            
            assert loaded is not None
            assert loaded["nodes"]["Alice"]["type"] == "person"
    
    def test_load_compressed(self):
        """测试加载压缩数据"""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "test.json")
            config = StorageConfig(use_compression=True)
            storage = IncrementalStorage(path, config)
            
            data = {
                "nodes": {"Alice": {"type": "person"}},
                "edges": []
            }
            
            storage.save_full(data)
            loaded = storage.load()
            
            assert loaded is not None
            assert loaded["nodes"]["Alice"]["type"] == "person"
    
    def test_save_incremental(self):
        """测试增量保存"""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "test.json")
            config = StorageConfig(use_compression=False, incremental_save=True)
            storage = IncrementalStorage(path, config)
            
            # 先完整保存
            data = {
                "nodes": {"Alice": {"type": "person"}},
                "edges": []
            }
            storage.save_full(data)
            
            # 标记变更
            storage.mark_node_dirty("Bob")
            
            # 增量保存
            data["nodes"]["Bob"] = {"type": "person"}
            assert storage.save_incremental(data) is True
            
            # 验证增量文件存在
            assert os.path.exists(f"{path}.inc")
    
    def test_load_with_incremental(self):
        """测试加载包含增量变更的数据"""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "test.json")
            config = StorageConfig(use_compression=False, incremental_save=True)
            storage = IncrementalStorage(path, config)
            
            # 完整保存
            data = {
                "nodes": {"Alice": {"type": "person"}},
                "edges": []
            }
            storage.save_full(data)
            
            # 增量保存 - 添加 Bob
            storage.mark_node_dirty("Bob")
            data["nodes"]["Bob"] = {"type": "person"}
            storage.save_incremental(data)
            
            # 加载
            loaded = storage.load()
            assert loaded is not None
            assert "Alice" in loaded["nodes"]
            assert "Bob" in loaded["nodes"]
    
    def test_load_with_deletion(self):
        """测试加载包含删除的数据"""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "test.json")
            config = StorageConfig(use_compression=False, incremental_save=True)
            storage = IncrementalStorage(path, config)
            
            # 完整保存
            data = {
                "nodes": {
                    "Alice": {"type": "person"},
                    "Bob": {"type": "person"}
                },
                "edges": []
            }
            storage.save_full(data)
            
            # 增量保存 - 删除 Bob
            storage.mark_node_deleted("Bob")
            storage.save_incremental(data)
            
            # 加载
            loaded = storage.load()
            assert loaded is not None
            assert "Alice" in loaded["nodes"]
            assert "Bob" not in loaded["nodes"]
    
    def test_compact(self):
        """测试压缩存储"""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "test.json")
            config = StorageConfig(use_compression=False, incremental_save=True)
            storage = IncrementalStorage(path, config)
            
            # 完整保存
            data = {
                "nodes": {"Alice": {"type": "person"}},
                "edges": []
            }
            storage.save_full(data)
            
            # 增量保存
            storage.mark_node_dirty("Bob")
            data["nodes"]["Bob"] = {"type": "person"}
            storage.save_incremental(data)
            
            # 压缩
            assert storage.compact(data) is True
            
            # 验证增量文件被清理
            assert not os.path.exists(f"{path}.inc")
            
            # 验证数据仍然可加载
            loaded = storage.load()
            assert loaded is not None
            assert "Bob" in loaded["nodes"]
    
    def test_get_storage_stats(self):
        """测试获取存储统计"""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "test.json")
            config = StorageConfig(use_compression=False)
            storage = IncrementalStorage(path, config)
            
            data = {"nodes": {}, "edges": []}
            storage.save_full(data)
            
            stats = storage.get_storage_stats()
            assert stats["base_path"] == path
            assert stats["save_count"] == 1
            assert "file_size" in stats
    
    def test_clear(self):
        """测试清空"""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "test.json")
            storage = IncrementalStorage(path)
            
            storage.mark_node_dirty("Alice")
            storage.save_full({"nodes": {}, "edges": []})
            
            storage.clear()
            assert storage.has_changes() is False
            assert storage._save_count == 0


class TestStorageOptimizer:
    """测试存储优化器"""
    
    def test_deduplicate_edges(self):
        """测试边去重"""
        edges = [
            {"source": "Alice", "target": "Bob", "relation": "friend", "weight": 0.5},
            {"source": "Alice", "target": "Bob", "relation": "friend", "weight": 0.8},
            {"source": "Bob", "target": "Charlie", "relation": "friend", "weight": 0.6}
        ]
        
        result = StorageOptimizer.deduplicate_edges(edges)
        assert len(result) == 2
        
        # 检查保留了权重更高的边
        alice_bob = [e for e in result if e["source"] == "Alice" and e["target"] == "Bob"]
        assert len(alice_bob) == 1
        assert alice_bob[0]["weight"] == 0.8
    
    def test_compress_attributes(self):
        """测试属性压缩"""
        attributes = {
            "name": "Alice",
            "age": 30,
            "empty_string": "",
            "none_value": None,
            "empty_list": [],
            "valid_list": [1, 2, 3]
        }
        
        result = StorageOptimizer.compress_attributes(attributes)
        assert "name" in result
        assert "age" in result
        assert "empty_string" not in result
        assert "none_value" not in result
        assert "empty_list" not in result
        assert "valid_list" in result
    
    def test_estimate_size(self):
        """测试大小估算"""
        data = {"key": "value", "number": 42}
        size = StorageOptimizer.estimate_size(data)
        assert size > 0
        
        # 更大的数据应该更大
        bigger_data = {"key": "value" * 100}
        bigger_size = StorageOptimizer.estimate_size(bigger_data)
        assert bigger_size > size

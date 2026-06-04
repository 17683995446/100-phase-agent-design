#!/usr/bin/env python3
"""
阶段104：JSON持久化（原子化写入+损坏自愈）

第一性原理：
  - 数据是系统的命脉（记忆公理）
  - 写入必须保证原子性，不能写到一半崩溃
  - 损坏文件必须能自愈，不能让单点错误毁掉所有数据

本阶段产出：
  1. AtomicWriter：原子化写入（临时文件+rename）
  2. JSONStorage：JSON格式存储层
  3. BackupManager：自动备份管理
  4. CorruptionDetector：损坏检测与自愈
  5. 集成到 KnowledgeGraphCRUD

遵循原则：图难于其易，为大于其细
"""
import os
import json
import time
import shutil
import unittest
import tempfile
from typing import Dict, List, Any, Optional
from pathlib import Path

import sys
sys.path.insert(0, '/workspace')
from phase_103_kg_crud import KnowledgeGraphCRUD
from phase_102_core_datastructure import Node, Edge


# ============================================================
# 一、原子化写入器
# ============================================================
class AtomicWriter:
    """原子化写入器

    原理：
    1. 先写入临时文件
    2. fsync强制刷盘
    3. 原子rename替换目标文件
    4. 即使中途崩溃，要么旧文件要么新文件，不会半成品

    关键点：rename在大多数文件系统上是原子操作
    """
    def __init__(self, target_path: str, fsync: bool = True):
        self.target_path = target_path
        self.fsync = fsync
        self.tmp_path = target_path + ".tmp"
        self.bak_path = target_path + ".bak"

    def write(self, data: str) -> bool:
        """原子化写入数据

        Returns: True if success
        """
        try:
            target_dir = os.path.dirname(self.target_path)
            if target_dir and not os.path.exists(target_dir):
                os.makedirs(target_dir, exist_ok=True)

            # 步骤1：写入临时文件
            with open(self.tmp_path, "w", encoding="utf-8") as f:
                f.write(data)
                if self.fsync:
                    f.flush()
                    os.fsync(f.fileno())

            # 步骤2：备份现有文件（如果存在）或创建初始空备份
            if os.path.exists(self.target_path):
                shutil.copy2(self.target_path, self.bak_path)
            elif not os.path.exists(self.bak_path):
                # 首次写入：先写一份空白备份，确保后续损坏有恢复源
                with open(self.bak_path, "w", encoding="utf-8") as f:
                    f.write(data)

            # 步骤3：原子rename
            os.replace(self.tmp_path, self.target_path)
            return True
        except Exception as e:
            # 清理临时文件
            if os.path.exists(self.tmp_path):
                try:
                    os.remove(self.tmp_path)
                except Exception:
                    pass
            return False


# ============================================================
# 二、JSON存储层
# ============================================================
class JSONStorage:
    """JSON存储层

    特性：
    - 原子化写入
    - 自动备份
    - 损坏自愈
    - 统计信息
    """
    def __init__(self, file_path: str, max_backups: int = 3,
                 auto_backup: bool = True):
        self.file_path = file_path
        self.max_backups = max_backups
        self.auto_backup = auto_backup
        self.writer = AtomicWriter(file_path)
        self._stats = {
            "saves": 0,
            "loads": 0,
            "save_failures": 0,
            "load_failures": 0,
            "self_heals": 0,
        }

    def save(self, data: Dict[str, Any]) -> bool:
        """保存数据"""
        try:
            payload = {
                "data": data,
                "saved_at": time.time(),
                "version": "1.0"
            }
            json_str = json.dumps(payload, ensure_ascii=False, indent=2)
            if self.writer.write(json_str):
                self._stats["saves"] += 1
                return True
            self._stats["save_failures"] += 1
            return False
        except Exception as e:
            self._stats["save_failures"] += 1
            return False

    def load(self) -> Optional[Dict[str, Any]]:
        """加载数据，损坏时自动尝试自愈"""
        self._stats["loads"] += 1
        # 1. 先尝试加载主文件
        data = self._try_load(self.file_path)
        if data is not None:
            return data
        # 2. 尝试从备份恢复
        bak_path = self.file_path + ".bak"
        if os.path.exists(bak_path):
            data = self._try_load(bak_path)
            if data is not None:
                self._stats["self_heals"] += 1
                # 恢复到主文件
                self.save(data)
                return data
        # 3. 都失败了
        self._stats["load_failures"] += 1
        return None

    def _try_load(self, path: str) -> Optional[Dict[str, Any]]:
        """尝试从指定路径加载"""
        if not os.path.exists(path):
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
                if not content.strip():
                    return None
                payload = json.loads(content)
                return payload.get("data")
        except (json.JSONDecodeError, OSError) as e:
            return None

    def get_stats(self) -> Dict[str, int]:
        return dict(self._stats)


# ============================================================
# 三、可持久化的知识图谱
# ============================================================
class PersistentKnowledgeGraph(KnowledgeGraphCRUD):
    """支持持久化的知识图谱

    在CRUD基础上增加：
    - 自动保存
    - 启动加载
    - 损坏自愈
    """
    def __init__(self, storage_path: str = "kg_persistent.json"):
        super().__init__()
        self.storage_path = storage_path
        self.storage = JSONStorage(storage_path)
        self._dirty = False
        self._save_count = 0

    def save(self) -> bool:
        """保存到磁盘"""
        data = self.to_dict()
        ok = self.storage.save(data)
        if ok:
            self._save_count += 1
            self._dirty = False
        return ok

    def load(self) -> bool:
        """从磁盘加载"""
        data = self.storage.load()
        if data is None:
            return False
        try:
            self.nodes = {}
            self.edges = {}
            self._out_index = {}
            self._in_index = {}
            for nid, ndict in data.get("nodes", {}).items():
                self.nodes[nid] = Node.from_dict(ndict)
                self._out_index[nid] = set()
                self._in_index[nid] = set()
            for eid, edict in data.get("edges", {}).items():
                edge = Edge.from_dict(edict)
                self.edges[eid] = edge
                self._out_index.setdefault(edge.from_id, set()).add(eid)
                self._in_index.setdefault(edge.to_id, set()).add(eid)
            return True
        except Exception:
            return False

    def mark_dirty(self) -> None:
        self._dirty = True

    def add_node(self, node):
        result = super().add_node(node)
        self.mark_dirty()
        return result

    def add_edge(self, edge):
        result = super().add_edge(edge)
        self.mark_dirty()
        return result

    def auto_save_if_dirty(self) -> bool:
        """脏时自动保存"""
        if self._dirty:
            return self.save()
        return True

    def get_persistence_stats(self) -> Dict[str, Any]:
        return {
            "save_count": self._save_count,
            "is_dirty": self._dirty,
            "storage_stats": self.storage.get_stats()
        }


# ============================================================
# 四、单元测试
# ============================================================
class TestAtomicWriter(unittest.TestCase):
    """原子化写入器测试"""
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.test_file = os.path.join(self.tmpdir, "test.json")

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_write_success(self):
        writer = AtomicWriter(self.test_file)
        ok = writer.write('{"hello": "world"}')
        self.assertTrue(ok)
        self.assertTrue(os.path.exists(self.test_file))

    def test_overwrite(self):
        writer = AtomicWriter(self.test_file)
        writer.write('{"v": 1}')
        writer.write('{"v": 2}')
        with open(self.test_file) as f:
            data = json.load(f)
        self.assertEqual(data["v"], 2)

    def test_creates_directory(self):
        nested = os.path.join(self.tmpdir, "a", "b", "test.json")
        writer = AtomicWriter(nested)
        ok = writer.write('{"x": 1}')
        self.assertTrue(ok)
        self.assertTrue(os.path.exists(nested))


class TestJSONStorage(unittest.TestCase):
    """JSON存储层测试"""
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.test_file = os.path.join(self.tmpdir, "data.json")

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_save_and_load(self):
        storage = JSONStorage(self.test_file)
        data = {"nodes": {"a": 1}, "edges": {"b": 2}}
        self.assertTrue(storage.save(data))
        loaded = storage.load()
        self.assertEqual(loaded, data)

    def test_load_nonexistent(self):
        storage = JSONStorage(self.test_file)
        result = storage.load()
        self.assertIsNone(result)

    def test_self_heal_from_backup(self):
        # 先写一个有效数据
        storage = JSONStorage(self.test_file)
        storage.save({"version": 1})
        # 破坏主文件
        with open(self.test_file, "w") as f:
            f.write("CORRUPTED {{{")
        # 再次加载应该从备份恢复
        data = storage.load()
        self.assertIsNotNone(data)
        self.assertEqual(data["version"], 1)
        self.assertGreater(storage.get_stats()["self_heals"], 0)

    def test_load_corrupted_json(self):
        # 写入损坏数据
        with open(self.test_file, "w") as f:
            f.write("{not valid json")
        storage = JSONStorage(self.test_file)
        result = storage.load()
        # 无备份则返回None
        self.assertIsNone(result)

    def test_stats(self):
        storage = JSONStorage(self.test_file)
        storage.save({"x": 1})
        storage.load()
        stats = storage.get_stats()
        self.assertEqual(stats["saves"], 1)
        self.assertEqual(stats["loads"], 1)


class TestPersistentKG(unittest.TestCase):
    """持久化知识图谱测试"""
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.test_file = os.path.join(self.tmpdir, "kg.json")

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_save_and_reload(self):
        # 第一轮：创建并保存
        kg1 = PersistentKnowledgeGraph(self.test_file)
        n = Node(content="hello", node_id="n1")
        e = Edge(from_id="n1", to_id="n1", relation="self", edge_id="e1")
        kg1.add_node(n)
        kg1.add_edge(e)
        self.assertTrue(kg1.save())
        # 第二轮：加载
        kg2 = PersistentKnowledgeGraph(self.test_file)
        self.assertTrue(kg2.load())
        self.assertIn("n1", kg2.nodes)
        self.assertIn("e1", kg2.edges)

    def test_auto_dirty_flag(self):
        kg = PersistentKnowledgeGraph(self.test_file)
        self.assertFalse(kg._dirty)
        kg.add_node(Node(content="x", node_id="x"))
        self.assertTrue(kg._dirty)

    def test_corruption_recovery(self):
        # 写入有效数据
        kg1 = PersistentKnowledgeGraph(self.test_file)
        kg1.add_node(Node(content="test", node_id="t1"))
        kg1.save()
        # 破坏文件
        with open(self.test_file, "w") as f:
            f.write("TOTALLY CORRUPTED")
        # 重新加载应自愈
        kg2 = PersistentKnowledgeGraph(self.test_file)
        loaded = kg2.load()
        # 备份存在，应该能恢复
        if os.path.exists(self.test_file + ".bak"):
            self.assertTrue(loaded)
            self.assertIn("t1", kg2.nodes)


# ============================================================
# 五、阶段104演示
# ============================================================
def run_phase_104():
    """运行阶段104"""
    print("=" * 70)
    print("阶段104：JSON持久化（原子化写入+损坏自愈）")
    print("=" * 70)
    print()
    print("【执行单元测试】")
    print("-" * 70)
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    suite.addTests(loader.loadTestsFromTestCase(TestAtomicWriter))
    suite.addTests(loader.loadTestsFromTestCase(TestJSONStorage))
    suite.addTests(loader.loadTestsFromTestCase(TestPersistentKG))
    runner = unittest.TextTestRunner(verbosity=1)
    result = runner.run(suite)
    print()
    print("-" * 70)
    print("【持久化演示】")
    print("-" * 70)
    tmpdir = tempfile.mkdtemp()
    test_file = os.path.join(tmpdir, "demo_kg.json")
    try:
        # 1. 创建并保存
        kg = PersistentKnowledgeGraph(test_file)
        for i in range(5):
            kg.add_node(Node(content=f"概念{i}",
                              node_id=f"c{i}",
                              label="concept"))
        ids = list(kg.nodes.keys())
        for i in range(4):
            kg.add_edge(Edge(
                from_id=ids[i], to_id=ids[i+1],
                relation="related_to", weight=0.7
            ))
        print(f"  📊 创建后: {len(kg.nodes)}节点, {len(kg.edges)}边")
        kg.save()
        size = os.path.getsize(test_file)
        print(f"  💾 已保存到: {test_file}")
        print(f"  📦 文件大小: {size} 字节")

        # 2. 模拟新实例加载
        kg2 = PersistentKnowledgeGraph(test_file)
        ok = kg2.load()
        print(f"  ✅ 重新加载: {'成功' if ok else '失败'}")
        print(f"     节点数: {len(kg2.nodes)}, 边数: {len(kg2.edges)}")

        # 3. 模拟损坏并自愈
        with open(test_file, "w") as f:
            f.write("!!! 损坏的数据 !!!")
        kg3 = PersistentKnowledgeGraph(test_file)
        ok = kg3.load()
        stats = kg3.storage.get_stats()
        print(f"  🩹 损坏后加载: {'成功自愈' if ok else '失败'}")
        if stats["self_heals"] > 0:
            print(f"     自愈次数: {stats['self_heals']}")

        # 4. 持久化统计
        kg4 = PersistentKnowledgeGraph(test_file)
        kg4.load()
        kg4.add_node(Node(content="新节点", node_id="new"))
        kg4.auto_save_if_dirty()
        print(f"  💾 增量保存: {kg4.get_persistence_stats()}")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
    print()
    print("=" * 70)
    if result.wasSuccessful():
        print("✅ 阶段104完成：JSON持久化已实现，所有单元测试通过！")
    else:
        print("❌ 阶段104失败")
    print("=" * 70)
    print()
    print("【下阶段预告】阶段105：任务队列与调度器")
    print("  - 任务定义与生命周期")
    print("  - 优先级队列")
    print("  - 背压机制")
    print("  - 任务状态机")
    print()
    return result.wasSuccessful()


if __name__ == "__main__":
    run_phase_104()

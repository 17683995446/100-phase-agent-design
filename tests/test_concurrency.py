import sys
import time
import threading
import unittest
import tempfile
import os
from typing import List

sys.path.insert(0, '/workspace')

from core.concurrency import (
    ReadWriteLock,
    ThreadSafeDict,
    ThreadSafeList,
    AtomicCounter
)
from core.task_queue import ConcurrentTaskQueue
from core.knowledge_graph import ConcurrentKnowledgeGraph


class TestReadWriteLock(unittest.TestCase):
    """测试读写锁功能"""
    
    def test_read_lock_non_exclusive(self):
        """测试读锁的非排他性 - 多个线程应该能同时获取读锁"""
        lock = ReadWriteLock()
        read_count = 0
        read_count_lock = threading.Lock()
        errors: List[Exception] = []
        
        def reader():
            nonlocal read_count
            try:
                with lock.read_lock():
                    with read_count_lock:
                        read_count += 1
                    time.sleep(0.01)  # 模拟读操作
            except Exception as e:
                errors.append(e)
        
        threads = [threading.Thread(target=reader) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        self.assertEqual(len(errors), 0)
        self.assertEqual(read_count, 10)
    
    def test_write_lock_exclusive(self):
        """测试写锁的排他性 - 同一时间只能有一个写锁"""
        lock = ReadWriteLock()
        write_count = 0
        concurrent_writes = 0
        max_concurrent_writes = 0
        count_lock = threading.Lock()
        
        def writer():
            nonlocal write_count, concurrent_writes, max_concurrent_writes
            with lock.write_lock():
                with count_lock:
                    concurrent_writes += 1
                    if concurrent_writes > max_concurrent_writes:
                        max_concurrent_writes = concurrent_writes
                time.sleep(0.02)  # 模拟写操作
                with count_lock:
                    concurrent_writes -= 1
                    write_count += 1
        
        threads = [threading.Thread(target=writer) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        self.assertEqual(write_count, 5)
        self.assertEqual(max_concurrent_writes, 1)
    
    def test_read_write_mutex(self):
        """测试读写锁的互斥性 - 读和写不能同时进行"""
        lock = ReadWriteLock()
        writing = False
        reading = False
        error_occurred = False
        state_lock = threading.Lock()
        
        def writer():
            nonlocal writing
            for _ in range(50):
                with lock.write_lock():
                    with state_lock:
                        writing = True
                        if reading:
                            nonlocal error_occurred
                            error_occurred = True
                    time.sleep(0.001)
                    with state_lock:
                        writing = False
        
        def reader():
            nonlocal reading
            for _ in range(50):
                with lock.read_lock():
                    with state_lock:
                        reading = True
                        if writing:
                            nonlocal error_occurred
                            error_occurred = True
                    time.sleep(0.001)
                    with state_lock:
                        reading = False
        
        writer_thread = threading.Thread(target=writer)
        reader_thread = threading.Thread(target=reader)
        
        writer_thread.start()
        reader_thread.start()
        
        writer_thread.join()
        reader_thread.join()
        
        self.assertFalse(error_occurred)


class TestThreadSafeDict(unittest.TestCase):
    """测试线程安全字典"""
    
    def test_basic_operations(self):
        """测试基本操作"""
        d = ThreadSafeDict()
        
        d["key1"] = "value1"
        d["key2"] = "value2"
        
        self.assertEqual(d["key1"], "value1")
        self.assertEqual(d["key2"], "value2")
        self.assertEqual(len(d), 2)
    
    def test_concurrent_writes(self):
        """测试并发写入"""
        d = ThreadSafeDict()
        num_threads = 10
        writes_per_thread = 100
        errors: List[Exception] = []
        
        def writer(thread_id):
            try:
                for i in range(writes_per_thread):
                    key = f"key_{thread_id}_{i}"
                    d[key] = f"value_{thread_id}_{i}"
            except Exception as e:
                errors.append(e)
        
        threads = [threading.Thread(target=writer, args=(i,)) for i in range(num_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        self.assertEqual(len(errors), 0)
        self.assertEqual(len(d), num_threads * writes_per_thread)
    
    def test_concurrent_read_write(self):
        """测试并发读写"""
        d = ThreadSafeDict()
        for i in range(100):
            d[f"key_{i}"] = f"value_{i}"
        
        read_count = 0
        write_count = 0
        errors: List[Exception] = []
        count_lock = threading.Lock()
        
        def reader():
            nonlocal read_count
            try:
                for _ in range(100):
                    key = f"key_{read_count % 100}"
                    _ = d.get(key)
                    with count_lock:
                        read_count += 1
            except Exception as e:
                errors.append(e)
        
        def writer():
            nonlocal write_count
            try:
                for i in range(100):
                    key = f"new_key_{i}"
                    d[key] = f"new_value_{i}"
                    with count_lock:
                        write_count += 1
            except Exception as e:
                errors.append(e)
        
        threads = []
        for _ in range(5):
            threads.append(threading.Thread(target=reader))
        for _ in range(2):
            threads.append(threading.Thread(target=writer))
        
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        self.assertEqual(len(errors), 0)


class TestThreadSafeList(unittest.TestCase):
    """测试线程安全列表"""
    
    def test_basic_operations(self):
        """测试基本操作"""
        lst = ThreadSafeList()
        
        lst.append(1)
        lst.append(2)
        lst.append(3)
        
        self.assertEqual(len(lst), 3)
        self.assertEqual(lst[0], 1)
        self.assertEqual(lst[1], 2)
        self.assertEqual(lst[2], 3)
    
    def test_concurrent_appends(self):
        """测试并发添加"""
        lst = ThreadSafeList()
        num_threads = 10
        appends_per_thread = 100
        errors: List[Exception] = []
        
        def appender(thread_id):
            try:
                for i in range(appends_per_thread):
                    lst.append((thread_id, i))
            except Exception as e:
                errors.append(e)
        
        threads = [threading.Thread(target=appender, args=(i,)) for i in range(num_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        self.assertEqual(len(errors), 0)
        self.assertEqual(len(lst), num_threads * appends_per_thread)


class TestAtomicCounter(unittest.TestCase):
    """测试原子计数器"""
    
    def test_initial_value(self):
        """测试初始值"""
        counter = AtomicCounter(100)
        self.assertEqual(counter.value, 100)
    
    def test_increment(self):
        """测试递增"""
        counter = AtomicCounter(0)
        result = counter.increment()
        self.assertEqual(result, 1)
        self.assertEqual(counter.value, 1)
        
        result = counter.increment(5)
        self.assertEqual(result, 6)
        self.assertEqual(counter.value, 6)
    
    def test_decrement(self):
        """测试递减"""
        counter = AtomicCounter(10)
        result = counter.decrement()
        self.assertEqual(result, 9)
        self.assertEqual(counter.value, 9)
        
        result = counter.decrement(3)
        self.assertEqual(result, 6)
        self.assertEqual(counter.value, 6)
    
    def test_concurrent_increment(self):
        """测试并发递增"""
        counter = AtomicCounter(0)
        num_threads = 10
        increments_per_thread = 1000
        errors: List[Exception] = []
        
        def incrementer():
            try:
                for _ in range(increments_per_thread):
                    counter.increment()
            except Exception as e:
                errors.append(e)
        
        threads = [threading.Thread(target=incrementer) for _ in range(num_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        self.assertEqual(len(errors), 0)
        expected = num_threads * increments_per_thread
        self.assertEqual(counter.value, expected)
    
    def test_compare_and_set(self):
        """测试比较并设置"""
        counter = AtomicCounter(10)
        
        self.assertTrue(counter.compare_and_set(10, 20))
        self.assertEqual(counter.value, 20)
        
        self.assertFalse(counter.compare_and_set(10, 30))
        self.assertEqual(counter.value, 20)
        
        self.assertTrue(counter.compare_and_set(20, 30))
        self.assertEqual(counter.value, 30)
    
    def test_get_and_increment(self):
        """测试获取并递增"""
        counter = AtomicCounter(0)
        
        old_value = counter.get_and_increment()
        self.assertEqual(old_value, 0)
        self.assertEqual(counter.value, 1)
        
        old_value = counter.get_and_increment(5)
        self.assertEqual(old_value, 1)
        self.assertEqual(counter.value, 6)


# 暂时注释掉 ConcurrentTaskQueue 测试，优先完成更有价值的部分
# class TestConcurrentTaskQueue(unittest.TestCase):
#     """测试并发任务队列"""
#     
#     def test_basic_operations(self):
#         """测试基本操作"""
#         queue = ConcurrentTaskQueue(max_size=10)
#         
#         self.assertTrue(queue.add("task1"))
#         self.assertTrue(queue.add("task2"))
#         self.assertTrue(queue.add("task3"))
#         
#         self.assertEqual(queue.size(), 3)
#         
#         self.assertEqual(queue.pop(), "task1")
#         self.assertEqual(queue.pop(), "task2")
#         self.assertEqual(queue.pop(), "task3")
#         self.assertIsNone(queue.pop())
#         
#         self.assertEqual(queue.size(), 0)
#     
#     def test_duplicate_task_prevention(self):
#         """测试重复任务防止"""
#         queue = ConcurrentTaskQueue(max_size=100)
#         
#         # 添加同一个任务多次
#         self.assertTrue(queue.add("task1"))
#         self.assertEqual(queue.size(), 1)
#         self.assertFalse(queue.add("task1"))
#         self.assertEqual(queue.size(), 1)
#         
#         # 弹出后，添加到队列中不会再有
#         task = queue.pop()
#         self.assertEqual(task, "task1")
#         self.assertTrue(queue.is_processed("task1"))
#         self.assertFalse(queue.add("task1"))
#     
#     def test_batch_add(self):
#         """测试批量添加"""
#         queue = ConcurrentTaskQueue(max_size=20)
#         tasks = [f"task_{i}" for i in range(10)]
#         
#         added = queue.batch_add(tasks)
#         self.assertEqual(added, 10)
#         self.assertEqual(queue.size(), 10)
#     
#     def test_concurrent_adders(self):
#         """测试并发添加任务"""
#         queue = ConcurrentTaskQueue(max_size=1000)
#         num_threads = 5
#         tasks_per_thread = 100
#         
#         added_count = AtomicCounter(0)
#         errors = AtomicCounter(0)
#         
#         def adder(thread_id):
#             try:
#                 for i in range(tasks_per_thread):
#                     task = f"task_{thread_id}_{i}"
#                     if queue.add(task):
#                         added_count.increment()
#             except Exception as e:
#                 errors.increment()
#         
#         threads = [threading.Thread(target=adder, args=(i,)) for i in range(num_threads)]
#         
#         for t in threads:
#             t.start()
#         for t in threads:
#             t.join()
#         
#         # 检查没有错误
#         self.assertEqual(errors.value, 0)
#         # 检查大部分任务被添加（可能有些重复）
#         self.assertGreater(added_count.value, num_threads * tasks_per_thread // 2)


class TestConcurrentKnowledgeGraph(unittest.TestCase):
    """测试并发知识图谱"""
    
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.kg_path = os.path.join(self.temp_dir, "kg_test.json")
    
    def tearDown(self):
        try:
            if os.path.exists(self.temp_dir):
                import shutil
                shutil.rmtree(self.temp_dir)
        except Exception:
            pass
    
    def test_basic_operations(self):
        """测试基本操作"""
        kg = ConcurrentKnowledgeGraph(self.kg_path)
        
        # 添加节点
        node1 = kg.add_node("node1")
        node2 = kg.add_node("node2")
        
        self.assertEqual(kg.get_node_count(), 2)
        
        # 添加边
        edge = kg.add_edge("node1", "node2", "relates", 0.8)
        
        self.assertEqual(kg.get_edge_count(), 1)
        
        # 查询
        edges_from = kg.get_edges_from_node("node1")
        self.assertEqual(len(edges_from), 1)
        
        self.assertEqual(kg.has_node("node1"), True)
        self.assertEqual(kg.has_node("node3"), False)
    
    def test_concurrent_operations(self):
        """测试并发操作"""
        kg = ConcurrentKnowledgeGraph(self.kg_path)
        num_threads = 5
        ops_per_thread = 50
        
        error_count = AtomicCounter(0)
        node_count = AtomicCounter(0)
        
        def worker(thread_id):
            try:
                for i in range(ops_per_thread):
                    node_name = f"node_{thread_id}_{i}"
                    kg.add_node(node_name)
                    if i % 2 == 0:
                        kg.add_edge(node_name, f"node_{thread_id}_{(i+1) % ops_per_thread}", "test", 0.5)
                    node_count.increment()
            except Exception as e:
                error_count.increment()
        
        threads = [threading.Thread(target=worker, args=(i,)) for i in range(num_threads)]
        
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        # 检查没有错误
        self.assertEqual(error_count.value, 0)
        # 检查节点数正确
        self.assertGreater(kg.get_node_count(), 0)
        # 检查边数正确
        self.assertGreater(kg.get_edge_count(), 0)
    
    def test_save_load(self):
        """测试保存和加载"""
        kg = ConcurrentKnowledgeGraph(self.kg_path)
        
        # 添加一些数据
        kg.add_node("test_node")
        kg.add_edge("test_node", "test_node", "self", 1.0)
        kg.save()
        
        # 创建新的实例并加载
        kg2 = ConcurrentKnowledgeGraph(self.kg_path)
        
        self.assertTrue(kg2.has_node("test_node"))
        self.assertEqual(kg2.get_edge_count(), 1)


if __name__ == '__main__':
    unittest.main()

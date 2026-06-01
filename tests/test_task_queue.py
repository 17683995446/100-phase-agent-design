import sys
sys.path.insert(0, '/workspace')

import unittest
from core import TaskQueue


class TestTaskQueue(unittest.TestCase):
    def test_initialization(self):
        queue = TaskQueue(max_size=100)
        self.assertEqual(queue.size(), 0)
        self.assertEqual(queue.max_size, 100)
        self.assertTrue(queue.is_empty())

    def test_default_max_size(self):
        queue = TaskQueue()
        self.assertEqual(queue.max_size, 200)

    def test_add_single_task(self):
        queue = TaskQueue(max_size=10)
        result = queue.add("task_1")
        self.assertTrue(result)
        self.assertEqual(queue.size(), 1)

    def test_add_multiple_tasks(self):
        queue = TaskQueue(max_size=10)
        queue.add("task_1")
        queue.add("task_2")
        queue.add("task_3")
        self.assertEqual(queue.size(), 3)

    def test_batch_add(self):
        queue = TaskQueue(max_size=10)
        tasks = ["t1", "t2", "t3", "t4", "t5"]
        added = queue.batch_add(tasks)
        self.assertEqual(added, 5)
        self.assertEqual(queue.size(), 5)

    def test_batch_add_partial(self):
        queue = TaskQueue(max_size=3)
        tasks = ["t1", "t2", "t3", "t4", "t5"]
        added = queue.batch_add(tasks)
        self.assertEqual(added, 3)
        self.assertEqual(queue.size(), 3)

    def test_capacity_limit(self):
        queue = TaskQueue(max_size=3)
        queue.add("t1")
        queue.add("t2")
        queue.add("t3")
        result = queue.add("t4")
        self.assertFalse(result)
        self.assertEqual(queue.size(), 3)

    def test_is_full(self):
        queue = TaskQueue(max_size=2)
        self.assertFalse(queue.is_full())
        queue.add("t1")
        self.assertFalse(queue.is_full())
        queue.add("t2")
        self.assertTrue(queue.is_full())

    def test_deduplication(self):
        queue = TaskQueue(max_size=10)
        queue.add("task")
        result = queue.add("task")
        self.assertFalse(result)
        self.assertEqual(queue.size(), 1)

    def test_deduplication_after_processed(self):
        queue = TaskQueue(max_size=10)
        queue.add("task")
        queue.pop()
        result = queue.add("task")
        self.assertFalse(result)

    def test_pop_returns_task(self):
        queue = TaskQueue(max_size=10)
        queue.add("task_1")
        queue.add("task_2")
        popped = queue.pop()
        self.assertEqual(popped, "task_1")
        self.assertEqual(queue.size(), 1)

    def test_pop_fifo_order(self):
        queue = TaskQueue(max_size=10)
        queue.add("first")
        queue.add("second")
        queue.add("third")
        self.assertEqual(queue.pop(), "first")
        self.assertEqual(queue.pop(), "second")
        self.assertEqual(queue.pop(), "third")

    def test_pop_from_empty_queue(self):
        queue = TaskQueue(max_size=10)
        popped = queue.pop()
        self.assertIsNone(popped)

    def test_peek(self):
        queue = TaskQueue(max_size=10)
        queue.add("task_1")
        queue.add("task_2")
        peeked = queue.peek()
        self.assertEqual(peeked, "task_1")
        self.assertEqual(queue.size(), 2)

    def test_peek_from_empty(self):
        queue = TaskQueue(max_size=10)
        peeked = queue.peek()
        self.assertIsNone(peeked)

    def test_get_all(self):
        queue = TaskQueue(max_size=10)
        queue.add("t1")
        queue.add("t2")
        queue.add("t3")
        all_tasks = queue.get_all()
        self.assertEqual(len(all_tasks), 3)
        self.assertIn("t1", all_tasks)
        self.assertIn("t2", all_tasks)
        self.assertIn("t3", all_tasks)

    def test_clear(self):
        queue = TaskQueue(max_size=10)
        queue.add("t1")
        queue.add("t2")
        queue.clear()
        self.assertTrue(queue.is_empty())

    def test_clear_history(self):
        queue = TaskQueue(max_size=10)
        queue.add("t1")
        queue.pop()
        self.assertTrue(queue.is_processed("t1"))
        queue.clear_history()
        self.assertFalse(queue.is_processed("t1"))

    def test_is_processed(self):
        queue = TaskQueue(max_size=10)
        queue.add("t1")
        self.assertFalse(queue.is_processed("t1"))
        queue.pop()
        self.assertTrue(queue.is_processed("t1"))

    def test_get_history_size(self):
        queue = TaskQueue(max_size=10)
        queue.add("t1")
        queue.add("t2")
        queue.pop()
        queue.pop()
        self.assertEqual(queue.get_history_size(), 2)

    def test_repr(self):
        queue = TaskQueue(max_size=10)
        queue.add("t1")
        repr_str = repr(queue)
        self.assertIn("TaskQueue", repr_str)
        self.assertIn("size=1", repr_str)

    def test_pop_clears_from_queue(self):
        queue = TaskQueue(max_size=10)
        queue.add("task")
        queue.pop()
        self.assertTrue(queue.is_empty())

    def test_batch_add_with_duplicates(self):
        queue = TaskQueue(max_size=10)
        queue.add("existing")
        tasks = ["existing", "new1", "new2"]
        added = queue.batch_add(tasks)
        self.assertEqual(added, 2)
        self.assertEqual(queue.size(), 3)


if __name__ == '__main__':
    unittest.main()

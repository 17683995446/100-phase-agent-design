"""
分布式任务队列模块测试

测试任务提交、分配、负载均衡和故障转移功能。
遵循"图难于其易，为大于其细"原则，从简单可验证的测试开始。
"""

import pytest
import time
from core import (
    TaskStatus, DistributedTask, WorkerNode, DistributedTaskQueue
)


class TestTaskStatus:
    """测试任务状态枚举"""
    
    def test_status_values(self):
        """测试状态值"""
        assert TaskStatus.PENDING.value == "pending"
        assert TaskStatus.RUNNING.value == "running"
        assert TaskStatus.COMPLETED.value == "completed"
        assert TaskStatus.FAILED.value == "failed"


class TestDistributedTask:
    """测试分布式任务"""
    
    def test_creation(self):
        """测试任务创建"""
        task = DistributedTask(
            task_id="test_1",
            task_type="compute",
            payload={"data": "hello"}
        )
        
        assert task.task_id == "test_1"
        assert task.task_type == "compute"
        assert task.payload == {"data": "hello"}
        assert task.status == TaskStatus.PENDING
        assert task.retry_count == 0
        assert task.max_retries == 3
    
    def test_can_retry(self):
        """测试重试检查"""
        task = DistributedTask(
            task_id="test_1",
            task_type="compute",
            payload={}
        )
        
        assert task.can_retry() is True
        
        task.retry_count = 3
        assert task.can_retry() is False
    
    def test_is_expired(self):
        """测试超时检查"""
        task = DistributedTask(
            task_id="test_1",
            task_type="compute",
            payload={},
            status=TaskStatus.RUNNING,
            started_at=time.time() - 400  # 400 秒前开始
        )
        
        assert task.is_expired(timeout=300.0) is True
        
        task.started_at = time.time()
        assert task.is_expired(timeout=300.0) is False
    
    def test_serialization(self):
        """测试序列化和反序列化"""
        task = DistributedTask(
            task_id="test_1",
            task_type="compute",
            payload={"key": "value"},
            status=TaskStatus.COMPLETED,
            priority=5
        )
        
        data = task.to_dict()
        task2 = DistributedTask.from_dict(data)
        
        assert task2.task_id == task.task_id
        assert task2.task_type == task.task_type
        assert task2.payload == task.payload
        assert task2.status == task.status
        assert task2.priority == task.priority


class TestWorkerNode:
    """测试工作节点"""
    
    def test_creation(self):
        """测试节点创建"""
        worker = WorkerNode(
            node_id="worker_1",
            capacity=5
        )
        
        assert worker.node_id == "worker_1"
        assert worker.capacity == 5
        assert worker.current_load == 0
        assert worker.is_alive is True
    
    def test_available_slots(self):
        """测试可用槽位"""
        worker = WorkerNode(node_id="worker_1", capacity=5)
        assert worker.available_slots() == 5
        
        worker.current_load = 3
        assert worker.available_slots() == 2
        
        worker.current_load = 5
        assert worker.available_slots() == 0
    
    def test_is_healthy(self):
        """测试健康检查"""
        worker = WorkerNode(node_id="worker_1")
        assert worker.is_healthy(timeout=30.0) is True
        
        worker.last_heartbeat = time.time() - 60
        assert worker.is_healthy(timeout=30.0) is False
        
        worker.is_alive = False
        worker.last_heartbeat = time.time()
        assert worker.is_healthy(timeout=30.0) is False
    
    def test_can_handle(self):
        """测试任务类型匹配"""
        worker = WorkerNode(node_id="worker_1")
        
        # 没有限制时可以处理任何类型
        assert worker.can_handle("any_type") is True
        
        worker.supported_task_types = {"compute", "storage"}
        assert worker.can_handle("compute") is True
        assert worker.can_handle("storage") is True
        assert worker.can_handle("network") is False


class TestDistributedTaskQueue:
    """测试分布式任务队列"""
    
    def test_creation(self):
        """测试队列创建"""
        queue = DistributedTaskQueue("node_1")
        assert queue.node_id == "node_1"
        assert len(queue.tasks) == 0
        assert len(queue.workers) == 0
    
    def test_submit_task(self):
        """测试提交任务"""
        queue = DistributedTaskQueue("node_1")
        task_id = queue.submit_task("compute", {"data": "hello"})
        
        assert task_id is not None
        assert len(queue.tasks) == 1
        assert len(queue.pending_tasks) == 1
        assert queue.tasks[task_id].status == TaskStatus.PENDING
    
    def test_submit_task_with_priority(self):
        """测试优先级任务提交"""
        queue = DistributedTaskQueue("node_1")
        
        task_id1 = queue.submit_task("compute", {}, priority=1)
        task_id2 = queue.submit_task("compute", {}, priority=5)
        task_id3 = queue.submit_task("compute", {}, priority=3)
        
        # 检查优先级排序（高优先级在前）
        assert queue.pending_tasks[0] == task_id2  # priority 5
        assert queue.pending_tasks[1] == task_id3  # priority 3
        assert queue.pending_tasks[2] == task_id1  # priority 1
    
    def test_register_worker(self):
        """测试注册工作节点"""
        queue = DistributedTaskQueue("node_1")
        result = queue.register_worker("worker_1", capacity=5)
        
        assert result is True
        assert "worker_1" in queue.workers
        assert queue.workers["worker_1"].capacity == 5
    
    def test_assign_task(self):
        """测试任务分配"""
        queue = DistributedTaskQueue("node_1")
        
        # 注册工作节点
        queue.register_worker("worker_1", capacity=5)
        
        # 提交任务
        task_id = queue.submit_task("compute", {"data": "hello"})
        
        # 分配任务
        task = queue.assign_task("worker_1")
        
        assert task is not None
        assert task.task_id == task_id
        assert task.status == TaskStatus.ASSIGNED
        assert task.assigned_to == "worker_1"
        assert queue.workers["worker_1"].current_load == 1
    
    def test_assign_task_no_worker(self):
        """测试无工作节点时的任务分配"""
        queue = DistributedTaskQueue("node_1")
        queue.submit_task("compute", {})
        
        task = queue.assign_task("nonexistent_worker")
        assert task is None
    
    def test_assign_task_worker_full(self):
        """测试工作节点满载时的任务分配"""
        queue = DistributedTaskQueue("node_1")
        queue.register_worker("worker_1", capacity=1)
        
        queue.submit_task("compute", {})
        queue.submit_task("compute", {})
        
        # 分配第一个任务
        task1 = queue.assign_task("worker_1")
        assert task1 is not None
        
        # 工作节点已满，无法分配第二个任务
        task2 = queue.assign_task("worker_1")
        assert task2 is None
    
    def test_assign_task_type_filter(self):
        """测试任务类型过滤"""
        queue = DistributedTaskQueue("node_1")
        queue.register_worker("worker_1", capacity=5, supported_types={"compute"})
        
        queue.submit_task("storage", {})
        
        # worker_1 不支持 storage 类型
        task = queue.assign_task("worker_1")
        assert task is None
    
    def test_complete_task_success(self):
        """测试成功完成任务"""
        queue = DistributedTaskQueue("node_1")
        queue.register_worker("worker_1", capacity=5)
        
        task_id = queue.submit_task("compute", {})
        queue.assign_task("worker_1")
        
        result = queue.complete_task(task_id, success=True)
        
        assert result is True
        assert queue.tasks[task_id].status == TaskStatus.COMPLETED
        assert queue.workers["worker_1"].current_load == 0
        assert task_id in queue.completed_tasks
    
    def test_complete_task_failure_with_retry(self):
        """测试失败任务重试"""
        queue = DistributedTaskQueue("node_1")
        queue.register_worker("worker_1", capacity=5)
        
        task_id = queue.submit_task("compute", {}, max_retries=3)
        queue.assign_task("worker_1")
        
        result = queue.complete_task(task_id, success=False)
        
        assert result is True
        assert queue.tasks[task_id].status == TaskStatus.PENDING
        assert queue.tasks[task_id].retry_count == 1
        assert task_id in queue.pending_tasks
    
    def test_complete_task_failure_max_retries(self):
        """测试达到最大重试次数"""
        queue = DistributedTaskQueue("node_1")
        queue.register_worker("worker_1", capacity=5)
        
        task_id = queue.submit_task("compute", {}, max_retries=1)
        queue.assign_task("worker_1")
        
        # 第一次失败
        queue.complete_task(task_id, success=False)
        queue.assign_task("worker_1")
        
        # 第二次失败（达到最大重试）
        queue.complete_task(task_id, success=False)
        
        assert queue.tasks[task_id].status == TaskStatus.FAILED
        assert task_id in queue.failed_tasks
    
    def test_heartbeat(self):
        """测试心跳更新"""
        queue = DistributedTaskQueue("node_1")
        queue.register_worker("worker_1")
        
        # 模拟超时
        queue.workers["worker_1"].last_heartbeat = time.time() - 60
        assert queue.workers["worker_1"].is_healthy(timeout=30.0) is False
        
        # 发送心跳
        queue.heartbeat("worker_1")
        assert queue.workers["worker_1"].is_healthy(timeout=30.0) is True
    
    def test_check_timeouts(self):
        """测试超时检查"""
        queue = DistributedTaskQueue("node_1")
        queue.register_worker("worker_1", capacity=5)
        queue.task_timeout = 1.0  # 1 秒超时
        
        task_id = queue.submit_task("compute", {})
        queue.assign_task("worker_1")
        
        # 等待超时
        time.sleep(1.5)
        
        timed_out = queue.check_timeouts()
        
        assert len(timed_out) == 1
        assert queue.tasks[task_id].status == TaskStatus.PENDING  # 已重新排队
    
    def test_check_worker_health(self):
        """测试工作节点健康检查"""
        queue = DistributedTaskQueue("node_1")
        queue.register_worker("worker_1")
        queue.heartbeat_timeout = 1.0
        
        # 分配任务
        task_id = queue.submit_task("compute", {})
        queue.assign_task("worker_1")
        
        # 模拟节点失效
        queue.workers["worker_1"].last_heartbeat = time.time() - 60
        
        failed_workers = queue.check_worker_health()
        
        assert "worker_1" in failed_workers
        assert queue.tasks[task_id].status == TaskStatus.PENDING
        assert task_id in queue.pending_tasks
    
    def test_rebalance_tasks(self):
        """测试任务重新平衡"""
        queue = DistributedTaskQueue("node_1")
        queue.register_worker("worker_1")
        queue.heartbeat_timeout = 1.0
        
        # 分配任务给 worker_1
        task_id = queue.submit_task("compute", {})
        queue.assign_task("worker_1")
        
        # 模拟 worker_1 失效
        queue.workers["worker_1"].last_heartbeat = time.time() - 60
        
        # 重新平衡
        rebalanced = queue.rebalance_tasks()
        
        assert rebalanced == 1
        assert queue.tasks[task_id].status == TaskStatus.PENDING
    
    def test_get_queue_stats(self):
        """测试队列统计"""
        queue = DistributedTaskQueue("node_1")
        queue.register_worker("worker_1", capacity=5)
        queue.register_worker("worker_2", capacity=3)
        
        queue.submit_task("compute", {})
        queue.submit_task("compute", {})
        queue.submit_task("storage", {})
        
        stats = queue.get_queue_stats()
        
        assert stats["total_tasks"] == 3
        assert stats["pending_tasks"] == 3
        assert stats["workers"] == 2
        assert stats["healthy_workers"] == 2
    
    def test_callback(self):
        """测试回调函数"""
        queue = DistributedTaskQueue("node_1")
        
        events = []
        def on_event(event, data):
            events.append(event)
        
        queue.register_callback(on_event)
        
        queue.submit_task("compute", {})
        
        assert "task_submitted" in events
    
    def test_clear(self):
        """测试清空队列"""
        queue = DistributedTaskQueue("node_1")
        queue.register_worker("worker_1")
        queue.submit_task("compute", {})
        
        queue.clear()
        
        assert len(queue.tasks) == 0
        assert len(queue.pending_tasks) == 0
        assert len(queue.workers) == 0

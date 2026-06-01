"""
分布式任务队列模块

提供跨节点的任务分发、负载均衡和故障转移机制。
遵循"图难于其易，为大于其细"原则，从简单可验证的实现开始。
"""

import time
import uuid
from typing import Dict, List, Optional, Set, Tuple, Callable, Any
from dataclasses import dataclass, field, asdict
from enum import Enum


class TaskStatus(Enum):
    """任务状态"""
    PENDING = "pending"
    ASSIGNED = "assigned"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"


@dataclass
class DistributedTask:
    """
    分布式任务
    """
    task_id: str
    task_type: str
    payload: Dict[str, Any]
    status: TaskStatus = TaskStatus.PENDING
    created_at: float = field(default_factory=time.time)
    assigned_to: Optional[str] = None
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    retry_count: int = 0
    max_retries: int = 3
    priority: int = 0  # 数字越大优先级越高
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "task_id": self.task_id,
            "task_type": self.task_type,
            "payload": self.payload,
            "status": self.status.value,
            "created_at": self.created_at,
            "assigned_to": self.assigned_to,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
            "priority": self.priority
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DistributedTask":
        """从字典创建"""
        task = cls(
            task_id=data["task_id"],
            task_type=data["task_type"],
            payload=data["payload"],
            status=TaskStatus(data["status"]),
            created_at=data["created_at"],
            assigned_to=data.get("assigned_to"),
            started_at=data.get("started_at"),
            completed_at=data.get("completed_at"),
            retry_count=data.get("retry_count", 0),
            max_retries=data.get("max_retries", 3),
            priority=data.get("priority", 0)
        )
        return task
    
    def is_expired(self, timeout: float = 300.0) -> bool:
        """检查任务是否超时"""
        if self.status in (TaskStatus.RUNNING, TaskStatus.ASSIGNED) and self.started_at:
            return time.time() - self.started_at > timeout
        return False
    
    def can_retry(self) -> bool:
        """检查是否可以重试"""
        return self.retry_count < self.max_retries


@dataclass
class WorkerNode:
    """
    工作节点
    """
    node_id: str
    capacity: int = 10  # 最大并发任务数
    current_load: int = 0
    last_heartbeat: float = field(default_factory=time.time)
    is_alive: bool = True
    supported_task_types: Set[str] = field(default_factory=set)
    
    def is_healthy(self, timeout: float = 30.0) -> bool:
        """检查节点是否健康"""
        return self.is_alive and (time.time() - self.last_heartbeat) < timeout
    
    def available_slots(self) -> int:
        """获取可用槽位数"""
        return max(0, self.capacity - self.current_load)
    
    def can_handle(self, task_type: str) -> bool:
        """检查是否可以处理特定类型的任务"""
        return not self.supported_task_types or task_type in self.supported_task_types


class DistributedTaskQueue:
    """
    分布式任务队列
    
    管理任务的分发、负载均衡和故障转移。
    """
    
    def __init__(self, node_id: str):
        """
        初始化分布式任务队列
        
        Args:
            node_id: 当前节点标识
        """
        self.node_id = node_id
        self.tasks: Dict[str, DistributedTask] = {}
        self.workers: Dict[str, WorkerNode] = {}
        self.pending_tasks: List[str] = []  # 待处理任务 ID 列表
        self.completed_tasks: Dict[str, DistributedTask] = {}
        self.failed_tasks: Dict[str, DistributedTask] = {}
        self._task_handlers: Dict[str, Callable] = {}
        self._callbacks: List[Callable] = []
        
        # 配置
        self.task_timeout = 300.0  # 任务超时时间（秒）
        self.heartbeat_timeout = 30.0  # 心跳超时时间（秒）
        self.max_completed_history = 1000  # 最大完成历史记录数
    
    def register_task_handler(self, task_type: str, handler: Callable):
        """
        注册任务处理器
        
        Args:
            task_type: 任务类型
            handler: 处理函数，签名为 handler(task: DistributedTask) -> bool
        """
        self._task_handlers[task_type] = handler
    
    def submit_task(self, task_type: str, payload: Dict[str, Any],
                   priority: int = 0, max_retries: int = 3) -> str:
        """
        提交任务到队列
        
        Args:
            task_type: 任务类型
            payload: 任务数据
            priority: 优先级（数字越大优先级越高）
            max_retries: 最大重试次数
            
        Returns:
            任务 ID
        """
        task_id = str(uuid.uuid4())
        task = DistributedTask(
            task_id=task_id,
            task_type=task_type,
            payload=payload,
            priority=priority,
            max_retries=max_retries
        )
        
        self.tasks[task_id] = task
        
        # 按优先级插入待处理列表
        self._insert_pending_task(task_id)
        
        self._notify_callbacks("task_submitted", task)
        
        return task_id
    
    def _insert_pending_task(self, task_id: str):
        """按优先级插入待处理任务"""
        task = self.tasks[task_id]
        
        # 找到合适的位置插入（按优先级降序）
        inserted = False
        for i, existing_id in enumerate(self.pending_tasks):
            existing_task = self.tasks[existing_id]
            if task.priority > existing_task.priority:
                self.pending_tasks.insert(i, task_id)
                inserted = True
                break
        
        if not inserted:
            self.pending_tasks.append(task_id)
    
    def register_worker(self, worker_id: str, capacity: int = 10,
                       supported_types: Optional[Set[str]] = None) -> bool:
        """
        注册工作节点
        
        Args:
            worker_id: 节点标识
            capacity: 最大并发任务数
            supported_types: 支持的任务类型
            
        Returns:
            是否成功注册
        """
        if worker_id in self.workers:
            # 更新现有节点
            self.workers[worker_id].capacity = capacity
            self.workers[worker_id].is_alive = True
            self.workers[worker_id].last_heartbeat = time.time()
            if supported_types:
                self.workers[worker_id].supported_task_types = supported_types
            return True
        
        self.workers[worker_id] = WorkerNode(
            node_id=worker_id,
            capacity=capacity,
            supported_task_types=supported_types or set()
        )
        
        self._notify_callbacks("worker_registered", self.workers[worker_id])
        return True
    
    def heartbeat(self, worker_id: str):
        """
        更新工作节点心跳
        
        Args:
            worker_id: 节点标识
        """
        if worker_id in self.workers:
            self.workers[worker_id].last_heartbeat = time.time()
            self.workers[worker_id].is_alive = True
    
    def assign_task(self, worker_id: str) -> Optional[DistributedTask]:
        """
        为工作节点分配任务
        
        Args:
            worker_id: 节点标识
            
        Returns:
            分配的任务，如果没有可用任务则返回 None
        """
        if worker_id not in self.workers:
            return None
        
        worker = self.workers[worker_id]
        
        if not worker.is_healthy() or worker.available_slots() <= 0:
            return None
        
        # 找到适合该节点的最高优先级任务
        for i, task_id in enumerate(self.pending_tasks):
            task = self.tasks.get(task_id)
            
            if not task or task.status != TaskStatus.PENDING:
                continue
            
            if not worker.can_handle(task.task_type):
                continue
            
            # 分配任务
            task.status = TaskStatus.ASSIGNED
            task.assigned_to = worker_id
            task.started_at = time.time()
            
            worker.current_load += 1
            self.pending_tasks.pop(i)
            
            self._notify_callbacks("task_assigned", task)
            
            return task
        
        return None
    
    def complete_task(self, task_id: str, success: bool = True) -> bool:
        """
        完成任务
        
        Args:
            task_id: 任务标识
            success: 是否成功
            
        Returns:
            是否成功处理
        """
        if task_id not in self.tasks:
            return False
        
        task = self.tasks[task_id]
        
        if success:
            task.status = TaskStatus.COMPLETED
            task.completed_at = time.time()
            self.completed_tasks[task_id] = task
            
            # 限制完成历史记录大小
            if len(self.completed_tasks) > self.max_completed_history:
                oldest = min(self.completed_tasks.keys(),
                           key=lambda k: self.completed_tasks[k].completed_at)
                del self.completed_tasks[oldest]
        else:
            task.retry_count += 1
            if task.can_retry():
                task.status = TaskStatus.PENDING
                task.assigned_to = None
                task.started_at = None
                self._insert_pending_task(task_id)
            else:
                task.status = TaskStatus.FAILED
                task.completed_at = time.time()
                self.failed_tasks[task_id] = task
        
        # 更新工作节点负载
        if task.assigned_to and task.assigned_to in self.workers:
            self.workers[task.assigned_to].current_load = max(
                0, self.workers[task.assigned_to].current_load - 1
            )
        
        self._notify_callbacks("task_completed" if success else "task_failed", task)
        
        return True
    
    def get_task_status(self, task_id: str) -> Optional[TaskStatus]:
        """获取任务状态"""
        if task_id in self.tasks:
            return self.tasks[task_id].status
        return None
    
    def get_task(self, task_id: str) -> Optional[DistributedTask]:
        """获取任务"""
        return self.tasks.get(task_id)
    
    def get_pending_tasks(self) -> List[DistributedTask]:
        """获取所有待处理任务"""
        return [self.tasks[tid] for tid in self.pending_tasks if tid in self.tasks]
    
    def get_running_tasks(self) -> List[DistributedTask]:
        """获取所有运行中任务"""
        return [t for t in self.tasks.values() if t.status == TaskStatus.RUNNING]
    
    def get_worker_stats(self) -> Dict[str, Dict[str, Any]]:
        """获取工作节点统计"""
        stats = {}
        for worker_id, worker in self.workers.items():
            stats[worker_id] = {
                "node_id": worker.node_id,
                "capacity": worker.capacity,
                "current_load": worker.current_load,
                "available_slots": worker.available_slots(),
                "is_healthy": worker.is_healthy(self.heartbeat_timeout),
                "supported_types": list(worker.supported_task_types)
            }
        return stats
    
    def get_queue_stats(self) -> Dict[str, Any]:
        """获取队列统计"""
        return {
            "total_tasks": len(self.tasks),
            "pending_tasks": len(self.pending_tasks),
            "running_tasks": len(self.get_running_tasks()),
            "completed_tasks": len(self.completed_tasks),
            "failed_tasks": len(self.failed_tasks),
            "workers": len(self.workers),
            "healthy_workers": sum(
                1 for w in self.workers.values()
                if w.is_healthy(self.heartbeat_timeout)
            )
        }
    
    def check_timeouts(self) -> List[DistributedTask]:
        """
        检查并处理超时任务
        
        Returns:
            超时任务列表
        """
        timed_out = []
        
        for task in list(self.tasks.values()):
            if task.status in (TaskStatus.RUNNING, TaskStatus.ASSIGNED) and task.is_expired(self.task_timeout):
                task.status = TaskStatus.TIMEOUT
                timed_out.append(task)
                
                # 更新工作节点负载
                if task.assigned_to and task.assigned_to in self.workers:
                    self.workers[task.assigned_to].current_load = max(
                        0, self.workers[task.assigned_to].current_load - 1
                    )
                
                # 尝试重试
                if task.can_retry():
                    task.retry_count += 1
                    task.status = TaskStatus.PENDING
                    task.assigned_to = None
                    task.started_at = None
                    self._insert_pending_task(task.task_id)
                else:
                    self.failed_tasks[task.task_id] = task
                
                self._notify_callbacks("task_timeout", task)
        
        return timed_out
    
    def check_worker_health(self) -> List[str]:
        """
        检查工作节点健康状态
        
        Returns:
            失效节点列表
        """
        failed_workers = []
        
        for worker_id, worker in list(self.workers.items()):
            if not worker.is_healthy(self.heartbeat_timeout):
                worker.is_alive = False
                failed_workers.append(worker_id)
                
                # 重新分配该节点的任务
                for task in list(self.tasks.values()):
                    if task.assigned_to == worker_id and task.status in (
                        TaskStatus.ASSIGNED, TaskStatus.RUNNING
                    ):
                        task.status = TaskStatus.PENDING
                        task.assigned_to = None
                        task.started_at = None
                        self._insert_pending_task(task.task_id)
                
                self._notify_callbacks("worker_failed", worker)
        
        return failed_workers
    
    def register_callback(self, callback: Callable):
        """注册回调函数"""
        self._callbacks.append(callback)
    
    def unregister_callback(self, callback: Callable):
        """注销回调函数"""
        if callback in self._callbacks:
            self._callbacks.remove(callback)
    
    def _notify_callbacks(self, event: str, data: Any):
        """通知所有回调"""
        for callback in self._callbacks:
            try:
                callback(event, data)
            except Exception:
                pass
    
    def rebalance_tasks(self) -> int:
        """
        重新平衡任务分配
        
        Returns:
            重新分配的任务数
        """
        rebalanced = 0
        
        # 检查已分配/运行中的任务是否分配给了不健康的节点
        for task in list(self.tasks.values()):
            if task.status in (TaskStatus.RUNNING, TaskStatus.ASSIGNED) and task.assigned_to:
                worker = self.workers.get(task.assigned_to)
                if not worker or not worker.is_healthy(self.heartbeat_timeout):
                    # 重新分配回待处理队列
                    task.status = TaskStatus.PENDING
                    task.assigned_to = None
                    task.started_at = None
                    self._insert_pending_task(task.task_id)
                    rebalanced += 1
        
        return rebalanced
    
    def clear(self):
        """清空队列"""
        self.tasks.clear()
        self.pending_tasks.clear()
        self.completed_tasks.clear()
        self.failed_tasks.clear()
        self.workers.clear()
        self._callbacks.clear()
    
    def __repr__(self) -> str:
        stats = self.get_queue_stats()
        return (f"DistributedTaskQueue(node={self.node_id}, "
                f"pending={stats['pending_tasks']}, "
                f"running={stats['running_tasks']}, "
                f"workers={stats['healthy_workers']}/{stats['workers']})")

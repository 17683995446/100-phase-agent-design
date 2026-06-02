from typing import Dict, List, Callable, Any, Optional
from enum import Enum
from collections import defaultdict
import threading
import time


class EventPriority(Enum):
    """事件优先级"""
    CRITICAL = 0   # 关键：立即处理
    HIGH = 1       # 高：优先处理
    NORMAL = 2     # 正常：按顺序处理
    LOW = 3        # 低：可延迟处理
    BACKGROUND = 4 # 后台：空闲时处理


class EventBus:
    """
    事件总线

    功能：模块间通信的基础设施，实现松耦合的模块交互
    原理：发布-订阅模式（Pub/Sub）

    设计原则：
    - 模块间禁止直接调用，所有通信通过事件总线
    - 事件是异步的，不阻塞发布方
    - 支持优先级和过滤

    使用方式：
        # 订阅事件
        EventBus.subscribe("node.added", my_handler, priority=EventPriority.NORMAL)

        # 发布事件
        EventBus.publish("node.added", {"node": "AI", "timestamp": time.time()})

        # 取消订阅
        EventBus.unsubscribe("node.added", my_handler)
    """

    _subscribers: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    _lock = threading.RLock()
    _event_history: List[Dict[str, Any]] = []
    _max_history = 1000

    @classmethod
    def subscribe(cls, event_type: str, handler: Callable,
                  priority: EventPriority = EventPriority.NORMAL,
                  filter_fn: Optional[Callable[[Any], bool]] = None) -> bool:
        """
        订阅事件

        Args:
            event_type: 事件类型
            handler: 处理函数，签名为 handler(data: dict)
            priority: 优先级
            filter_fn: 过滤函数，只处理满足条件的事件

        Returns:
            是否成功
        """
        with cls._lock:
            # 检查是否已订阅
            for sub in cls._subscribers[event_type]:
                if sub['handler'] == handler:
                    return False

            cls._subscribers[event_type].append({
                'handler': handler,
                'priority': priority,
                'filter': filter_fn,
                'subscribed_at': time.time()
            })

            # 按优先级排序
            cls._subscribers[event_type].sort(key=lambda x: x['priority'].value)

            return True

    @classmethod
    def unsubscribe(cls, event_type: str, handler: Callable) -> bool:
        """取消订阅"""
        with cls._lock:
            subs = cls._subscribers.get(event_type, [])
            for i, sub in enumerate(subs):
                if sub['handler'] == handler:
                    subs.pop(i)
                    return True
            return False

    @classmethod
    def publish(cls, event_type: str, data: Dict[str, Any],
                priority: EventPriority = EventPriority.NORMAL) -> int:
        """
        发布事件

        Args:
            event_type: 事件类型
            data: 事件数据
            priority: 事件优先级

        Returns:
            成功通知的订阅者数量
        """
        event = {
            'type': event_type,
            'data': data,
            'priority': priority,
            'timestamp': time.time(),
            'id': f"{event_type}_{time.time()}_{id(data)}"
        }

        # 记录历史
        cls._event_history.append(event)
        if len(cls._event_history) > cls._max_history:
            cls._event_history.pop(0)

        # 通知订阅者
        notified = 0
        with cls._lock:
            subs = cls._subscribers.get(event_type, []).copy()

        for sub in subs:
            try:
                # 应用过滤
                if sub['filter'] and not sub['filter'](data):
                    continue

                # 调用处理函数
                sub['handler'](data)
                notified += 1
            except Exception as e:
                # 记录错误但不影响其他订阅者
                print(f"[EventBus ERROR] 处理事件 '{event_type}' 失败: {e}")

        return notified

    @classmethod
    def publish_sync(cls, event_type: str, data: Dict[str, Any],
                     priority: EventPriority = EventPriority.NORMAL,
                     timeout: float = 5.0) -> Dict[str, Any]:
        """
        同步发布事件，等待第一个响应

        Args:
            event_type: 事件类型
            data: 事件数据
            priority: 优先级
            timeout: 超时时间（秒）

        Returns:
            第一个订阅者的响应
        """
        result = {'response': None, 'responded': False}

        def wrapper_handler(event_data):
            if not result['responded']:
                result['response'] = event_data
                result['responded'] = True

        cls.subscribe(event_type, wrapper_handler, priority)
        cls.publish(event_type, data, priority)

        # 等待响应
        start = time.time()
        while not result['responded'] and time.time() - start < timeout:
            time.sleep(0.01)

        cls.unsubscribe(event_type, wrapper_handler)
        return result['response']

    @classmethod
    def get_subscribers(cls, event_type: Optional[str] = None) -> Dict[str, List[Dict[str, Any]]]:
        """获取订阅者信息"""
        with cls._lock:
            if event_type:
                return {event_type: cls._subscribers.get(event_type, [])}
            return dict(cls._subscribers)

    @classmethod
    def get_event_history(cls, event_type: Optional[str] = None,
                          limit: int = 100) -> List[Dict[str, Any]]:
        """获取事件历史"""
        history = cls._event_history
        if event_type:
            history = [e for e in history if e['type'] == event_type]
        return history[-limit:]

    @classmethod
    def clear_history(cls) -> None:
        """清除事件历史"""
        cls._event_history.clear()

    @classmethod
    def get_stats(cls) -> Dict[str, Any]:
        """获取事件总线统计"""
        with cls._lock:
            return {
                'total_event_types': len(cls._subscribers),
                'total_subscribers': sum(len(subs) for subs in cls._subscribers.values()),
                'event_history_size': len(cls._event_history),
                'event_types': list(cls._subscribers.keys())
            }


# 预定义的标准事件类型
class SystemEvents:
    """系统标准事件类型"""

    # 节点事件
    NODE_ADDED = "node.added"
    NODE_REMOVED = "node.removed"
    NODE_UPDATED = "node.updated"

    # 边事件
    EDGE_ADDED = "edge.added"
    EDGE_REMOVED = "edge.removed"

    # 任务事件
    TASK_ADDED = "task.added"
    TASK_STARTED = "task.started"
    TASK_COMPLETED = "task.completed"
    TASK_FAILED = "task.failed"

    # 系统事件
    SYSTEM_STARTUP = "system.startup"
    SYSTEM_SHUTDOWN = "system.shutdown"
    SYSTEM_ERROR = "system.error"

    # 进化事件
    EVOLUTION_STARTED = "evolution.started"
    EVOLUTION_COMPLETED = "evolution.completed"

    # 模块事件
    MODULE_REGISTERED = "module.registered"
    MODULE_READY = "module.ready"
    MODULE_ERROR = "module.error"

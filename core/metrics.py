import time
import threading
from typing import Dict, Any, List, Optional


class Counter:
    """
    计数器指标 - 单调递增
    """
    def __init__(self, name: str, labels: Optional[Dict[str, str]] = None):
        self.name = name
        self.labels = labels or {}
        self._value = 0
        self._created_at = time.time()
        self._lock = threading.Lock()
    
    def inc(self, delta: int = 1) -> None:
        with self._lock:
            self._value += delta
    
    def get(self) -> int:
        with self._lock:
            return self._value
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "type": "counter",
            "value": self._value,
            "labels": self.labels,
            "created_at": self._created_at
        }


class Gauge:
    """
    仪表盘指标 - 可增减
    """
    def __init__(self, name: str, labels: Optional[Dict[str, str]] = None):
        self.name = name
        self.labels = labels or {}
        self._value = 0.0
        self._created_at = time.time()
        self._lock = threading.Lock()
    
    def set(self, value: float) -> None:
        with self._lock:
            self._value = value
    
    def inc(self, delta: float = 1.0) -> None:
        with self._lock:
            self._value += delta
    
    def dec(self, delta: float = 1.0) -> None:
        with self._lock:
            self._value -= delta
    
    def get(self) -> float:
        with self._lock:
            return self._value
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "type": "gauge",
            "value": self._value,
            "labels": self.labels,
            "created_at": self._created_at
        }


class MetricsCollector:
    """
    指标收集管理器
    """
    def __init__(self):
        self._counters: Dict[str, Counter] = {}
        self._gauges: Dict[str, Gauge] = {}
        self._lock = threading.Lock()
        self._started_at = time.time()
    
    def counter(self, name: str, labels: Optional[Dict[str, str]] = None) -> Counter:
        key = self._make_key(name, labels)
        with self._lock:
            if key not in self._counters:
                self._counters[key] = Counter(name, labels)
            return self._counters[key]
    
    def gauge(self, name: str, labels: Optional[Dict[str, str]] = None) -> Gauge:
        key = self._make_key(name, labels)
        with self._lock:
            if key not in self._gauges:
                self._gauges[key] = Gauge(name, labels)
            return self._gauges[key]
    
    def _make_key(self, name: str, labels: Optional[Dict[str, str]] = None) -> str:
        sorted_labels = sorted((labels or {}).items())
        label_str = ",".join([f"{k}={v}" for k, v in sorted_labels])
        if label_str:
            return f"{name}[{label_str}]"
        return name
    
    def export(self) -> List[Dict[str, Any]]:
        metrics = []
        with self._lock:
            for counter in self._counters.values():
                metrics.append(counter.to_dict())
            for gauge in self._gauges.values():
                metrics.append(gauge.to_dict())
        return metrics
    
    def export_json(self) -> str:
        import json
        data = {
            "exported_at": time.time(),
            "uptime": time.time() - self._started_at,
            "metrics": self.export()
        }
        return json.dumps(data, indent=2, ensure_ascii=False)
    
    def get_uptime(self) -> float:
        return time.time() - self._started_at
    
    def reset(self) -> None:
        with self._lock:
            self._counters.clear()
            self._gauges.clear()
            self._started_at = time.time()

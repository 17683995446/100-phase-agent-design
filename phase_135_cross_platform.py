#!/usr/bin/env python3
"""
阶段135：跨平台适配

第一性原理：
  - 抽象公理：差异之上建立统一接口
  - 检测公理：先识别平台，再选择适配
  - 退化公理：低资源平台降级运行
  - 隔离公理：平台特性不污染核心
  - 可移植公理：核心代码与平台解耦

本阶段产出：
  1. PlatformType：平台类型枚举
  2. PlatformInfo：平台信息
  3. PlatformDetector：平台检测器
  4. Adapter：适配器基类
  5. FileAdapter/ProcessAdapter/NetworkAdapter
  6. AdapterRegistry：适配器注册表
  7. AbstractionLayer：统一抽象层
  8. CrossPlatformAgent：跨平台智能体

遵循原则：图难于其易，为大于其细
"""
import time
import unittest
import platform
import sys
import os
import threading
import json
import uuid
from typing import Dict, List, Any, Optional, Callable
from enum import Enum
from dataclasses import dataclass, field
from collections import defaultdict
from abc import ABC, abstractmethod


# ============================================================
# 一、平台类型与信息
# ============================================================
class PlatformType(Enum):
    """平台类型"""
    LINUX = "linux"
    WINDOWS = "windows"
    MACOS = "macos"
    ANDROID = "android"
    IOS = "ios"
    BROWSER = "browser"
    SERVERLESS = "serverless"
    EMBEDDED = "embedded"
    UNKNOWN = "unknown"


class Architecture(Enum):
    """处理器架构"""
    X86 = "x86"
    X64 = "x64"
    ARM = "arm"
    ARM64 = "arm64"
    WASM = "wasm"
    UNKNOWN = "unknown"


@dataclass
class PlatformInfo:
    """平台信息"""
    platform_type: PlatformType
    architecture: Architecture
    os_version: str = ""
    python_version: str = ""
    hostname: str = ""
    cpu_count: int = 1
    total_memory_mb: float = 0.0
    capabilities: List[str] = field(default_factory=list)
    is_container: bool = False
    is_virtual: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)

    def has_capability(self, cap: str) -> bool:
        return cap in self.capabilities

    def summary(self) -> Dict[str, Any]:
        return {
            "platform": self.platform_type.value,
            "arch": self.architecture.value,
            "os": self.os_version,
            "python": self.python_version,
            "cpu": self.cpu_count,
            "mem_mb": round(self.total_memory_mb, 1),
            "caps": self.capabilities,
            "container": self.is_container,
        }


# ============================================================
# 二、平台检测器
# ============================================================
class PlatformDetector:
    """平台检测器
    自动识别当前运行环境的能力与限制。
    """
    def __init__(self):
        self._cached: Optional[PlatformInfo] = None
        self._lock = threading.RLock()

    def detect(self) -> PlatformInfo:
        with self._lock:
            if self._cached is not None:
                return self._cached
            info = self._do_detect()
            self._cached = info
            return info

    def _do_detect(self) -> PlatformInfo:
        system = platform.system().lower()
        machine = platform.machine().lower()

        if system == "linux":
            ptype = PlatformType.LINUX
        elif system == "windows":
            ptype = PlatformType.WINDOWS
        elif system == "darwin":
            ptype = PlatformType.MACOS
        else:
            ptype = PlatformType.UNKNOWN

        if machine in ("x86", "i386", "i686"):
            arch = Architecture.X86
        elif machine in ("x86_64", "amd64"):
            arch = Architecture.X64
        elif machine in ("arm", "armv7l"):
            arch = Architecture.ARM
        elif machine in ("arm64", "aarch64"):
            arch = Architecture.ARM64
        else:
            arch = Architecture.UNKNOWN

        # 容量检测
        caps = ["threading", "json", "io"]
        try:
            import asyncio
            caps.append("asyncio")
        except ImportError:
            pass
        try:
            import ssl
            caps.append("ssl")
        except ImportError:
            pass
        try:
            import sqlite3
            caps.append("sqlite")
        except ImportError:
            pass

        # 容器检测
        is_container = os.path.exists("/.dockerenv") or os.path.exists("/run/.containerenv")
        if not is_container and "container" in platform.release().lower():
            is_container = True

        info = PlatformInfo(
            platform_type=ptype,
            architecture=arch,
            os_version=f"{platform.system()} {platform.release()}",
            python_version=sys.version.split()[0],
            hostname=platform.node(),
            cpu_count=os.cpu_count() or 1,
            total_memory_mb=self._detect_memory(),
            capabilities=caps,
            is_container=is_container,
            metadata={
                "implementation": platform.python_implementation(),
                "executable": sys.executable,
            },
        )
        return info

    def _detect_memory(self) -> float:
        try:
            if hasattr(os, 'sysconf'):
                pages = os.sysconf('SC_PHYS_PAGES')
                page_size = os.sysconf('SC_PAGE_SIZE')
                return (pages * page_size) / (1024 * 1024)
        except (ValueError, OSError):
            pass
        # 简化：估算
        return 1024.0

    def reset(self) -> None:
        with self._lock:
            self._cached = None

    def is_low_resource(self) -> bool:
        info = self.detect()
        return info.total_memory_mb < 512 or info.cpu_count <= 1


# ============================================================
# 三、能力与资源限制
# ============================================================
@dataclass
class ResourceLimits:
    """资源限制"""
    max_memory_mb: float = 1024.0
    max_cpu_cores: int = 4
    max_disk_mb: float = 10240.0
    max_file_handles: int = 1024
    max_threads: int = 100
    network_enabled: bool = True
    filesystem_writable: bool = True


class CapabilityProfile:
    """能力画像
    根据平台特性，提供降级建议。
    """
    def __init__(self, info: PlatformInfo,
                 limits: Optional[ResourceLimits] = None):
        self.info = info
        self.limits = limits or self._infer_limits(info)

    def _infer_limits(self, info: PlatformInfo) -> ResourceLimits:
        if info.platform_type in (PlatformType.EMBEDDED, PlatformType.IOS, PlatformType.ANDROID):
            return ResourceLimits(
                max_memory_mb=256.0, max_cpu_cores=2,
                max_disk_mb=512.0, max_threads=20,
                network_enabled=True, filesystem_writable=True)
        if info.is_container:
            return ResourceLimits(
                max_memory_mb=512.0, max_cpu_cores=2,
                max_disk_mb=2048.0, max_threads=50)
        if info.platform_type == PlatformType.SERVERLESS:
            return ResourceLimits(
                max_memory_mb=512.0, max_cpu_cores=1,
                max_disk_mb=512.0, max_threads=10,
                filesystem_writable=False)
        return ResourceLimits(
            max_memory_mb=4096.0, max_cpu_cores=8,
            max_disk_mb=10240.0, max_threads=200)

    def should_degrade(self, requested_memory_mb: float) -> bool:
        return requested_memory_mb > self.limits.max_memory_mb

    def recommended_settings(self) -> Dict[str, Any]:
        return {
            "batch_size": min(100, max(10, int(self.limits.max_memory_mb / 4))),
            "thread_count": min(self.limits.max_threads, self.info.cpu_count * 2),
            "cache_size_mb": int(self.limits.max_memory_mb * 0.2),
            "enable_network": self.limits.network_enabled,
            "enable_disk_writes": self.limits.filesystem_writable,
        }


# ============================================================
# 四、适配器基类
# ============================================================
class Adapter(ABC):
    """适配器基类
    每个平台特性都有对应的适配器实现。
    """
    def __init__(self, name: str, supported: List[PlatformType]):
        self.name = name
        self.supported = supported

    def supports(self, platform_type: PlatformType) -> bool:
        return platform_type in self.supported

    @abstractmethod
    def initialize(self, info: PlatformInfo) -> bool: ...

    @abstractmethod
    def health(self) -> Dict[str, Any]: ...


# ============================================================
# 五、文件适配器
# ============================================================
class FileAdapter(Adapter):
    """文件适配器
    抽象不同平台的文件系统差异。
    """
    def __init__(self):
        super().__init__("file", [PlatformType.LINUX, PlatformType.MACOS,
                                     PlatformType.WINDOWS, PlatformType.ANDROID,
                                     PlatformType.IOS])
        self._tmp_root: Optional[str] = None
        self._paths_created: List[str] = []

    def initialize(self, info: PlatformInfo) -> bool:
        try:
            import tempfile
            self._tmp_root = tempfile.gettempdir()
            return True
        except Exception:
            return False

    def path_separator(self) -> str:
        # 已抽象：通过os.path处理
        return os.sep

    def tmp_dir(self) -> str:
        if self._tmp_root is None:
            self._tmp_root = os.path.join(os.getcwd(), ".tmp")
            os.makedirs(self._tmp_root, exist_ok=True)
        return self._tmp_root

    def write_text(self, path: str, content: str) -> bool:
        try:
            full = self._normalize(path)
            os.makedirs(os.path.dirname(full) or ".", exist_ok=True)
            with open(full, "w", encoding="utf-8") as f:
                f.write(content)
            self._paths_created.append(full)
            return True
        except OSError:
            return False

    def read_text(self, path: str) -> Optional[str]:
        try:
            full = self._normalize(path)
            with open(full, "r", encoding="utf-8") as f:
                return f.read()
        except (OSError, FileNotFoundError):
            return None

    def exists(self, path: str) -> bool:
        return os.path.exists(self._normalize(path))

    def remove(self, path: str) -> bool:
        try:
            full = self._normalize(path)
            if os.path.isdir(full):
                import shutil
                shutil.rmtree(full)
            else:
                os.remove(full)
            return True
        except OSError:
            return False

    def _normalize(self, path: str) -> str:
        if self._tmp_root and not os.path.isabs(path):
            return os.path.join(self._tmp_root, path)
        return path

    def health(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "tmp_dir": self._tmp_root,
            "files_created": len(self._paths_created),
            "separator": self.path_separator(),
        }


# ============================================================
# 六、进程适配器
# ============================================================
class ProcessAdapter(Adapter):
    """进程适配器"""
    def __init__(self):
        super().__init__("process", [PlatformType.LINUX, PlatformType.MACOS,
                                       PlatformType.WINDOWS])
        self._initialized = False
        self._pids: List[int] = []

    def initialize(self, info: PlatformInfo) -> bool:
        self._initialized = True
        return True

    def current_pid(self) -> int:
        return os.getpid()

    def current_time(self) -> float:
        return time.time()

    def sleep(self, seconds: float) -> None:
        time.sleep(seconds)

    def environment(self, name: str, default: str = "") -> str:
        return os.environ.get(name, default)

    def health(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "pid": self.current_pid(),
            "initialized": self._initialized,
        }


# ============================================================
# 七、网络适配器
# ============================================================
class NetworkAdapter(Adapter):
    """网络适配器
    模拟网络访问；不同平台网络栈差异被屏蔽。
    """
    def __init__(self):
        super().__init__("network", [PlatformType.LINUX, PlatformType.MACOS,
                                       PlatformType.WINDOWS, PlatformType.ANDROID,
                                       PlatformType.IOS, PlatformType.BROWSER,
                                       PlatformType.SERVERLESS])
        self._enabled = True
        self._simulated_latency_ms: float = 0.0
        self._call_count = 0

    def initialize(self, info: PlatformInfo) -> bool:
        self._enabled = True
        return True

    def disable(self) -> None:
        self._enabled = False

    def enable(self) -> None:
        self._enabled = True

    def set_simulated_latency(self, ms: float) -> None:
        self._simulated_latency_ms = ms

    def get(self, url: str, simulate: bool = True) -> Dict[str, Any]:
        if not self._enabled:
            return {"url": url, "status": 0, "error": "network_disabled"}
        self._call_count += 1
        if simulate and self._simulated_latency_ms > 0:
            time.sleep(self._simulated_latency_ms / 1000.0)
        # 模拟响应
        return {
            "url": url,
            "status": 200,
            "data": f"response for {url}",
        }

    def is_available(self) -> bool:
        return self._enabled

    def health(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "enabled": self._enabled,
            "calls": self._call_count,
        }


# ============================================================
# 八、适配器注册表
# ============================================================
class AdapterRegistry:
    """适配器注册表"""
    def __init__(self):
        self._adapters: Dict[str, Adapter] = {}
        self._lock = threading.RLock()

    def register(self, adapter: Adapter) -> None:
        with self._lock:
            self._adapters[adapter.name] = adapter

    def get(self, name: str) -> Optional[Adapter]:
        with self._lock:
            return self._adapters.get(name)

    def find_for_platform(self, platform_type: PlatformType) -> List[Adapter]:
        with self._lock:
            return [a for a in self._adapters.values() if a.supports(platform_type)]

    def all(self) -> List[Adapter]:
        with self._lock:
            return list(self._adapters.values())

    def initialize_all(self, info: PlatformInfo) -> Dict[str, bool]:
        with self._lock:
            results = {}
            for a in self._adapters.values():
                if a.supports(info.platform_type):
                    results[a.name] = a.initialize(info)
            return results


# ============================================================
# 九、抽象层
# ============================================================
class AbstractionLayer:
    """抽象层
    对上层提供统一接口，屏蔽平台差异。
    """
    def __init__(self, registry: AdapterRegistry, info: PlatformInfo,
                 profile: CapabilityProfile):
        self.registry = registry
        self.info = info
        self.profile = profile
        self._initialized = False

    def initialize(self) -> None:
        self.registry.initialize_all(self.info)
        self._initialized = True

    def read_file(self, path: str) -> Optional[str]:
        if not self.profile.limits.filesystem_writable:
            # 只读平台
            pass
        fa = self.registry.get("file")
        if isinstance(fa, FileAdapter):
            return fa.read_text(path)
        return None

    def write_file(self, path: str, content: str) -> bool:
        if not self.profile.limits.filesystem_writable:
            return False
        fa = self.registry.get("file")
        if isinstance(fa, FileAdapter):
            return fa.write_text(path, content)
        return False

    def http_get(self, url: str) -> Dict[str, Any]:
        if not self.profile.limits.network_enabled:
            return {"url": url, "status": 0, "error": "network_unavailable"}
        na = self.registry.get("network")
        if isinstance(na, NetworkAdapter):
            return na.get(url)
        return {"url": url, "status": 0, "error": "no_adapter"}

    def sleep(self, seconds: float) -> None:
        pa = self.registry.get("process")
        if isinstance(pa, ProcessAdapter):
            pa.sleep(seconds)
        else:
            time.sleep(seconds)

    def health(self) -> Dict[str, Any]:
        return {
            "platform": self.info.summary(),
            "adapters": {a.name: a.health() for a in self.registry.all()},
            "profile": self.profile.recommended_settings(),
            "initialized": self._initialized,
        }


# ============================================================
# 十、跨平台智能体
# ============================================================
class CrossPlatformAgent:
    """跨平台智能体
    整合所有能力，呈现一个可在多平台部署的统一接口。
    """
    def __init__(self, name: str = "agent"):
        self.name = name
        self.detector = PlatformDetector()
        self.registry = AdapterRegistry()
        self._register_default_adapters()
        info = self.detector.detect()
        self.profile = CapabilityProfile(info)
        self.abstraction = AbstractionLayer(self.registry, info, self.profile)
        self.abstraction.initialize()
        self._metrics: Dict[str, int] = defaultdict(int)
        self._lock = threading.RLock()

    def _register_default_adapters(self) -> None:
        self.registry.register(FileAdapter())
        self.registry.register(ProcessAdapter())
        self.registry.register(NetworkAdapter())

    def run(self, task: str) -> Dict[str, Any]:
        with self._lock:
            self._metrics["tasks_total"] += 1
            result = {
                "task": task,
                "platform": self.detector.detect().platform_type.value,
                "ts": time.time(),
            }
            if task.startswith("read:"):
                path = task[len("read:"):]
                content = self.abstraction.read_file(path)
                result["content"] = content
            elif task.startswith("write:"):
                parts = task[len("write:"):].split("=", 1)
                if len(parts) == 2:
                    ok = self.abstraction.write_file(parts[0], parts[1])
                    result["written"] = ok
            elif task.startswith("http:"):
                url = task[len("http:"):]
                result["response"] = self.abstraction.http_get(url)
            elif task.startswith("sleep:"):
                secs = float(task[len("sleep:"):])
                self.abstraction.sleep(secs)
                result["slept"] = secs
            else:
                result["note"] = "unknown_task"
            self._metrics["tasks_ok"] += 1
            return result

    def health(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "name": self.name,
                "metrics": dict(self._metrics),
                "abstraction": self.abstraction.health(),
            }

    def adapt(self, new_info: PlatformInfo) -> None:
        """切换平台（演示用）"""
        with self._lock:
            self.profile = CapabilityProfile(new_info)
            self.abstraction = AbstractionLayer(self.registry, new_info, self.profile)
            self.abstraction.initialize()


# ============================================================
# 十一、测试
# ============================================================
class TestPlatformInfo(unittest.TestCase):
    def test_summary(self):
        info = PlatformInfo(platform_type=PlatformType.LINUX,
                             architecture=Architecture.X64,
                             cpu_count=4)
        s = info.summary()
        self.assertEqual(s["platform"], "linux")
        self.assertEqual(s["arch"], "x64")
        self.assertEqual(s["cpu"], 4)

    def test_has_capability(self):
        info = PlatformInfo(platform_type=PlatformType.LINUX,
                             architecture=Architecture.X64,
                             capabilities=["json", "io"])
        self.assertTrue(info.has_capability("json"))
        self.assertFalse(info.has_capability("async"))


class TestPlatformDetector(unittest.TestCase):
    def test_detect(self):
        d = PlatformDetector()
        info = d.detect()
        self.assertIsNotNone(info)
        self.assertIn(info.platform_type, list(PlatformType))

    def test_cached(self):
        d = PlatformDetector()
        i1 = d.detect()
        i2 = d.detect()
        self.assertIs(i1, i2)

    def test_reset(self):
        d = PlatformDetector()
        d.detect()
        d.reset()
        self.assertIsNone(d._cached)

    def test_low_resource_check(self):
        d = PlatformDetector()
        # 只检测不失败
        result = d.is_low_resource()
        self.assertIsInstance(result, bool)


class TestResourceLimits(unittest.TestCase):
    def test_default(self):
        lim = ResourceLimits()
        self.assertGreater(lim.max_memory_mb, 0)


class TestCapabilityProfile(unittest.TestCase):
    def test_infer_for_embedded(self):
        info = PlatformInfo(platform_type=PlatformType.EMBEDDED,
                             architecture=Architecture.ARM)
        p = CapabilityProfile(info)
        self.assertLessEqual(p.limits.max_memory_mb, 512)

    def test_infer_for_container(self):
        info = PlatformInfo(platform_type=PlatformType.LINUX,
                             architecture=Architecture.X64,
                             is_container=True)
        p = CapabilityProfile(info)
        self.assertLessEqual(p.limits.max_memory_mb, 1024)

    def test_infer_for_server(self):
        info = PlatformInfo(platform_type=PlatformType.LINUX,
                             architecture=Architecture.X64)
        p = CapabilityProfile(info)
        self.assertGreater(p.limits.max_memory_mb, 1024)

    def test_should_degrade(self):
        info = PlatformInfo(platform_type=PlatformType.EMBEDDED,
                             architecture=Architecture.ARM)
        p = CapabilityProfile(info)
        self.assertTrue(p.should_degrade(10000))

    def test_recommended_settings(self):
        info = PlatformInfo(platform_type=PlatformType.LINUX,
                             architecture=Architecture.X64,
                             cpu_count=4)
        p = CapabilityProfile(info)
        s = p.recommended_settings()
        self.assertIn("batch_size", s)
        self.assertIn("thread_count", s)


class TestFileAdapter(unittest.TestCase):
    def test_initialize(self):
        a = FileAdapter()
        info = PlatformInfo(platform_type=PlatformType.LINUX,
                             architecture=Architecture.X64)
        self.assertTrue(a.initialize(info))

    def test_write_read(self):
        a = FileAdapter()
        a.initialize(PlatformInfo(platform_type=PlatformType.LINUX,
                                    architecture=Architecture.X64))
        test_path = f"test_{uuid.uuid4().hex[:6]}.txt"
        ok = a.write_text(test_path, "hello")
        self.assertTrue(ok)
        content = a.read_text(test_path)
        self.assertEqual(content, "hello")
        a.remove(test_path)

    def test_exists(self):
        a = FileAdapter()
        a.initialize(PlatformInfo(platform_type=PlatformType.LINUX,
                                    architecture=Architecture.X64))
        self.assertFalse(a.exists("nonexistent_file_xyz.txt"))

    def test_health(self):
        a = FileAdapter()
        h = a.health()
        self.assertEqual(h["name"], "file")


class TestProcessAdapter(unittest.TestCase):
    def test_pid(self):
        a = ProcessAdapter()
        a.initialize(PlatformInfo(platform_type=PlatformType.LINUX,
                                    architecture=Architecture.X64))
        self.assertEqual(a.current_pid(), os.getpid())

    def test_environment(self):
        os.environ["TEST_X"] = "1"
        a = ProcessAdapter()
        a.initialize(PlatformInfo(platform_type=PlatformType.LINUX,
                                    architecture=Architecture.X64))
        self.assertEqual(a.environment("TEST_X"), "1")
        self.assertEqual(a.environment("NONEXISTENT", "default"), "default")

    def test_sleep(self):
        a = ProcessAdapter()
        a.initialize(PlatformInfo(platform_type=PlatformType.LINUX,
                                    architecture=Architecture.X64))
        start = time.time()
        a.sleep(0.01)
        self.assertGreaterEqual(time.time() - start, 0.005)


class TestNetworkAdapter(unittest.TestCase):
    def test_get(self):
        a = NetworkAdapter()
        a.initialize(PlatformInfo(platform_type=PlatformType.LINUX,
                                    architecture=Architecture.X64))
        r = a.get("http://test.example.com")
        self.assertEqual(r["status"], 200)

    def test_disable(self):
        a = NetworkAdapter()
        a.initialize(PlatformInfo(platform_type=PlatformType.LINUX,
                                    architecture=Architecture.X64))
        a.disable()
        self.assertFalse(a.is_available())
        r = a.get("http://test.example.com")
        self.assertEqual(r["status"], 0)
        a.enable()
        self.assertTrue(a.is_available())

    def test_simulated_latency(self):
        a = NetworkAdapter()
        a.initialize(PlatformInfo(platform_type=PlatformType.LINUX,
                                    architecture=Architecture.X64))
        a.set_simulated_latency(50.0)
        start = time.time()
        a.get("http://test.example.com")
        self.assertGreaterEqual(time.time() - start, 0.04)


class TestAdapterRegistry(unittest.TestCase):
    def test_register_and_get(self):
        r = AdapterRegistry()
        fa = FileAdapter()
        r.register(fa)
        self.assertIs(r.get("file"), fa)

    def test_find_for_platform(self):
        r = AdapterRegistry()
        r.register(FileAdapter())
        r.register(NetworkAdapter())
        adapters = r.find_for_platform(PlatformType.LINUX)
        names = [a.name for a in adapters]
        self.assertIn("file", names)
        self.assertIn("network", names)

    def test_initialize_all(self):
        r = AdapterRegistry()
        r.register(FileAdapter())
        r.register(ProcessAdapter())
        info = PlatformInfo(platform_type=PlatformType.LINUX,
                             architecture=Architecture.X64)
        results = r.initialize_all(info)
        self.assertTrue(results["file"])
        self.assertTrue(results["process"])


class TestAbstractionLayer(unittest.TestCase):
    def test_initialize(self):
        r = AdapterRegistry()
        r.register(FileAdapter())
        info = PlatformInfo(platform_type=PlatformType.LINUX,
                             architecture=Architecture.X64)
        profile = CapabilityProfile(info)
        al = AbstractionLayer(r, info, profile)
        al.initialize()
        self.assertTrue(al._initialized)

    def test_write_file_disabled(self):
        r = AdapterRegistry()
        r.register(FileAdapter())
        info = PlatformInfo(platform_type=PlatformType.SERVERLESS,
                             architecture=Architecture.X64)
        profile = CapabilityProfile(info)
        al = AbstractionLayer(r, info, profile)
        al.initialize()
        ok = al.write_file("test.txt", "x")
        self.assertFalse(ok)

    def test_http_get_disabled(self):
        r = AdapterRegistry()
        r.register(NetworkAdapter())
        info = PlatformInfo(platform_type=PlatformType.LINUX,
                             architecture=Architecture.X64)
        profile = CapabilityProfile(info)
        profile.limits.network_enabled = False
        al = AbstractionLayer(r, info, profile)
        al.initialize()
        r2 = al.http_get("http://test")
        self.assertEqual(r2["status"], 0)


class TestCrossPlatformAgent(unittest.TestCase):
    def test_create(self):
        agent = CrossPlatformAgent("test")
        self.assertIsNotNone(agent.detector.detect())

    def test_run_write_read(self):
        agent = CrossPlatformAgent("test")
        test_path = f"cp_{uuid.uuid4().hex[:6]}.txt"
        r1 = agent.run(f"write:{test_path}=hello world")
        self.assertTrue(r1.get("written", False))
        r2 = agent.run(f"read:{test_path}")
        self.assertEqual(r2.get("content"), "hello world")

    def test_run_http(self):
        agent = CrossPlatformAgent("test")
        r = agent.run("http:http://test.example.com")
        self.assertIn("response", r)

    def test_run_sleep(self):
        agent = CrossPlatformAgent("test")
        r = agent.run("sleep:0.01")
        self.assertEqual(r.get("slept"), 0.01)

    def test_run_unknown(self):
        agent = CrossPlatformAgent("test")
        r = agent.run("unknown_task")
        self.assertEqual(r.get("note"), "unknown_task")

    def test_health(self):
        agent = CrossPlatformAgent("test")
        h = agent.health()
        self.assertIn("abstraction", h)

    def test_adapt(self):
        agent = CrossPlatformAgent("test")
        new_info = PlatformInfo(platform_type=PlatformType.EMBEDDED,
                                  architecture=Architecture.ARM)
        agent.adapt(new_info)
        self.assertEqual(agent.detector.detect().platform_type, PlatformType.LINUX)
        # 切换的是profile，不是detector
        self.assertLessEqual(agent.profile.limits.max_memory_mb, 512)


# ============================================================
# 十二、Demo
# ============================================================
def demo():
    """演示阶段135的功能"""
    print("=" * 60)
    print("阶段135演示：跨平台适配")
    print("=" * 60)

    # 1. 平台检测
    print("\n🔍 演示1：平台检测")
    print("-" * 60)
    detector = PlatformDetector()
    info = detector.detect()
    print(f"  平台: {info.summary()}")

    # 2. 能力画像
    print("\n📋 演示2：能力画像")
    print("-" * 60)
    profile = CapabilityProfile(info)
    print(f"  推荐设置: {profile.recommended_settings()}")

    # 模拟嵌入式平台
    print("\n  模拟嵌入式平台:")
    embedded = PlatformInfo(platform_type=PlatformType.EMBEDDED,
                             architecture=Architecture.ARM,
                             cpu_count=1, total_memory_mb=64.0)
    p_emb = CapabilityProfile(embedded)
    print(f"    限制: 内存 {p_emb.limits.max_memory_mb}MB, 线程 {p_emb.limits.max_threads}")
    print(f"    推荐: {p_emb.recommended_settings()}")
    print(f"    10000MB请求应降级: {p_emb.should_degrade(10000)}")

    # 3. 适配器
    print("\n🔌 演示3：适配器")
    print("-" * 60)
    registry = AdapterRegistry()
    registry.register(FileAdapter())
    registry.register(ProcessAdapter())
    registry.register(NetworkAdapter())
    init_results = registry.initialize_all(info)
    print(f"  初始化结果: {init_results}")
    for a in registry.all():
        print(f"    {a.name}: {a.health()}")

    # 4. 抽象层
    print("\n🌐 演示4：抽象层")
    print("-" * 60)
    al = AbstractionLayer(registry, info, profile)
    al.initialize()
    # 写入
    test_path = f"abstraction_{uuid.uuid4().hex[:6]}.txt"
    al.write_file(test_path, "跨平台测试")
    content = al.read_file(test_path)
    print(f"  写入读取: '{content}'")
    # 网络
    r = al.http_get("http://api.example.com/data")
    print(f"  HTTP GET: status={r['status']}")

    # 5. 跨平台智能体
    print("\n🤖 演示5：跨平台智能体")
    print("-" * 60)
    agent = CrossPlatformAgent("multi-platform")
    for task in [
        "write:demo.txt=agent data",
        "read:demo.txt",
        "http:http://example.com",
        "sleep:0.01",
    ]:
        r = agent.run(task)
        print(f"  task='{task[:30]}' -> keys={list(r.keys())}")
    h = agent.health()
    print(f"  健康: name={h['name']}, 任务={h['metrics']}")

    # 6. 平台切换
    print("\n🔄 演示6：平台切换")
    print("-" * 60)
    new_platform = PlatformInfo(platform_type=PlatformType.SERVERLESS,
                                 architecture=Architecture.X64)
    agent.adapt(new_platform)
    r = agent.run("write:serverless.txt=cant write")
    print(f"  切换到serverless后写入: {r.get('written')}")
    print(f"  当前profile: 内存 {agent.profile.limits.max_memory_mb}MB")

    # 清理
    fa = registry.get("file")
    if isinstance(fa, FileAdapter):
        fa.remove(test_path)

    print("\n" + "=" * 60)
    print("✅ 阶段135完成：跨平台适配已实现！")
    print("=" * 60)
    print("\n【下阶段预告】阶段136：移动端SDK")
    print("  - 轻量化内核")
    print("  - 离线优先")
    print("  - 同步协议")


if __name__ == "__main__":
    unittest.main(verbosity=2, exit=False)
    print()
    demo()

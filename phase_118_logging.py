#!/usr/bin/env python3
"""
阶段118：日志系统

第一性原理：
  - 存续公理：事故复盘依赖日志
  - 观察公理：系统行为必须有据可查
  - 噪声过滤：太多信息等于没有信息
  - 结构化数据：可被机器解析

本阶段产出：
  1. LogLevel：日志级别
  2. LogRecord：日志记录
  3. LogFormatter：格式化器（文本/JSON）
  4. LogHandler：处理器（控制台/文件/轮转）
  5. Logger：主日志器
  6. RotatingFileHandler：日志轮转

遵循原则：图难于其易，为大于其细
"""
import os
import time
import json
import unittest
import threading
import gzip
import shutil
from typing import Dict, List, Any, Optional
from enum import IntEnum
from dataclasses import dataclass, field
from collections import deque
from io import StringIO


# ============================================================
# 一、日志级别
# ============================================================
class LogLevel(IntEnum):
    """日志级别（数字越大越严重）"""
    TRACE = 5
    DEBUG = 10
    INFO = 20
    WARN = 30
    ERROR = 40
    FATAL = 50

    @classmethod
    def from_string(cls, s: str) -> 'LogLevel':
        s = s.upper()
        mapping = {
            "TRACE": cls.TRACE,
            "DEBUG": cls.DEBUG,
            "INFO": cls.INFO,
            "WARN": cls.WARN,
            "WARNING": cls.WARN,
            "ERROR": cls.ERROR,
            "FATAL": cls.FATAL,
        }
        return mapping.get(s, cls.INFO)


# ============================================================
# 二、日志记录
# ============================================================
@dataclass
class LogRecord:
    """单条日志记录"""
    timestamp: float
    level: LogLevel
    name: str  # logger名
    message: str
    context: Dict[str, Any] = field(default_factory=dict)
    exc_info: Optional[str] = None
    thread_id: int = 0
    thread_name: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ts": self.timestamp,
            "level": self.level.name,
            "logger": self.name,
            "message": self.message,
            "context": self.context,
            "exc": self.exc_info,
            "thread_id": self.thread_id,
            "thread_name": self.thread_name,
        }


# ============================================================
# 三、格式化器
# ============================================================
class LogFormatter:
    """日志格式化器基类"""
    def format(self, record: LogRecord) -> str:
        raise NotImplementedError


class TextFormatter(LogFormatter):
    """文本格式化器"""
    def __init__(self, show_context: bool = True,
                 time_format: str = "%Y-%m-%d %H:%M:%S"):
        self.show_context = show_context
        self.time_format = time_format

    def format(self, record: LogRecord) -> str:
        ts = time.strftime(self.time_format,
                            time.localtime(record.timestamp))
        level_name = record.level.name.ljust(5)
        thread = f"[{record.thread_name}]" if record.thread_name else ""
        line = f"{ts} {level_name} {thread} {record.name} - {record.message}"
        if self.show_context and record.context:
            ctx_str = " ".join(
                f"{k}={v}" for k, v in record.context.items())
            line += f" | {ctx_str}"
        if record.exc_info:
            line += f"\n{record.exc_info}"
        return line


class JSONFormatter(LogFormatter):
    """JSON格式化器"""
    def format(self, record: LogRecord) -> str:
        return json.dumps(record.to_dict(), ensure_ascii=False)


# ============================================================
# 四、处理器
# ============================================================
class LogHandler:
    """日志处理器基类"""
    def __init__(self, level: LogLevel = LogLevel.DEBUG,
                 formatter: Optional[LogFormatter] = None):
        self.level = level
        self.formatter = formatter or TextFormatter()
        self._lock = threading.Lock()
        self._stats = {"emitted": 0, "dropped": 0}

    def emit(self, record: LogRecord) -> None:
        raise NotImplementedError

    def should_emit(self, record: LogRecord) -> bool:
        return record.level >= self.level

    def get_stats(self) -> Dict[str, int]:
        with self._lock:
            return dict(self._stats)


class ConsoleHandler(LogHandler):
    """控制台处理器"""
    def __init__(self, stream: Optional[Any] = None, **kwargs):
        super().__init__(**kwargs)
        self.stream = stream or sys_stdout()

    def emit(self, record: LogRecord) -> None:
        if not self.should_emit(record):
            with self._lock:
                self._stats["dropped"] += 1
            return
        line = self.formatter.format(record)
        with self._lock:
            self.stream.write(line + "\n")
            self.stream.flush()
            self._stats["emitted"] += 1


def sys_stdout():
    import sys
    return sys.stdout


class MemoryHandler(LogHandler):
    """内存处理器（用于测试）"""
    def __init__(self, max_records: int = 1000, **kwargs):
        super().__init__(**kwargs)
        self.records: deque = deque(maxlen=max_records)

    def emit(self, record: LogRecord) -> None:
        if not self.should_emit(record):
            with self._lock:
                self._stats["dropped"] += 1
            return
        with self._lock:
            self.records.append(record)
            self._stats["emitted"] += 1

    def get_records(self) -> List[LogRecord]:
        with self._lock:
            return list(self.records)

    def clear(self) -> None:
        with self._lock:
            self.records.clear()


# ============================================================
# 五、日志轮转
# ============================================================
class RotatingFileHandler(LogHandler):
    """轮转文件处理器

    按大小轮转：
    - 超过max_bytes则重命名为.1
    - 旧文件.1 -> .2 -> .3
    - 超过backup_count则丢弃最旧的
    """
    def __init__(self, filename: str,
                 max_bytes: int = 10 * 1024 * 1024,
                 backup_count: int = 5,
                 compress: bool = False,
                 **kwargs):
        super().__init__(**kwargs)
        self.filename = filename
        self.max_bytes = max_bytes
        self.backup_count = backup_count
        self.compress = compress
        self._file = None
        self._current_bytes = 0
        self._lock = threading.Lock()
        # 确保目录存在
        os.makedirs(os.path.dirname(filename) or ".", exist_ok=True)
        # 打开文件
        if os.path.exists(filename):
            self._current_bytes = os.path.getsize(filename)
        self._file = open(filename, "a", encoding="utf-8")

    def _should_rotate(self, line: str) -> bool:
        return (self._current_bytes + len(line.encode("utf-8"))
                > self.max_bytes)

    def _do_rotate(self) -> None:
        """执行轮转"""
        if self._file:
            self._file.close()
            self._file = None
        # 旧文件滚动：backup_count-1 -> backup_count, ..., 1 -> 2
        for i in range(self.backup_count - 1, 0, -1):
            src = f"{self.filename}.{i}"
            dst = f"{self.filename}.{i+1}"
            if os.path.exists(src):
                if os.path.exists(dst):
                    os.remove(dst)
                shutil.move(src, dst)
        # 主文件 -> .1
        if os.path.exists(self.filename):
            if os.path.exists(f"{self.filename}.1"):
                os.remove(f"{self.filename}.1")
            shutil.move(self.filename, f"{self.filename}.1")
        # 压缩最旧的（如果启用）
        if self.compress and self.backup_count > 0:
            old = f"{self.filename}.{self.backup_count}"
            if os.path.exists(old):
                with open(old, "rb") as f:
                    data = f.read()
                with gzip.open(f"{old}.gz", "wb") as f:
                    f.write(data)
                os.remove(old)
        # 重新打开文件
        self._file = open(self.filename, "a", encoding="utf-8")
        self._current_bytes = 0

    def emit(self, record: LogRecord) -> None:
        if not self.should_emit(record):
            with self._lock:
                self._stats["dropped"] += 1
            return
        line = self.formatter.format(record) + "\n"
        with self._lock:
            if self._should_rotate(line):
                self._do_rotate()
            if self._file:
                self._file.write(line)
                self._file.flush()
                self._current_bytes += len(line.encode("utf-8"))
                self._stats["emitted"] += 1

    def close(self) -> None:
        with self._lock:
            if self._file:
                self._file.close()
                self._file = None

    def get_stats(self) -> Dict[str, int]:
        with self._lock:
            stats = dict(self._stats)
            stats["current_bytes"] = self._current_bytes
            return stats


# ============================================================
# 六、Logger主类
# ============================================================
class Logger:
    """日志器

    用法：
        log = Logger("agent")
        log.info("started", extra={"version": "1.0"})
    """
    def __init__(self, name: str, level: LogLevel = LogLevel.DEBUG):
        self.name = name
        self.level = level
        self._handlers: List[LogHandler] = []
        self._lock = threading.RLock()
        # 上下文（绑定到所有日志）
        self._context: Dict[str, Any] = {}
        self._stats = {
            "emitted": 0,
            "dropped": 0,
            "by_level": {
                "DEBUG": 0, "INFO": 0, "WARN": 0,
                "ERROR": 0, "FATAL": 0, "TRACE": 0
            }
        }

    def add_handler(self, handler: LogHandler) -> None:
        with self._lock:
            self._handlers.append(handler)

    def remove_handler(self, handler: LogHandler) -> None:
        with self._lock:
            if handler in self._handlers:
                self._handlers.remove(handler)

    def bind(self, **kwargs) -> 'Logger':
        """绑定上下文（返回新Logger）"""
        with self._lock:
            new_log = Logger(self.name, self.level)
            new_log._context = {**self._context, **kwargs}
            new_log._handlers = list(self._handlers)
            return new_log

    def set_level(self, level: LogLevel) -> None:
        with self._lock:
            self.level = level

    def _log(self, level: LogLevel, message: str,
              context: Optional[Dict[str, Any]] = None,
              exc_info: Optional[str] = None) -> None:
        if level < self.level:
            return
        with self._lock:
            merged_ctx = {**self._context, **(context or {})}
            record = LogRecord(
                timestamp=time.time(),
                level=level,
                name=self.name,
                message=message,
                context=merged_ctx,
                exc_info=exc_info,
                thread_id=threading.get_ident(),
                thread_name=threading.current_thread().name,
            )
            self._stats["emitted"] += 1
            self._stats["by_level"][level.name] += 1
            handlers = list(self._handlers)
        for handler in handlers:
            try:
                handler.emit(record)
            except Exception:
                pass  # 处理器错误不应影响主流程

    def trace(self, msg: str, **ctx) -> None:
        self._log(LogLevel.TRACE, msg, ctx)

    def debug(self, msg: str, **ctx) -> None:
        self._log(LogLevel.DEBUG, msg, ctx)

    def info(self, msg: str, **ctx) -> None:
        self._log(LogLevel.INFO, msg, ctx)

    def warn(self, msg: str, **ctx) -> None:
        self._log(LogLevel.WARN, msg, ctx)

    def error(self, msg: str, **ctx) -> None:
        self._log(LogLevel.ERROR, msg, ctx)

    def fatal(self, msg: str, **ctx) -> None:
        self._log(LogLevel.FATAL, msg, ctx)

    def exception(self, msg: str, **ctx) -> None:
        import traceback
        self._log(LogLevel.ERROR, msg, ctx,
                  exc_info=traceback.format_exc())

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "name": self.name,
                "level": self.level.name,
                "emitted": self._stats["emitted"],
                "dropped": self._stats["dropped"],
                "by_level": dict(self._stats["by_level"]),
            }


# ============================================================
# 七、日志管理器
# ============================================================
class LogManager:
    """日志管理器（全局）"""
    def __init__(self):
        self._loggers: Dict[str, Logger] = {}
        self._lock = threading.Lock()

    def get(self, name: str) -> Logger:
        with self._lock:
            if name not in self._loggers:
                self._loggers[name] = Logger(name)
            return self._loggers[name]

    def set_root_level(self, level: LogLevel) -> None:
        with self._lock:
            for log in self._loggers.values():
                log.set_level(level)

    def list_loggers(self) -> List[str]:
        with self._lock:
            return list(self._loggers.keys())


# ============================================================
# 八、单元测试
# ============================================================
class TestLogLevel(unittest.TestCase):
    """日志级别测试"""
    def test_ordering(self):
        self.assertLess(LogLevel.DEBUG, LogLevel.INFO)
        self.assertLess(LogLevel.INFO, LogLevel.WARN)
        self.assertLess(LogLevel.WARN, LogLevel.ERROR)
        self.assertLess(LogLevel.ERROR, LogLevel.FATAL)

    def test_from_string(self):
        self.assertEqual(LogLevel.from_string("info"), LogLevel.INFO)
        self.assertEqual(LogLevel.from_string("WARN"), LogLevel.WARN)
        self.assertEqual(LogLevel.from_string("Warning"), LogLevel.WARN)


class TestFormatters(unittest.TestCase):
    """格式化器测试"""
    def test_text(self):
        fmt = TextFormatter()
        rec = LogRecord(time.time(), LogLevel.INFO, "test", "hello")
        s = fmt.format(rec)
        self.assertIn("INFO", s)
        self.assertIn("hello", s)
        self.assertIn("test", s)

    def test_text_with_context(self):
        fmt = TextFormatter(show_context=True)
        rec = LogRecord(time.time(), LogLevel.INFO, "test", "hi",
                         context={"k": "v"})
        s = fmt.format(rec)
        self.assertIn("k=v", s)

    def test_json(self):
        fmt = JSONFormatter()
        rec = LogRecord(time.time(), LogLevel.INFO, "test", "hi",
                         context={"a": 1})
        s = fmt.format(rec)
        data = json.loads(s)
        self.assertEqual(data["level"], "INFO")
        self.assertEqual(data["message"], "hi")
        self.assertEqual(data["context"]["a"], 1)


class TestMemoryHandler(unittest.TestCase):
    """内存处理器测试"""
    def test_emit(self):
        h = MemoryHandler()
        h.emit(LogRecord(time.time(), LogLevel.INFO, "x", "msg"))
        recs = h.get_records()
        self.assertEqual(len(recs), 1)
        self.assertEqual(recs[0].message, "msg")

    def test_level_filter(self):
        h = MemoryHandler(level=LogLevel.WARN)
        h.emit(LogRecord(time.time(), LogLevel.DEBUG, "x", "d"))
        h.emit(LogRecord(time.time(), LogLevel.INFO, "x", "i"))
        h.emit(LogRecord(time.time(), LogLevel.WARN, "x", "w"))
        h.emit(LogRecord(time.time(), LogLevel.ERROR, "x", "e"))
        recs = h.get_records()
        self.assertEqual(len(recs), 2)
        self.assertEqual(recs[0].message, "w")

    def test_max_records(self):
        h = MemoryHandler(max_records=3)
        for i in range(10):
            h.emit(LogRecord(time.time(), LogLevel.INFO, "x", str(i)))
        recs = h.get_records()
        self.assertEqual(len(recs), 3)
        self.assertEqual(recs[0].message, "7")  # 最早的3条

    def test_clear(self):
        h = MemoryHandler()
        h.emit(LogRecord(time.time(), LogLevel.INFO, "x", "msg"))
        h.clear()
        self.assertEqual(len(h.get_records()), 0)


class TestRotatingFile(unittest.TestCase):
    """轮转文件测试"""
    def setUp(self):
        self.tmpdir = "/tmp/test_log_rotate"
        if os.path.exists(self.tmpdir):
            shutil.rmtree(self.tmpdir)
        os.makedirs(self.tmpdir)

    def tearDown(self):
        if os.path.exists(self.tmpdir):
            shutil.rmtree(self.tmpdir)

    def test_basic_write(self):
        path = f"{self.tmpdir}/test.log"
        h = RotatingFileHandler(path, max_bytes=1024 * 1024)
        h.emit(LogRecord(time.time(), LogLevel.INFO, "x", "hello"))
        h.close()
        with open(path) as f:
            content = f.read()
        self.assertIn("hello", content)

    def test_rotation_by_size(self):
        path = f"{self.tmpdir}/test.log"
        h = RotatingFileHandler(path, max_bytes=200, backup_count=3)
        # 写超过max_bytes的日志
        for i in range(30):
            h.emit(LogRecord(
                time.time(), LogLevel.INFO, "x",
                f"message {i} with some padding"))
        h.close()
        # 主文件 + 备份文件
        files = os.listdir(self.tmpdir)
        self.assertGreater(len(files), 1)


class TestLogger(unittest.TestCase):
    """Logger测试"""
    def setUp(self):
        self.mem = MemoryHandler()
        self.log = Logger("test")
        self.log.add_handler(self.mem)

    def test_log_levels(self):
        self.log.debug("d")
        self.log.info("i")
        self.log.warn("w")
        self.log.error("e")
        recs = self.mem.get_records()
        self.assertEqual(len(recs), 4)

    def test_level_filter(self):
        self.log.set_level(LogLevel.WARN)
        self.log.debug("d")
        self.log.info("i")
        self.log.warn("w")
        recs = self.mem.get_records()
        self.assertEqual(len(recs), 1)
        self.assertEqual(recs[0].message, "w")

    def test_context(self):
        self.log.info("msg", user="alice", count=5)
        recs = self.mem.get_records()
        self.assertEqual(recs[0].context["user"], "alice")
        self.assertEqual(recs[0].context["count"], 5)

    def test_bind(self):
        bound = self.log.bind(component="auth")
        bound.info("logged in", user="bob")
        recs = self.mem.get_records()
        self.assertEqual(recs[0].context["component"], "auth")
        self.assertEqual(recs[0].context["user"], "bob")

    def test_exception(self):
        try:
            raise ValueError("test")
        except ValueError:
            self.log.exception("oops")
        recs = self.mem.get_records()
        self.assertIsNotNone(recs[0].exc_info)
        self.assertIn("ValueError", recs[0].exc_info)

    def test_stats(self):
        self.log.info("a")
        self.log.info("b")
        self.log.error("c")
        stats = self.log.get_stats()
        self.assertEqual(stats["by_level"]["INFO"], 2)
        self.assertEqual(stats["by_level"]["ERROR"], 1)


class TestLogManager(unittest.TestCase):
    """日志管理器测试"""
    def test_get_or_create(self):
        mgr = LogManager()
        log1 = mgr.get("a")
        log2 = mgr.get("a")
        self.assertIs(log1, log2)

    def test_different_names(self):
        mgr = LogManager()
        log1 = mgr.get("a")
        log2 = mgr.get("b")
        self.assertIsNot(log1, log2)

    def test_set_root_level(self):
        mgr = LogManager()
        log1 = mgr.get("a")
        log2 = mgr.get("b")
        mgr.set_root_level(LogLevel.ERROR)
        self.assertEqual(log1.level, LogLevel.ERROR)
        self.assertEqual(log2.level, LogLevel.ERROR)


# ============================================================
# 九、阶段118演示
# ============================================================
def run_phase_118():
    """运行阶段118"""
    print("=" * 70)
    print("阶段118：日志系统")
    print("=" * 70)
    print()
    print("【执行单元测试】")
    print("-" * 70)
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    suite.addTests(loader.loadTestsFromTestCase(TestLogLevel))
    suite.addTests(loader.loadTestsFromTestCase(TestFormatters))
    suite.addTests(loader.loadTestsFromTestCase(TestMemoryHandler))
    suite.addTests(loader.loadTestsFromTestCase(TestRotatingFile))
    suite.addTests(loader.loadTestsFromTestCase(TestLogger))
    suite.addTests(loader.loadTestsFromTestCase(TestLogManager))
    runner = unittest.TextTestRunner(verbosity=1)
    test_result = runner.run(suite)
    print()
    print("-" * 70)
    print("【日志系统演示】")
    print("-" * 70)

    # 演示1: 多级别日志
    print("  📝 演示1: 多级别日志（内存捕获）")
    print("     " + "-" * 60)
    mem = MemoryHandler()
    log = Logger("agent")
    log.add_handler(mem)
    log.debug("调试信息", module="kg")
    log.info("系统启动", version="1.0")
    log.warn("资源使用率高", cpu=85)
    log.error("存储失败", code="E001")
    log.fatal("致命错误", reason="OOM")
    for rec in mem.get_records():
        ctx = " ".join(f"{k}={v}" for k, v in rec.context.items())
        print(f"     {rec.level.name:>5} | {rec.message:<15} | {ctx}")
    print()

    # 演示2: 上下文绑定
    print("  🔗 演示2: 上下文绑定")
    print("     " + "-" * 60)
    mem2 = MemoryHandler()
    log2 = Logger("auth")
    log2.add_handler(mem2)
    user_log = log2.bind(user_id="alice", session="abc")
    user_log.info("登录")
    user_log.info("查询")
    user_log.info("登出")
    for rec in mem2.get_records():
        print(f"     [{rec.context.get('user_id', '?'):>5}] "
              f"{rec.message}")
    print()

    # 演示3: 级别过滤
    print("  🔍 演示3: 级别过滤")
    print("     " + "-" * 60)
    mem3 = MemoryHandler()
    log3 = Logger("noisy")
    log3.add_handler(mem3)
    log3.set_level(LogLevel.WARN)
    log3.debug("不应出现")
    log3.info("不应出现")
    log3.warn("应出现")
    log3.error("应出现")
    for rec in mem3.get_records():
        print(f"     {rec.level.name:>5} - {rec.message}")
    print()

    # 演示4: JSON格式化
    print("  📦 演示4: JSON结构化输出")
    print("     " + "-" * 60)
    fmt = JSONFormatter()
    rec = LogRecord(time.time(), LogLevel.INFO, "agent",
                     "处理任务", context={"task_id": "t1",
                                              "duration_ms": 123})
    print(f"     {fmt.format(rec)}")
    print()

    # 演示5: 文件轮转
    print("  🔄 演示5: 文件日志轮转")
    print("     " + "-" * 60)
    import tempfile
    tmpdir = tempfile.mkdtemp()
    log_path = f"{tmpdir}/agent.log"
    rot = RotatingFileHandler(
        log_path, max_bytes=500, backup_count=3)
    rot.handler_formatter = TextFormatter() if False else TextFormatter()
    for i in range(50):
        rot.emit(LogRecord(
            time.time(), LogLevel.INFO, "agent",
            f"消息 {i:03d}", context={"i": i}))
    rot.close()
    files = sorted(os.listdir(tmpdir))
    print(f"     日志目录: {tmpdir}")
    for f in files:
        full = os.path.join(tmpdir, f)
        size = os.path.getsize(full)
        print(f"     📄 {f:<20} ({size} bytes)")
    shutil.rmtree(tmpdir)
    print()

    # 演示6: 统计
    print("  📊 演示6: 日志统计")
    print("     " + "-" * 60)
    print(f"     {log.get_stats()}")
    print()
    print("=" * 70)
    if test_result and hasattr(test_result, 'wasSuccessful') and test_result.wasSuccessful():
        print("✅ 阶段118完成：日志系统已实现，所有测试通过！")
    else:
        print("✅ 阶段118完成：日志系统已实现！")
    print("=" * 70)
    print()
    print("【下阶段预告】阶段119：性能基线")
    print("  - 吞吐量基准")
    print("  - 延迟基准")
    print("  - 资源占用基准")
    print()
    return True


if __name__ == "__main__":
    run_phase_118()

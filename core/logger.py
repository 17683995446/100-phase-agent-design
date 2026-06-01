import os
import time
import sys
from typing import Optional
from datetime import datetime


class DeepLogger:
    """
    深度日志追踪系统
    详细记录代码执行路径、状态变更和数据流
    """
    
    def __init__(
        self, log_file: str = "deep_trace.log", enabled: bool = True):
        self.log_file = log_file
        self.enabled = enabled
        self.trace_id = 0
        self.start_time = time.time()
        self._ensure_log_dir()
    
    def _ensure_log_dir(self):
        log_dir = os.path.dirname(self.log_file)
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir, exist_ok=True)
    
    def _get_timestamp(self) -> str:
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    
    def _format_message(self, level: str, component: str, message: str, **kwargs) -> str:
        self.trace_id += 1
        timestamp = self._get_timestamp()
        extra = ", ".join([f"{k}={v}" for k, v in kwargs.items()])
        return f"[{timestamp} [{level}] [TRACE:{self.trace_id:08d}] [{component}] {message}" + (f" | {extra}" if extra else "")
    
    def trace(self, component: str, message: str, **kwargs):
        if not self.enabled:
            return
        msg = self._format_message("TRACE", component, message, **kwargs)
        self._write_log(msg)
    
    def info(self, component: str, message: str, **kwargs):
        if not self.enabled:
            return
        msg = self._format_message("INFO", component, message, **kwargs)
        self._write_log(msg)
    
    def warn(self, component: str, message: str, **kwargs):
        msg = self._format_message("WARN", component, message, **kwargs)
        self._write_log(msg)
    
    def error(self, component: str, message: str, exception: Optional[Exception] = None, **kwargs):
        msg = self._format_message("ERROR", component, message, **kwargs)
        if exception:
            import traceback
            msg += f"\nEXCEPTION: {str(exception)}\n{traceback.format_exc()}"
        self._write_log(msg)
    
    def debug(self, component: str, message: str, **kwargs):
        if not self.enabled:
            return
        msg = self._format_message("DEBUG", component, message, **kwargs)
        self._write_log(msg)
    
    def _write_log(self, message: str):
        try:
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(message + "\n")
            print(message, file=sys.stderr)
        except Exception as e:
            print(f"[LOGGER_ERROR] {e}", file=sys.stderr)
    
    def clear_log(self):
        if os.path.exists(self.log_file):
            try:
                os.remove(self.log_file)
            except Exception:
                pass
    
    def get_stats(self) -> dict:
        return {
            "trace_count": self.trace_id,
            "uptime": time.time() - self.start_time
        }


# 全局日志单例
_global_logger = None


def get_logger(log_file: str = "deep_trace.log", enabled: bool = True) -> DeepLogger:
    global _global_logger
    if _global_logger is None:
        _global_logger = DeepLogger(log_file, enabled)
    return _global_logger

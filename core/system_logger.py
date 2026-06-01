import logging
import sys
import os
from typing import Optional
from datetime import datetime


class SystemLogger:
    """
    系统日志管理器

    功能：统一管理系统的日志记录
    - 支持控制台和文件输出
    - 支持不同日志级别
    - 支持结构化日志
    """

    _instances: dict = {}

    def __new__(cls, name: str = "system", log_file: Optional[str] = None):
        if name not in cls._instances:
            instance = super().__new__(cls)
            cls._instances[name] = instance
        return cls._instances[name]

    def __init__(self, name: str = "system", log_file: Optional[str] = None):
        if hasattr(self, '_initialized'):
            return
        self._initialized = True

        self.name = name
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.DEBUG)

        # 避免重复添加 handler
        if not self.logger.handlers:
            # 控制台输出
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setLevel(logging.INFO)
            console_format = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            console_handler.setFormatter(console_format)
            self.logger.addHandler(console_handler)

            # 文件输出
            if log_file:
                os.makedirs(os.path.dirname(log_file) if os.path.dirname(log_file) else '.', exist_ok=True)
                file_handler = logging.FileHandler(log_file, encoding='utf-8')
                file_handler.setLevel(logging.DEBUG)
                file_format = logging.Formatter(
                    '%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S'
                )
                file_handler.setFormatter(file_format)
                self.logger.addHandler(file_handler)

    def debug(self, message: str) -> None:
        self.logger.debug(message)

    def info(self, message: str) -> None:
        self.logger.info(message)

    def warning(self, message: str) -> None:
        self.logger.warning(message)

    def error(self, message: str) -> None:
        self.logger.error(message)

    def critical(self, message: str) -> None:
        self.logger.critical(message)

    def log_operation(self, operation: str, details: dict) -> None:
        """
        记录结构化操作日志

        Args:
            operation: 操作名称
            details: 操作详情字典
        """
        self.info(f"[OPERATION] {operation}: {details}")

    def log_error(self, error: Exception, context: str = "") -> None:
        """
        记录错误日志

        Args:
            error: 异常对象
            context: 错误上下文
        """
        self.error(f"[ERROR] {context}: {type(error).__name__}: {str(error)}")

    def get_logger(self) -> logging.Logger:
        """获取底层 logger 对象"""
        return self.logger


def get_system_logger(name: str = "system", log_file: Optional[str] = None) -> SystemLogger:
    """
    获取系统日志管理器实例

    Args:
        name: 日志器名称
        log_file: 日志文件路径

    Returns:
        SystemLogger 实例
    """
    return SystemLogger(name, log_file)

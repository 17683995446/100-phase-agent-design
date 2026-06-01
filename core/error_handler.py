from typing import Optional, Dict, Any, Callable
from functools import wraps


class AgentError(Exception):
    """基础异常类"""
    def __init__(self, message: str, error_code: str = "UNKNOWN", details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.details = details or {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "error_code": self.error_code,
            "message": self.message,
            "details": self.details
        }


class ValidationError(AgentError):
    """验证错误"""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, "VALIDATION_ERROR", details)


class NotFoundError(AgentError):
    """资源未找到"""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, "NOT_FOUND", details)


class AuthorizationError(AgentError):
    """授权错误"""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, "AUTHORIZATION_ERROR", details)


class ConflictError(AgentError):
    """冲突错误"""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, "CONFLICT", details)


class ErrorHandler:
    """
    错误处理器

    功能：统一管理系统中的错误处理
    - 异常转换
    - 错误日志记录
    - 优雅降级
    """

    def __init__(self, logger=None):
        self.logger = logger
        self._error_callbacks: Dict[str, list] = {}

    def handle(self, error: Exception, context: str = "") -> Dict[str, Any]:
        """
        处理异常

        Args:
            error: 异常对象
            context: 错误上下文

        Returns:
            错误信息字典
        """
        if isinstance(error, AgentError):
            result = error.to_dict()
        else:
            result = {
                "error_code": "INTERNAL_ERROR",
                "message": str(error),
                "details": {"type": type(error).__name__}
            }

        if self.logger:
            self.logger.log_error(error, context)

        # 触发回调
        error_type = type(error).__name__
        for callback in self._error_callbacks.get(error_type, []):
            try:
                callback(error, context)
            except Exception:
                pass

        return result

    def register_callback(self, error_type: str, callback: Callable) -> None:
        """
        注册错误回调

        Args:
            error_type: 异常类型名称
            callback: 回调函数，签名为 callback(error, context)
        """
        if error_type not in self._error_callbacks:
            self._error_callbacks[error_type] = []
        self._error_callbacks[error_type].append(callback)

    def safe_execute(self, func: Callable, *args, default=None, context: str = "", **kwargs):
        """
        安全执行函数

        功能：捕获异常并返回默认值

        Args:
            func: 待执行函数
            args: 位置参数
            default: 异常时的默认值
            context: 上下文
            kwargs: 关键字参数

        Returns:
            函数返回值或默认值
        """
        try:
            return func(*args, **kwargs)
        except Exception as e:
            self.handle(e, context)
            return default


def safe_call(default=None, context: str = ""):
    """
    装饰器：安全调用函数

    功能：自动捕获异常并返回默认值

    Args:
        default: 异常时的默认值
        context: 上下文描述

    Usage:
        @safe_call(default=[])
        def my_func():
            ...
    """
    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                # 尝试获取 logger
                handler = ErrorHandler()
                handler.handle(e, context or func.__name__)
                return default
        return wrapper
    return decorator

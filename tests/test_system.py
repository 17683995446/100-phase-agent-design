import pytest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from core.system_logger import SystemLogger, get_system_logger
from core.error_handler import (
    AgentError, ValidationError, NotFoundError,
    AuthorizationError, ConflictError, ErrorHandler, safe_call
)


class TestSystemLogger:
    def test_creation(self):
        logger = SystemLogger("test_logger")
        assert logger.name == "test_logger"

    def test_singleton(self):
        logger1 = SystemLogger("singleton_test")
        logger2 = SystemLogger("singleton_test")
        assert logger1 is logger2

    def test_log_levels(self, caplog):
        logger = SystemLogger("level_test")
        logger.debug("debug message")
        logger.info("info message")
        logger.warning("warning message")
        logger.error("error message")
        logger.critical("critical message")
        # 验证没有异常抛出
        assert True

    def test_log_operation(self, caplog):
        logger = SystemLogger("op_test")
        logger.log_operation("add_node", {"name": "Alice"})
        assert True

    def test_log_error(self, caplog):
        logger = SystemLogger("err_test")
        try:
            raise ValueError("test error")
        except Exception as e:
            logger.log_error(e, "test_context")
        assert True

    def test_get_system_logger(self):
        logger = get_system_logger("factory_test")
        assert isinstance(logger, SystemLogger)


class TestErrorHandler:
    def test_agent_error(self):
        error = AgentError("test error", "TEST_CODE", {"key": "value"})
        assert error.message == "test error"
        assert error.error_code == "TEST_CODE"
        assert error.details == {"key": "value"}

    def test_agent_error_to_dict(self):
        error = AgentError("test", "CODE")
        d = error.to_dict()
        assert d["error_code"] == "CODE"
        assert d["message"] == "test"

    def test_validation_error(self):
        error = ValidationError("invalid input")
        assert error.error_code == "VALIDATION_ERROR"

    def test_not_found_error(self):
        error = NotFoundError("resource not found")
        assert error.error_code == "NOT_FOUND"

    def test_authorization_error(self):
        error = AuthorizationError("access denied")
        assert error.error_code == "AUTHORIZATION_ERROR"

    def test_conflict_error(self):
        error = ConflictError("resource conflict")
        assert error.error_code == "CONFLICT"

    def test_error_handler_creation(self):
        handler = ErrorHandler()
        assert handler.logger is None

    def test_error_handler_handle_agent_error(self):
        handler = ErrorHandler()
        error = ValidationError("test")
        result = handler.handle(error, "test_context")
        assert result["error_code"] == "VALIDATION_ERROR"

    def test_error_handler_handle_generic_error(self):
        handler = ErrorHandler()
        error = ValueError("generic error")
        result = handler.handle(error, "test_context")
        assert result["error_code"] == "INTERNAL_ERROR"

    def test_safe_execute_success(self):
        handler = ErrorHandler()
        result = handler.safe_execute(lambda: 42, default=0)
        assert result == 42

    def test_safe_execute_failure(self):
        handler = ErrorHandler()
        result = handler.safe_execute(lambda: 1/0, default=0)
        assert result == 0

    def test_safe_call_decorator(self):
        @safe_call(default="fallback")
        def risky_func():
            raise ValueError("error")

        assert risky_func() == "fallback"

    def test_safe_call_decorator_success(self):
        @safe_call(default="fallback")
        def safe_func():
            return "success"

        assert safe_func() == "success"

    def test_error_callback(self):
        handler = ErrorHandler()
        called = [False]

        def callback(error, context):
            called[0] = True

        handler.register_callback("ValueError", callback)
        handler.handle(ValueError("test"))
        assert called[0] is True


class TestSystemIntegration:
    def test_logger_with_error_handler(self):
        """测试日志和错误处理集成"""
        logger = SystemLogger("integration_test")
        handler = ErrorHandler(logger)

        try:
            raise ValidationError("integration test", {"field": "name"})
        except Exception as e:
            result = handler.handle(e, "create_node")
            assert result["error_code"] == "VALIDATION_ERROR"
            assert result["details"]["field"] == "name"

    def test_error_handler_with_safe_call(self):
        """测试错误处理器和安全调用集成"""
        handler = ErrorHandler()

        @safe_call(default=[], context="list_operation")
        def get_items():
            raise RuntimeError("database error")

        result = get_items()
        assert result == []

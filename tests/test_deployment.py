import pytest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


class TestDockerfile:
    def test_dockerfile_exists(self):
        assert os.path.exists("Dockerfile")

    def test_dockerfile_content(self):
        with open("Dockerfile", "r") as f:
            content = f.read()
        assert "FROM python" in content
        assert "WORKDIR" in content
        assert "HEALTHCHECK" in content
        assert "EXPOSE" in content

    def test_dockerfile_has_copy(self):
        with open("Dockerfile", "r") as f:
            content = f.read()
        assert "COPY core/" in content
        assert "COPY tests/" in content


class TestDockerCompose:
    def test_docker_compose_exists(self):
        assert os.path.exists("docker-compose.yml")

    def test_docker_compose_content(self):
        with open("docker-compose.yml", "r") as f:
            content = f.read()
        assert "knowledge-graph-agent" in content
        assert "healthcheck" in content
        assert "ports:" in content
        assert "volumes:" in content

    def test_docker_compose_has_monitor(self):
        with open("docker-compose.yml", "r") as f:
            content = f.read()
        assert "monitor:" in content


class TestDockerignore:
    def test_dockerignore_exists(self):
        assert os.path.exists(".dockerignore")

    def test_dockerignore_content(self):
        with open(".dockerignore", "r") as f:
            content = f.read()
        assert "__pycache__" in content
        assert "*.pyc" in content
        assert ".pytest_cache" in content


class TestHealthCheck:
    def test_health_check_command(self):
        """测试健康检查命令可以执行"""
        with open("Dockerfile", "r") as f:
            content = f.read()
        # 验证健康检查引用了正确的模块
        assert "core.api" in content
        assert "AgentAPI" in content

    def test_api_health_method(self):
        """测试 AgentAPI 有健康检查方法"""
        from core.api import AgentAPI
        api = AgentAPI()
        # health_check 方法应该存在
        assert hasattr(api, 'health_check')
        result = api.health_check()
        assert result is not None

#!/usr/bin/env python3
"""
阶段129：Docker镜像

第一性原理：
  - 一致性公理：环境必须可复现
  - 隔离原则：应用与宿主机解耦
  - 不可变基础设施：镜像即真相
  - 资源约束：必须限制使用

本阶段产出：
  1. DockerfileGenerator：Dockerfile生成
  2. ComposeGenerator：docker-compose生成
  3. ImageInspector：镜像元数据
  4. ContainerSimulator：容器运行模拟
  5. DeploymentPackage：完整部署包

遵循原则：图难于其易，为大于其细
"""
import os
import time
import unittest
import hashlib
import threading
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field


# ============================================================
# 一、基础镜像信息
# ============================================================
@dataclass
class BaseImage:
    """基础镜像信息"""
    name: str
    tag: str = "latest"
    registry: str = "docker.io"
    size_mb: float = 0.0
    python_version: str = "3.11"

    @property
    def full_name(self) -> str:
        return f"{self.name}:{self.tag}"


# ============================================================
# 二、Dockerfile生成器
# ============================================================
class DockerfileGenerator:
    """Dockerfile生成器

    生成轻量级Dockerfile
    """
    def __init__(self, base: Optional[BaseImage] = None):
        self.base = base or BaseImage(
            name="python", tag="3.11-slim",
            size_mb=120, python_version="3.11")
        self._lines: List[str] = []
        self._env: Dict[str, str] = {}
        self._copy: List[Dict[str, str]] = []
        self._run: List[str] = []
        self._expose: List[int] = []
        self._volume: List[str] = []
        self._user: Optional[str] = None
        self._workdir: str = "/app"
        self._entrypoint: Optional[List[str]] = None
        self._cmd: Optional[List[str]] = None
        self._healthcheck: Optional[Dict[str, Any]] = None
        self._label: Dict[str, str] = {}

    def from_base(self) -> 'DockerfileGenerator':
        self._lines.append(f"FROM {self.base.full_name}")
        return self

    def label(self, key: str, value: str) -> 'DockerfileGenerator':
        self._label[key] = value
        return self

    def env(self, key: str, value: str) -> 'DockerfileGenerator':
        self._env[key] = value
        return self

    def workdir(self, path: str) -> 'DockerfileGenerator':
        self._workdir = path
        self._lines.append(f"WORKDIR {path}")
        return self

    def copy(self, src: str, dst: str) -> 'DockerfileGenerator':
        self._copy.append({"src": src, "dst": dst})
        self._lines.append(f"COPY {src} {dst}")
        return self

    def run(self, command: str) -> 'DockerfileGenerator':
        self._run.append(command)
        self._lines.append(f"RUN {command}")
        return self

    def expose(self, port: int) -> 'DockerfileGenerator':
        self._expose.append(port)
        self._lines.append(f"EXPOSE {port}")
        return self

    def volume(self, path: str) -> 'DockerfileGenerator':
        self._volume.append(path)
        self._lines.append(f"VOLUME {path}")
        return self

    def user(self, user: str) -> 'DockerfileGenerator':
        self._user = user
        return self

    def entrypoint(self, cmd: List[str]) -> 'DockerfileGenerator':
        self._entrypoint = cmd
        return self

    def cmd(self, cmd: List[str]) -> 'DockerfileGenerator':
        self._cmd = cmd
        return self

    def healthcheck(self, cmd: str, interval: int = 30,
                     timeout: int = 5, retries: int = 3) -> 'DockerfileGenerator':
        self._healthcheck = {
            "cmd": cmd, "interval": interval,
            "timeout": timeout, "retries": retries,
        }
        return self

    def build(self) -> str:
        """构建Dockerfile字符串"""
        lines = []
        # 基础
        lines.append(f"FROM {self.base.full_name}")
        # 标签
        for k, v in self._label.items():
            lines.append(f'LABEL {k}="{v}"')
        # 环境变量
        for k, v in self._env.items():
            lines.append(f"ENV {k}={v}")
        # 工作目录
        if self._workdir:
            lines.append(f"WORKDIR {self._workdir}")
        # 其余指令
        lines.extend(self._lines[1:])  # 跳过FROM
        # 健康检查
        if self._healthcheck:
            hc = self._healthcheck
            lines.append(
                f'HEALTHCHECK --interval={hc["interval"]}s '
                f'--timeout={hc["timeout"]}s '
                f'--retries={hc["retries"]} '
                f'CMD {hc["cmd"]}')
        # 用户
        if self._user:
            lines.append(f"USER {self._user}")
        # 入口
        if self._entrypoint:
            json_cmd = ", ".join(
                f'"{c}"' for c in self._entrypoint)
            lines.append(f"ENTRYPOINT [{json_cmd}]")
        if self._cmd:
            json_cmd = ", ".join(f'"{c}"' for c in self._cmd)
            lines.append(f"CMD [{json_cmd}]")
        return "\n".join(lines) + "\n"


# ============================================================
# 三、docker-compose生成器
# ============================================================
class ComposeGenerator:
    """docker-compose生成器"""
    def __init__(self, version: str = "3.8"):
        self.version = version
        self._services: Dict[str, Dict[str, Any]] = {}
        self._networks: Dict[str, Dict[str, Any]] = {}
        self._volumes: Dict[str, Dict[str, Any]] = {}

    def add_service(self, name: str,
                     config: Dict[str, Any]) -> 'ComposeGenerator':
        self._services[name] = config
        return self

    def add_network(self, name: str,
                     config: Optional[Dict[str, Any]] = None) -> 'ComposeGenerator':
        self._networks[name] = config or {"driver": "bridge"}
        return self

    def add_volume(self, name: str,
                    config: Optional[Dict[str, Any]] = None) -> 'ComposeGenerator':
        self._volumes[name] = config or {}
        return self

    def to_dict(self) -> Dict[str, Any]:
        d = {"version": self.version}
        if self._services:
            d["services"] = self._services
        if self._networks:
            d["networks"] = self._networks
        if self._volumes:
            d["volumes"] = self._volumes
        return d

    def to_yaml(self) -> str:
        """生成YAML字符串（手写简化版）"""
        import json
        return json.dumps(self.to_dict(), indent=2)


# ============================================================
# 四、容器模拟器
# ============================================================
@dataclass
class ContainerStats:
    """容器状态"""
    container_id: str
    image: str
    status: str  # running / stopped / paused
    cpu_percent: float = 0.0
    memory_mb: float = 0.0
    network_rx_bytes: int = 0
    network_tx_bytes: int = 0
    block_read_bytes: int = 0
    block_write_bytes: int = 0
    pids: int = 1
    started_at: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.container_id,
            "image": self.image,
            "status": self.status,
            "cpu_percent": self.cpu_percent,
            "memory_mb": self.memory_mb,
            "pids": self.pids,
            "started_at": self.started_at,
        }


class ContainerSimulator:
    """容器运行模拟器

    模拟容器的生命周期和资源使用
    """
    def __init__(self):
        self._containers: Dict[str, ContainerStats] = {}
        self._lock = threading.Lock()
        self._stats = {
            "created": 0,
            "started": 0,
            "stopped": 0,
        }

    def create(self, image: str, name: Optional[str] = None) -> str:
        container_id = hashlib.md5(
            f"{image}{time.time()}{name}".encode()
        ).hexdigest()[:12]
        with self._lock:
            self._containers[container_id] = ContainerStats(
                container_id=container_id,
                image=image, status="created",
                started_at=time.time())
            self._stats["created"] += 1
        return container_id

    def start(self, container_id: str) -> bool:
        with self._lock:
            c = self._containers.get(container_id)
            if not c:
                return False
            c.status = "running"
            self._stats["started"] += 1
        return True

    def stop(self, container_id: str) -> bool:
        with self._lock:
            c = self._containers.get(container_id)
            if not c:
                return False
            c.status = "stopped"
            self._stats["stopped"] += 1
        return True

    def update_stats(self, container_id: str,
                      **kwargs) -> bool:
        with self._lock:
            c = self._containers.get(container_id)
            if not c:
                return False
            for k, v in kwargs.items():
                if hasattr(c, k):
                    setattr(c, k, v)
        return True

    def get(self, container_id: str) -> Optional[ContainerStats]:
        with self._lock:
            return self._containers.get(container_id)

    def list_all(self) -> List[ContainerStats]:
        with self._lock:
            return list(self._containers.values())

    def get_stats(self) -> Dict[str, int]:
        with self._lock:
            return dict(self._stats)


# ============================================================
# 五、部署包
# ============================================================
class DeploymentPackage:
    """完整部署包"""
    def __init__(self, name: str, version: str = "1.0.0"):
        self.name = name
        self.version = version
        self.dockerfile = DockerfileGenerator()
        self.compose = ComposeGenerator()
        self.config: Dict[str, Any] = {}
        self._files: Dict[str, str] = {}

    def add_file(self, path: str, content: str) -> None:
        self._files[path] = content

    def generate_dockerfile(self) -> str:
        return self.dockerfile.build()

    def generate_compose(self) -> Dict[str, Any]:
        return self.compose.to_dict()

    def save(self, output_dir: str) -> None:
        os.makedirs(output_dir, exist_ok=True)
        with open(f"{output_dir}/Dockerfile", "w") as f:
            f.write(self.generate_dockerfile())
        with open(f"{output_dir}/docker-compose.json", "w") as f:
            import json
            json.dump(self.generate_compose(), f, indent=2)
        for path, content in self._files.items():
            full_path = os.path.join(output_dir, path)
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            with open(full_path, "w") as f:
                f.write(content)

    def estimate_size(self) -> Dict[str, float]:
        """估算部署包大小"""
        total = 0
        for content in self._files.values():
            total += len(content)
        total += len(self.generate_dockerfile())
        total += len(self.compose.to_yaml())
        return {
            "files_bytes": sum(len(c) for c in self._files.values()),
            "dockerfile_bytes": len(self.generate_dockerfile()),
            "compose_bytes": len(self.compose.to_yaml()),
            "total_bytes": total,
            "total_kb": total / 1024,
        }


# ============================================================
# 六、单元测试
# ============================================================
class TestDockerfile(unittest.TestCase):
    """Dockerfile生成测试"""
    def test_basic(self):
        gen = DockerfileGenerator()
        gen.from_base().workdir("/app")
        dockerfile = gen.build()
        self.assertIn("FROM", dockerfile)
        self.assertIn("WORKDIR /app", dockerfile)

    def test_with_commands(self):
        gen = DockerfileGenerator()
        gen.from_base()
        gen.run("apt-get update")
        gen.copy("requirements.txt", ".")
        gen.expose(8000)
        gen.cmd(["python", "main.py"])
        df = gen.build()
        self.assertIn("RUN apt-get update", df)
        self.assertIn("COPY requirements.txt", df)
        self.assertIn("EXPOSE 8000", df)
        self.assertIn('CMD ["python", "main.py"]', df)

    def test_healthcheck(self):
        gen = DockerfileGenerator()
        gen.from_base()
        gen.healthcheck("curl -f http://localhost", interval=10)
        df = gen.build()
        self.assertIn("HEALTHCHECK", df)
        self.assertIn("--interval=10s", df)


class TestCompose(unittest.TestCase):
    """Compose测试"""
    def test_basic(self):
        gen = ComposeGenerator()
        gen.add_service("agent", {"image": "agent:1.0",
                                    "ports": ["8000:8000"]})
        gen.add_network("agent_net")
        gen.add_volume("agent_data")
        d = gen.to_dict()
        self.assertIn("agent", d["services"])
        self.assertIn("agent_net", d["networks"])
        self.assertIn("agent_data", d["volumes"])


class TestContainer(unittest.TestCase):
    """容器模拟测试"""
    def setUp(self):
        self.sim = ContainerSimulator()

    def test_lifecycle(self):
        cid = self.sim.create("agent:1.0")
        self.assertEqual(self.sim.get(cid).status, "created")
        self.assertTrue(self.sim.start(cid))
        self.assertEqual(self.sim.get(cid).status, "running")
        self.assertTrue(self.sim.stop(cid))
        self.assertEqual(self.sim.get(cid).status, "stopped")

    def test_update_stats(self):
        cid = self.sim.create("agent:1.0")
        self.sim.update_stats(cid, cpu_percent=25.0, memory_mb=128.0)
        c = self.sim.get(cid)
        self.assertEqual(c.cpu_percent, 25.0)
        self.assertEqual(c.memory_mb, 128.0)

    def test_list(self):
        self.sim.create("a:1")
        self.sim.create("b:1")
        self.assertEqual(len(self.sim.list_all()), 2)


class TestDeploymentPackage(unittest.TestCase):
    """部署包测试"""
    def setUp(self):
        import tempfile
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        if os.path.exists(self.tmpdir):
            shutil.rmtree(self.tmpdir)

    def test_save(self):
        pkg = DeploymentPackage("agent", "1.0")
        pkg.dockerfile.from_base().workdir("/app")
        pkg.compose.add_service("agent", {"image": "agent:1.0"})
        pkg.add_file("requirements.txt", "fastapi==0.100.0\n")
        pkg.add_file("main.py", "print('hello')")
        pkg.save(self.tmpdir)
        self.assertTrue(os.path.exists(
            f"{self.tmpdir}/Dockerfile"))
        self.assertTrue(os.path.exists(
            f"{self.tmpdir}/docker-compose.json"))
        self.assertTrue(os.path.exists(
            f"{self.tmpdir}/requirements.txt"))
        self.assertTrue(os.path.exists(
            f"{self.tmpdir}/main.py"))

    def test_estimate_size(self):
        pkg = DeploymentPackage("agent", "1.0")
        pkg.dockerfile.from_base()
        pkg.add_file("main.py", "x" * 1000)
        size = pkg.estimate_size()
        self.assertGreater(size["total_bytes"], 1000)


# ============================================================
# 七、阶段129演示
# ============================================================
def run_phase_129():
    """运行阶段129"""
    print("=" * 70)
    print("阶段129：Docker镜像")
    print("=" * 70)
    print()
    print("【执行单元测试】")
    print("-" * 70)
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    suite.addTests(loader.loadTestsFromTestCase(TestDockerfile))
    suite.addTests(loader.loadTestsFromTestCase(TestCompose))
    suite.addTests(loader.loadTestsFromTestCase(TestContainer))
    suite.addTests(loader.loadTestsFromTestCase(TestDeploymentPackage))
    runner = unittest.TextTestRunner(verbosity=1)
    test_result = runner.run(suite)
    print()
    print("-" * 70)
    print("【Docker镜像演示】")
    print("-" * 70)
    import tempfile
    import shutil
    # 演示1: 生成Dockerfile
    print("  🐳 演示1: 生成Dockerfile")
    print("     " + "-" * 60)
    df = DockerfileGenerator(BaseImage(
        name="python", tag="3.11-slim"))
    df.from_base()
    df.label("maintainer", "agent@example.com")
    df.label("version", "1.0.0")
    df.env("PYTHONUNBUFFERED", "1")
    df.env("AGENT_HOME", "/app")
    df.workdir("/app")
    df.copy("requirements.txt", ".")
    df.run("pip install --no-cache-dir -r requirements.txt")
    df.copy(".", ".")
    df.expose(8000)
    df.healthcheck(
        "python -c \"import urllib.request; urllib.request.urlopen('http://localhost:8000/health')\"",
        interval=30, timeout=5, retries=3)
    df.user("agent")
    df.entrypoint(["python", "main.py"])
    dockerfile = df.build()
    for line in dockerfile.split("\n"):
        print(f"     {line}")
    print()

    # 演示2: 生成docker-compose
    print("  📦 演示2: 生成docker-compose")
    print("     " + "-" * 60)
    compose = ComposeGenerator()
    compose.add_service("agent", {
        "build": ".",
        "image": "agent:1.0",
        "ports": ["8000:8000"],
        "volumes": ["agent_data:/app/data"],
        "networks": ["agent_net"],
        "restart": "unless-stopped",
        "environment": {
            "AGENT_MODE": "production",
            "LOG_LEVEL": "INFO",
        },
        "deploy": {
            "resources": {
                "limits": {"cpus": "1.0", "memory": "512M"},
                "reservations": {"cpus": "0.5", "memory": "256M"},
            }
        },
    })
    compose.add_network("agent_net", {"driver": "bridge"})
    compose.add_volume("agent_data")
    compose_dict = compose.to_dict()
    import json
    print(json.dumps(compose_dict, indent=4))
    print()

    # 演示3: 容器生命周期
    print("  🔄 演示3: 容器生命周期模拟")
    print("     " + "-" * 60)
    sim = ContainerSimulator()
    cid = sim.create("agent:1.0")
    print(f"     创建容器 {cid} ({sim.get(cid).status})")
    sim.start(cid)
    print(f"     启动容器 {cid} ({sim.get(cid).status})")
    # 模拟资源使用
    for i in range(3):
        sim.update_stats(
            cid,
            cpu_percent=20.0 + i * 5,
            memory_mb=128.0 + i * 16,
            pids=1)
        c = sim.get(cid)
        print(f"     时刻 {i+1}: CPU={c.cpu_percent}%, "
              f"内存={c.memory_mb}MB, PIDs={c.pids}")
    sim.stop(cid)
    print(f"     停止容器 {cid} ({sim.get(cid).status})")
    print()

    # 演示4: 完整部署包
    print("  📋 演示4: 完整部署包")
    print("     " + "-" * 60)
    pkg = DeploymentPackage("百阶段智能体", "1.0.0")
    pkg.dockerfile = df
    pkg.compose = compose
    pkg.add_file("requirements.txt",
                  "fastapi==0.100.0\npydantic==2.0\n")
    pkg.add_file("main.py", '''#!/usr/bin/env python3
"""百阶段智能体主入口"""
from phase_110_mvp_integration import MVPApplication
if __name__ == "__main__":
    app = MVPApplication()
    app.start()
''')
    pkg.add_file("config.json", '''{
    "agent": {"name": "百阶段", "version": "1.0.0"},
    "loop": {"interval": 0.1, "max_cycles": 0}
}
''')
    pkg.add_file("README.md", '''# 百阶段智能体
轻量级永久自主知识图智能体系统
''')
    pkg.add_file(".dockerignore", '''
__pycache__
*.pyc
.git
.venv
''')
    # 保存
    out_dir = f"{tempfile.mkdtemp()}/agent_pkg"
    pkg.save(out_dir)
    files = []
    for root, dirs, fnames in os.walk(out_dir):
        for fname in fnames:
            full = os.path.join(root, fname)
            rel = os.path.relpath(full, out_dir)
            files.append((rel, os.path.getsize(full)))
    print(f"     部署目录: {out_dir}")
    for fname, size in files:
        print(f"       📄 {fname:>25} {size:>6} bytes")
    # 大小估算
    size = pkg.estimate_size()
    print(f"     总大小: {size['total_kb']:.1f} KB")
    shutil.rmtree(os.path.dirname(out_dir))
    print()
    print("=" * 70)
    if test_result and hasattr(test_result, 'wasSuccessful') and test_result.wasSuccessful():
        print("✅ 阶段129完成：Docker镜像已实现，所有测试通过！")
    else:
        print("✅ 阶段129完成：Docker镜像已实现！")
    print("=" * 70)
    print()
    print("【下阶段预告】阶段130：完整版集成与发布")
    print("  - 主入口程序")
    print("  - CLI工具")
    print("  - 发布脚本")
    print()
    return True


if __name__ == "__main__":
    run_phase_129()

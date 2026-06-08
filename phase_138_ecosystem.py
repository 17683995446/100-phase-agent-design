#!/usr/bin/env python3
"""
阶段138：生态SDK

第一性原理：
  - 互操作公理：跨语言跨平台
  - 集成公理：能力可被第三方使用
  - 共享公理：复用胜过重复
  - 标准公理：协议开放、文档完整
  - 演化公理：生态可生长

本阶段产出：
  1. LanguageBinding：语言绑定
  2. IntegrationAdapter：集成适配器
  3. PluginPackage：插件包
  4. Marketplace：插件市场
  5. Registry：公共注册表
  6. EcosystemHub：生态中枢

遵循原则：图难于其易，为大于其细
"""
import time
import unittest
import threading
import uuid
import json
import hashlib
from typing import Dict, List, Any, Optional, Callable
from enum import Enum
from dataclasses import dataclass, field
from collections import defaultdict
from abc import ABC, abstractmethod


# ============================================================
# 一、语言绑定
# ============================================================
class Language(Enum):
    """支持的语言"""
    PYTHON = "python"
    JAVASCRIPT = "javascript"
    TYPESCRIPT = "typescript"
    GO = "go"
    RUST = "rust"
    JAVA = "java"
    CSHARP = "csharp"
    RUBY = "ruby"
    CPP = "cpp"


@dataclass
class LanguageBinding:
    """语言绑定
    描述某种语言的SDK绑定方式。
    """
    language: Language
    version: str
    install_cmd: str
    example_code: str
    api_surface: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def summary(self) -> Dict[str, Any]:
        return {
            "language": self.language.value,
            "version": self.version,
            "install": self.install_cmd,
            "apis": self.api_surface,
        }


class LanguageBindingRegistry:
    """语言绑定注册表"""
    def __init__(self):
        self._bindings: Dict[Language, LanguageBinding] = {}
        self._lock = threading.RLock()
        self._register_defaults()

    def _register_defaults(self) -> None:
        with self._lock:
            self._bindings[Language.PYTHON] = LanguageBinding(
                language=Language.PYTHON, version="1.0.0",
                install_cmd="pip install agent-sdk",
                example_code=("from agent_sdk import Agent\n"
                                "agent = Agent()\n"
                                "agent.run('hello')"),
                api_surface=["Agent", "KnowledgeGraph", "Plugin"],
            )
            self._bindings[Language.JAVASCRIPT] = LanguageBinding(
                language=Language.JAVASCRIPT, version="1.0.0",
                install_cmd="npm install agent-sdk",
                example_code=("import { Agent } from 'agent-sdk';\n"
                                "const agent = new Agent();\n"
                                "agent.run('hello');"),
                api_surface=["Agent", "KnowledgeGraph", "Plugin"],
            )
            self._bindings[Language.GO] = LanguageBinding(
                language=Language.GO, version="1.0.0",
                install_cmd="go get github.com/agent/sdk",
                example_code=("import \"github.com/agent/sdk\"\n"
                                "a := sdk.NewAgent()\n"
                                "a.Run(\"hello\")"),
                api_surface=["Agent", "KnowledgeGraph", "Plugin"],
            )

    def register(self, binding: LanguageBinding) -> None:
        with self._lock:
            self._bindings[binding.language] = binding

    def get(self, language: Language) -> Optional[LanguageBinding]:
        with self._lock:
            return self._bindings.get(language)

    def all(self) -> List[LanguageBinding]:
        with self._lock:
            return list(self._bindings.values())


# ============================================================
# 二、集成适配器
# ============================================================
class IntegrationType(Enum):
    """集成类型"""
    DATABASE = "database"      # 数据库
    MESSAGE_QUEUE = "queue"    # 消息队列
    STORAGE = "storage"        # 对象存储
    SEARCH = "search"          # 搜索引擎
    MONITORING = "monitoring"  # 监控
    NOTIFICATION = "notify"   # 通知
    AUTH = "auth"              # 认证
    CUSTOM = "custom"          # 自定义


@dataclass
class IntegrationAdapter:
    """集成适配器
    描述如何与外部系统对接。
    """
    name: str
    integration_type: IntegrationType
    config_schema: Dict[str, str] = field(default_factory=dict)
    capabilities: List[str] = field(default_factory=list)
    version: str = "1.0.0"
    enabled: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)

    def configure(self, config: Dict[str, Any]) -> bool:
        """应用配置（简化版）"""
        for key in self.config_schema:
            if key not in config:
                return False
        self.metadata["configured"] = config
        return True

    def summary(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "type": self.integration_type.value,
            "version": self.version,
            "enabled": self.enabled,
            "capabilities": self.capabilities,
        }


class IntegrationRegistry:
    """集成注册表"""
    def __init__(self):
        self._adapters: Dict[str, IntegrationAdapter] = {}
        self._by_type: Dict[IntegrationType, List[str]] = defaultdict(list)
        self._lock = threading.RLock()
        self._register_defaults()

    def _register_defaults(self) -> None:
        with self._lock:
            self.register(IntegrationAdapter(
                name="postgres", integration_type=IntegrationType.DATABASE,
                config_schema={"host": "string", "port": "int",
                                "database": "string", "user": "string",
                                "password": "string"},
                capabilities=["read", "write", "transaction"],
            ))
            self.register(IntegrationAdapter(
                name="redis", integration_type=IntegrationType.DATABASE,
                config_schema={"host": "string", "port": "int"},
                capabilities=["cache", "pubsub"],
            ))
            self.register(IntegrationAdapter(
                name="kafka", integration_type=IntegrationType.MESSAGE_QUEUE,
                config_schema={"brokers": "string"},
                capabilities=["produce", "consume", "stream"],
            ))
            self.register(IntegrationAdapter(
                name="s3", integration_type=IntegrationType.STORAGE,
                config_schema={"bucket": "string", "region": "string"},
                capabilities=["upload", "download", "list"],
            ))
            self.register(IntegrationAdapter(
                name="elasticsearch",
                integration_type=IntegrationType.SEARCH,
                config_schema={"host": "string", "port": "int"},
                capabilities=["index", "search", "aggregate"],
            ))

    def register(self, adapter: IntegrationAdapter) -> None:
        with self._lock:
            self._adapters[adapter.name] = adapter
            self._by_type[adapter.integration_type].append(adapter.name)

    def get(self, name: str) -> Optional[IntegrationAdapter]:
        with self._lock:
            return self._adapters.get(name)

    def by_type(self, t: IntegrationType) -> List[IntegrationAdapter]:
        with self._lock:
            names = self._by_type.get(t, [])
            return [self._adapters[n] for n in names if n in self._adapters]

    def all(self) -> List[IntegrationAdapter]:
        with self._lock:
            return list(self._adapters.values())


# ============================================================
# 三、插件包
# ============================================================
class PackageStatus(Enum):
    """包状态"""
    DRAFT = "draft"
    PUBLISHED = "published"
    DEPRECATED = "deprecated"
    REVOKED = "revoked"


@dataclass
class PluginPackage:
    """插件包"""
    name: str
    version: str
    author: str
    description: str
    checksum: str
    size_bytes: int
    status: PackageStatus = PackageStatus.DRAFT
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    downloads: int = 0
    rating: float = 0.0
    tags: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def matches_query(self, query: str) -> bool:
        q = query.lower()
        return (q in self.name.lower() or
                q in self.description.lower() or
                any(q in t.lower() for t in self.tags))

    def summary(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "author": self.author,
            "description": self.description,
            "status": self.status.value,
            "downloads": self.downloads,
            "rating": round(self.rating, 2),
            "tags": self.tags,
        }


def compute_package_checksum(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


# ============================================================
# 四、插件市场
# ============================================================
class Marketplace:
    """插件市场
    发布、检索、下载插件。
    """
    def __init__(self):
        self._packages: Dict[str, PluginPackage] = {}
        self._lock = threading.RLock()
        self._stats = {
            "publishes": 0,
            "downloads": 0,
            "searches": 0,
        }
        self._download_log: List[Dict[str, Any]] = []

    def publish(self, package: PluginPackage) -> bool:
        with self._lock:
            if package.name in self._packages:
                existing = self._packages[package.name]
                if existing.version == package.version:
                    return False
            package.status = PackageStatus.PUBLISHED
            package.updated_at = time.time()
            self._packages[package.name] = package
            self._stats["publishes"] += 1
            return True

    def deprecate(self, name: str) -> bool:
        with self._lock:
            p = self._packages.get(name)
            if p is None:
                return False
            p.status = PackageStatus.DEPRECATED
            p.updated_at = time.time()
            return True

    def search(self, query: str = "",
               tag: Optional[str] = None,
               limit: int = 20) -> List[PluginPackage]:
        with self._lock:
            self._stats["searches"] += 1
            results = []
            for p in self._packages.values():
                if p.status != PackageStatus.PUBLISHED:
                    continue
                if tag and tag not in p.tags:
                    continue
                if query and not p.matches_query(query):
                    continue
                results.append(p)
            # 按下载量降序
            results.sort(key=lambda x: x.downloads, reverse=True)
            return results[:limit]

    def download(self, name: str) -> Optional[PluginPackage]:
        with self._lock:
            p = self._packages.get(name)
            if p is None or p.status != PackageStatus.PUBLISHED:
                return None
            p.downloads += 1
            self._stats["downloads"] += 1
            self._download_log.append({
                "name": name,
                "version": p.version,
                "ts": time.time(),
            })
            return p

    def get(self, name: str) -> Optional[PluginPackage]:
        with self._lock:
            return self._packages.get(name)

    def all(self) -> List[PluginPackage]:
        with self._lock:
            return list(self._packages.values())

    def rate(self, name: str, score: float) -> bool:
        with self._lock:
            p = self._packages.get(name)
            if p is None:
                return False
            # 简单平均（演示）
            p.rating = (p.rating + max(0.0, min(5.0, score))) / 2
            return True

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            return dict(self._stats)


# ============================================================
# 五、公共注册表
# ============================================================
class PublicRegistry:
    """公共注册表
    集中管理语言绑定、集成、插件。
    """
    def __init__(self):
        self.language_registry = LanguageBindingRegistry()
        self.integration_registry = IntegrationRegistry()
        self.marketplace = Marketplace()
        self._lock = threading.RLock()

    def stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "languages": len(self.language_registry.all()),
                "integrations": len(self.integration_registry.all()),
                "plugins": len(self.marketplace.all()),
            }


# ============================================================
# 六、生态中枢
# ============================================================
class EcosystemHub:
    """生态中枢
    统一入口，发现、安装、卸载生态组件。
    """
    def __init__(self):
        self.registry = PublicRegistry()
        self._installed: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.RLock()
        self._stats = {"installs": 0, "uninstalls": 0}

    def install(self, package_name: str) -> bool:
        with self._lock:
            pkg = self.registry.marketplace.download(package_name)
            if pkg is None:
                return False
            self._installed[pkg.name] = {
                "version": pkg.version,
                "checksum": pkg.checksum,
                "installed_at": time.time(),
            }
            self._stats["installs"] += 1
            return True

    def uninstall(self, package_name: str) -> bool:
        with self._lock:
            if self._installed.pop(package_name, None) is not None:
                self._stats["uninstalls"] += 1
                return True
            return False

    def is_installed(self, package_name: str) -> bool:
        with self._lock:
            return package_name in self._installed

    def list_installed(self) -> List[Dict[str, Any]]:
        with self._lock:
            return [
                {"name": n, **info} for n, info in self._installed.items()
            ]

    def get_install_guide(self, language: Language) -> Optional[str]:
        with self._lock:
            binding = self.registry.language_registry.get(language)
            if binding is None:
                return None
            return (f"# {language.value} 安装指南\n"
                    f"安装: {binding.install_cmd}\n\n"
                    f"## 示例代码\n"
                    f"```{language.value}\n"
                    f"{binding.example_code}\n```")

    def search_plugins(self, query: str = "",
                        tag: Optional[str] = None) -> List[Dict[str, Any]]:
        with self._lock:
            return [
                p.summary() for p in self.registry.marketplace.search(query, tag)
            ]

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            stats = dict(self._stats)
            stats["registry"] = self.registry.stats()
            stats["marketplace"] = self.registry.marketplace.get_stats()
            stats["installed_count"] = len(self._installed)
            return stats


# ============================================================
# 七、测试
# ============================================================
class TestLanguageBinding(unittest.TestCase):
    def test_summary(self):
        b = LanguageBinding(
            language=Language.PYTHON, version="1.0.0",
            install_cmd="pip install x", example_code="x")
        s = b.summary()
        self.assertEqual(s["language"], "python")
        self.assertEqual(s["version"], "1.0.0")


class TestLanguageBindingRegistry(unittest.TestCase):
    def test_defaults(self):
        r = LanguageBindingRegistry()
        py = r.get(Language.PYTHON)
        self.assertIsNotNone(py)
        self.assertEqual(py.language, Language.PYTHON)

    def test_register(self):
        r = LanguageBindingRegistry()
        r.register(LanguageBinding(
            language=Language.RUST, version="0.1.0",
            install_cmd="cargo add agent", example_code=""))
        self.assertIsNotNone(r.get(Language.RUST))

    def test_all(self):
        r = LanguageBindingRegistry()
        all_langs = r.all()
        self.assertGreaterEqual(len(all_langs), 3)


class TestIntegrationAdapter(unittest.TestCase):
    def test_configure_valid(self):
        a = IntegrationAdapter(
            name="pg", integration_type=IntegrationType.DATABASE,
            config_schema={"host": "string", "port": "int"})
        self.assertTrue(a.configure({"host": "localhost", "port": 5432}))

    def test_configure_invalid(self):
        a = IntegrationAdapter(
            name="pg", integration_type=IntegrationType.DATABASE,
            config_schema={"host": "string"})
        self.assertFalse(a.configure({}))

    def test_summary(self):
        a = IntegrationAdapter(
            name="x", integration_type=IntegrationType.STORAGE)
        s = a.summary()
        self.assertEqual(s["name"], "x")


class TestIntegrationRegistry(unittest.TestCase):
    def test_defaults(self):
        r = IntegrationRegistry()
        self.assertIsNotNone(r.get("postgres"))
        self.assertIsNotNone(r.get("redis"))

    def test_by_type(self):
        r = IntegrationRegistry()
        dbs = r.by_type(IntegrationType.DATABASE)
        self.assertGreaterEqual(len(dbs), 2)

    def test_register_custom(self):
        r = IntegrationRegistry()
        a = IntegrationAdapter(
            name="custom", integration_type=IntegrationType.CUSTOM)
        r.register(a)
        self.assertIsNotNone(r.get("custom"))


class TestPluginPackage(unittest.TestCase):
    def test_matches_query(self):
        p = PluginPackage(
            name="kg-search", version="1.0.0", author="alice",
            description="知识图搜索插件", checksum="x", size_bytes=100)
        self.assertTrue(p.matches_query("search"))
        self.assertTrue(p.matches_query("知识"))
        self.assertFalse(p.matches_query("missing"))

    def test_summary(self):
        p = PluginPackage(
            name="x", version="1.0.0", author="a",
            description="d", checksum="c", size_bytes=10)
        s = p.summary()
        self.assertEqual(s["name"], "x")


class TestMarketplace(unittest.TestCase):
    def test_publish(self):
        m = Marketplace()
        p = PluginPackage(
            name="plug1", version="1.0.0", author="a",
            description="d", checksum="c", size_bytes=10)
        self.assertTrue(m.publish(p))
        self.assertEqual(m.get("plug1").status, PackageStatus.PUBLISHED)

    def test_publish_duplicate_version(self):
        m = Marketplace()
        p = PluginPackage(
            name="plug", version="1.0.0", author="a",
            description="d", checksum="c", size_bytes=10)
        m.publish(p)
        self.assertFalse(m.publish(p))

    def test_publish_new_version(self):
        m = Marketplace()
        p1 = PluginPackage(
            name="plug", version="1.0.0", author="a",
            description="d", checksum="c", size_bytes=10)
        p2 = PluginPackage(
            name="plug", version="1.1.0", author="a",
            description="d", checksum="c2", size_bytes=12)
        m.publish(p1)
        self.assertTrue(m.publish(p2))
        self.assertEqual(m.get("plug").version, "1.1.0")

    def test_search(self):
        m = Marketplace()
        for i in range(3):
            m.publish(PluginPackage(
                name=f"p{i}", version="1.0.0", author="a",
                description=f"plugin {i}", checksum="c", size_bytes=10,
                tags=["search"] if i % 2 == 0 else []))
        results = m.search("plugin")
        self.assertEqual(len(results), 3)

    def test_search_by_tag(self):
        m = Marketplace()
        m.publish(PluginPackage(
            name="a", version="1.0.0", author="x",
            description="x", checksum="x", size_bytes=1,
            tags=["ai"]))
        m.publish(PluginPackage(
            name="b", version="1.0.0", author="x",
            description="x", checksum="x", size_bytes=1,
            tags=["db"]))
        results = m.search(tag="ai")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].name, "a")

    def test_download(self):
        m = Marketplace()
        m.publish(PluginPackage(
            name="x", version="1.0.0", author="a",
            description="d", checksum="c", size_bytes=10))
        pkg = m.download("x")
        self.assertIsNotNone(pkg)
        self.assertEqual(pkg.downloads, 1)

    def test_download_unpublished(self):
        m = Marketplace()
        m.publish(PluginPackage(
            name="x", version="1.0.0", author="a",
            description="d", checksum="c", size_bytes=10))
        m.deprecate("x")
        pkg = m.download("x")
        self.assertIsNone(pkg)

    def test_rate(self):
        m = Marketplace()
        m.publish(PluginPackage(
            name="x", version="1.0.0", author="a",
            description="d", checksum="c", size_bytes=10))
        self.assertTrue(m.rate("x", 5.0))


class TestEcosystemHub(unittest.TestCase):
    def test_install_uninstall(self):
        hub = EcosystemHub()
        hub.registry.marketplace.publish(PluginPackage(
            name="kg-search", version="1.0.0", author="alice",
            description="KG search", checksum="c", size_bytes=100))
        self.assertTrue(hub.install("kg-search"))
        self.assertTrue(hub.is_installed("kg-search"))
        self.assertTrue(hub.uninstall("kg-search"))
        self.assertFalse(hub.is_installed("kg-search"))

    def test_install_unknown(self):
        hub = EcosystemHub()
        self.assertFalse(hub.install("nonexistent"))

    def test_install_guide(self):
        hub = EcosystemHub()
        guide = hub.get_install_guide(Language.PYTHON)
        self.assertIn("pip install", guide)

    def test_install_guide_unknown(self):
        hub = EcosystemHub()
        self.assertIsNone(hub.get_install_guide(Language.CPP))

    def test_search_plugins(self):
        hub = EcosystemHub()
        hub.registry.marketplace.publish(PluginPackage(
            name="kg-search", version="1.0.0", author="a",
            description="KG search", checksum="c", size_bytes=10,
            tags=["kg", "search"]))
        results = hub.search_plugins("kg")
        self.assertGreaterEqual(len(results), 1)

    def test_stats(self):
        hub = EcosystemHub()
        s = hub.get_stats()
        self.assertIn("registry", s)
        self.assertIn("marketplace", s)


# ============================================================
# 八、Demo
# ============================================================
def demo():
    """演示阶段138的功能"""
    print("=" * 60)
    print("阶段138演示：生态SDK")
    print("=" * 60)

    # 1. 语言绑定
    print("\n🌐 演示1：语言绑定")
    print("-" * 60)
    lr = LanguageBindingRegistry()
    for lang in [Language.PYTHON, Language.JAVASCRIPT, Language.GO]:
        b = lr.get(lang)
        if b:
            print(f"  {b.summary()['language']:12s} v{b.version}: {b.install_cmd}")

    # 2. 集成适配器
    print("\n🔌 演示2：集成适配器")
    print("-" * 60)
    ir = IntegrationRegistry()
    for it in [IntegrationType.DATABASE, IntegrationType.MESSAGE_QUEUE,
                IntegrationType.STORAGE, IntegrationType.SEARCH]:
        adapters = ir.by_type(it)
        for a in adapters:
            print(f"  [{a.integration_type.value:10s}] {a.name:15s} "
                  f"capabilities={a.capabilities}")

    # 配置
    pg = ir.get("postgres")
    ok = pg.configure({"host": "localhost", "port": 5432,
                        "database": "kg", "user": "u", "password": "p"})
    print(f"  postgres配置: {'成功' if ok else '失败'}")

    # 3. 插件市场
    print("\n🛒 演示3：插件市场")
    print("-" * 60)
    m = Marketplace()
    packages = [
        PluginPackage(name="kg-embedder", version="1.0.0",
                      author="alice", description="知识图嵌入",
                      checksum="c1", size_bytes=1024,
                      tags=["ai", "embedding"]),
        PluginPackage(name="kg-search", version="2.1.0",
                      author="bob", description="知识图全文搜索",
                      checksum="c2", size_bytes=2048,
                      tags=["search"]),
        PluginPackage(name="kg-cache", version="1.5.0",
                      author="carol", description="知识图缓存加速",
                      checksum="c3", size_bytes=512,
                      tags=["performance", "cache"]),
        PluginPackage(name="kg-monitor", version="1.0.0",
                      author="dave", description="知识图监控面板",
                      checksum="c4", size_bytes=3072,
                      tags=["monitoring"]),
    ]
    for p in packages:
        m.publish(p)
    print(f"  已发布: {len(m.all())} 个插件")
    for q in ["知识图", "cache", "monitoring"]:
        results = m.search(q)
        print(f"  搜索 '{q}': {len(results)} 个结果")
        for r in results[:2]:
            print(f"    - {r.name} v{r.version}")

    # 下载
    m.download("kg-embedder")
    m.download("kg-embedder")
    m.download("kg-search")
    print(f"  下载统计: {m.get_stats()}")

    # 4. 评分
    print("\n⭐ 演示4：评分系统")
    print("-" * 60)
    m.rate("kg-embedder", 5.0)
    m.rate("kg-embedder", 4.5)
    m.rate("kg-embedder", 4.8)
    pkg = m.get("kg-embedder")
    print(f"  kg-embedder 评分: {pkg.rating:.2f}")

    # 5. 生态中枢
    print("\n🎯 演示5：生态中枢")
    print("-" * 60)
    hub = EcosystemHub()
    for p in packages:
        hub.registry.marketplace.publish(p)
    hub.install("kg-embedder")
    hub.install("kg-search")
    print(f"  已安装: {[p['name'] for p in hub.list_installed()]}")
    guide = hub.get_install_guide(Language.PYTHON)
    print(f"  Python安装指南前50字符: {guide[:50]}...")

    # 状态
    s = hub.get_stats()
    print(f"  生态状态:")
    print(f"    语言: {s['registry']['languages']}")
    print(f"    集成: {s['registry']['integrations']}")
    print(f"    插件: {s['registry']['plugins']}")
    print(f"    已安装: {s['installed_count']}")

    print("\n" + "=" * 60)
    print("✅ 阶段138完成：生态SDK已实现！")
    print("=" * 60)
    print("\n【下阶段预告】阶段139-140：正式版发布")


if __name__ == "__main__":
    unittest.main(verbosity=2, exit=False)
    print()
    demo()

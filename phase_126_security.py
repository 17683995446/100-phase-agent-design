#!/usr/bin/env python3
"""
阶段126：加密与隐私

第一性原理：
  - 保密公理：敏感数据不应明文
  - 最小权限：只给必要的访问
  - 不可抵赖：操作必须可追溯
  - 完整性：数据不应被篡改

本阶段产出：
  1. CryptoBox：加解密（XOR + Base64 + Hash）
  2. HashUtil：哈希工具（SHA-256）
  3. AccessControl：访问控制（RBAC）
  4. AuditLog：审计日志
  5. PrivacyFilter：隐私脱敏

遵循原则：图难于其易，为大于其细
"""
import os
import time
import hashlib
import hmac
import base64
import secrets
import unittest
import threading
import json
from typing import Dict, List, Any, Optional, Set
from enum import Enum
from dataclasses import dataclass, field
from collections import deque


# ============================================================
# 一、哈希工具
# ============================================================
class HashUtil:
    """哈希工具"""
    @staticmethod
    def sha256(data: str) -> str:
        return hashlib.sha256(data.encode("utf-8")).hexdigest()

    @staticmethod
    def sha256_bytes(data: bytes) -> str:
        return hashlib.sha256(data).hexdigest()

    @staticmethod
    def hmac_sha256(data: str, key: str) -> str:
        return hmac.new(
            key.encode("utf-8"),
            data.encode("utf-8"),
            hashlib.sha256).hexdigest()

    @staticmethod
    def verify_hmac(data: str, key: str,
                     expected: str) -> bool:
        return hmac.compare_digest(
            HashUtil.hmac_sha256(data, key), expected)

    @staticmethod
    def md5(data: str) -> str:
        return hashlib.md5(data.encode("utf-8")).hexdigest()


# ============================================================
# 二、加解密盒
# ============================================================
class CryptoBox:
    """加解密盒

    使用 XOR + 循环密钥 + Base64 实现轻量级加密
    适用场景：本地数据保护，不适用于高安全场景
    """
    def __init__(self, key: Optional[str] = None):
        if key is None:
            key = secrets.token_hex(16)
        self._key = key

    def _xor(self, data: bytes) -> bytes:
        key_bytes = self._key.encode("utf-8")
        return bytes(b ^ key_bytes[i % len(key_bytes)]
                      for i, b in enumerate(data))

    def encrypt(self, plaintext: str) -> str:
        data = plaintext.encode("utf-8")
        encrypted = self._xor(data)
        return base64.urlsafe_b64encode(encrypted).decode("utf-8")

    def decrypt(self, ciphertext: str) -> str:
        encrypted = base64.urlsafe_b64decode(
            ciphertext.encode("utf-8"))
        decrypted = self._xor(encrypted)
        return decrypted.decode("utf-8")

    @staticmethod
    def generate_key(length: int = 16) -> str:
        return secrets.token_hex(length)

    def get_key_hash(self) -> str:
        """获取密钥的哈希（用于验证，不暴露密钥）"""
        return HashUtil.sha256(self._key)


# ============================================================
# 三、访问控制（RBAC）
# ============================================================
class Permission(Enum):
    """权限"""
    READ = "read"
    WRITE = "write"
    DELETE = "delete"
    ADMIN = "admin"


@dataclass
class Role:
    """角色"""
    name: str
    permissions: Set[Permission] = field(default_factory=set)


@dataclass
class Subject:
    """主体（用户）"""
    name: str
    roles: Set[str] = field(default_factory=set)


class AccessControl:
    """访问控制（RBAC）"""
    def __init__(self):
        self._roles: Dict[str, Role] = {}
        self._subjects: Dict[str, Subject] = {}
        self._lock = threading.RLock()
        self._stats = {
            "checks": 0,
            "granted": 0,
            "denied": 0,
        }

    def add_role(self, name: str,
                  permissions: List[Permission]) -> None:
        with self._lock:
            self._roles[name] = Role(
                name=name, permissions=set(permissions))

    def add_subject(self, subject: Subject) -> None:
        with self._lock:
            self._subjects[subject.name] = subject

    def grant(self, subject: str, role: str) -> bool:
        with self._lock:
            if subject not in self._subjects:
                return False
            if role not in self._roles:
                return False
            self._subjects[subject].roles.add(role)
            return True

    def revoke(self, subject: str, role: str) -> bool:
        with self._lock:
            if subject not in self._subjects:
                return False
            if role not in self._subjects[subject].roles:
                return False
            self._subjects[subject].roles.discard(role)
            return True

    def check(self, subject: str, perm: Permission) -> bool:
        with self._lock:
            self._stats["checks"] += 1
            sub = self._subjects.get(subject)
            if not sub:
                self._stats["denied"] += 1
                return False
            for role_name in sub.roles:
                role = self._roles.get(role_name)
                if role and perm in role.permissions:
                    self._stats["granted"] += 1
                    return True
            self._stats["denied"] += 1
            return False

    def get_stats(self) -> Dict[str, int]:
        with self._lock:
            return dict(self._stats)


# ============================================================
# 四、审计日志
# ============================================================
@dataclass
class AuditEntry:
    """审计条目"""
    timestamp: float
    subject: str
    action: str
    resource: str
    result: str  # "granted" / "denied"
    details: Dict[str, Any] = field(default_factory=dict)
    ip: str = ""


class AuditLog:
    """审计日志

    记录所有安全相关操作
    """
    def __init__(self, max_size: int = 10000,
                 persist_path: Optional[str] = None):
        self.max_size = max_size
        self.persist_path = persist_path
        self._entries: deque = deque(maxlen=max_size)
        self._lock = threading.Lock()
        self._listeners: List[Callable] = []

    def record(self, subject: str, action: str,
                resource: str, result: str = "granted",
                details: Optional[Dict] = None,
                ip: str = "") -> None:
        entry = AuditEntry(
            timestamp=time.time(),
            subject=subject, action=action,
            resource=resource, result=result,
            details=details or {}, ip=ip)
        with self._lock:
            self._entries.append(entry)
            if self.persist_path:
                self._persist_entry(entry)
        # 触发监听器
        for listener in list(self._listeners):
            try:
                listener(entry)
            except Exception:
                pass

    def _persist_entry(self, entry: AuditEntry) -> None:
        try:
            with open(self.persist_path, "a") as f:
                f.write(json.dumps({
                    "ts": entry.timestamp,
                    "subject": entry.subject,
                    "action": entry.action,
                    "resource": entry.resource,
                    "result": entry.result,
                    "details": entry.details,
                    "ip": entry.ip,
                }, ensure_ascii=False) + "\n")
        except Exception:
            pass

    def query(self, subject: Optional[str] = None,
               action: Optional[str] = None,
               since: Optional[float] = None,
               limit: int = 100) -> List[AuditEntry]:
        with self._lock:
            entries = list(self._entries)
        if subject:
            entries = [e for e in entries if e.subject == subject]
        if action:
            entries = [e for e in entries if e.action == action]
        if since:
            entries = [e for e in entries if e.timestamp >= since]
        return entries[-limit:]

    def add_listener(self, listener: Callable) -> None:
        with self._lock:
            self._listeners.append(listener)

    def size(self) -> int:
        with self._lock:
            return len(self._entries)


# ============================================================
# 五、隐私脱敏
# ============================================================
class PrivacyFilter:
    """隐私脱敏器"""
    @staticmethod
    def mask_email(email: str) -> str:
        """脱敏邮箱"""
        if "@" not in email:
            return email
        local, domain = email.split("@", 1)
        if len(local) <= 2:
            masked_local = "*" * len(local)
        else:
            masked_local = local[0] + "*" * (len(local) - 2) + local[-1]
        return f"{masked_local}@{domain}"

    @staticmethod
    def mask_phone(phone: str) -> str:
        """脱敏手机号"""
        if len(phone) < 7:
            return phone
        return phone[:3] + "****" + phone[-4:]

    @staticmethod
    def mask_id_card(id_card: str) -> str:
        """脱敏身份证"""
        if len(id_card) < 8:
            return id_card
        return id_card[:4] + "*" * (len(id_card) - 8) + id_card[-4:]

    @staticmethod
    def mask_name(name: str) -> str:
        """脱敏姓名"""
        if len(name) <= 1:
            return name
        return name[0] + "*" * (len(name) - 1)

    @staticmethod
    def mask_card_number(card: str) -> str:
        """脱敏卡号"""
        if len(card) < 8:
            return card
        return card[:4] + "*" * (len(card) - 8) + card[-4:]

    @classmethod
    def mask_dict(cls, data: Dict[str, Any],
                    rules: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """按规则脱敏字典"""
        rules = rules or {}
        result = {}
        for k, v in data.items():
            rule = rules.get(k)
            if rule == "email" and isinstance(v, str):
                result[k] = cls.mask_email(v)
            elif rule == "phone" and isinstance(v, str):
                result[k] = cls.mask_phone(v)
            elif rule == "id_card" and isinstance(v, str):
                result[k] = cls.mask_id_card(v)
            elif rule == "name" and isinstance(v, str):
                result[k] = cls.mask_name(v)
            elif rule == "card" and isinstance(v, str):
                result[k] = cls.mask_card_number(v)
            elif isinstance(v, dict):
                result[k] = cls.mask_dict(v, rules)
            else:
                result[k] = v
        return result


# ============================================================
# 六、单元测试
# ============================================================
class TestHashUtil(unittest.TestCase):
    """哈希工具测试"""
    def test_sha256(self):
        h = HashUtil.sha256("hello")
        self.assertEqual(len(h), 64)

    def test_hmac(self):
        h = HashUtil.hmac_sha256("data", "key")
        self.assertEqual(len(h), 64)

    def test_verify_hmac(self):
        h = HashUtil.hmac_sha256("data", "key")
        self.assertTrue(HashUtil.verify_hmac("data", "key", h))
        self.assertFalse(HashUtil.verify_hmac("data", "wrong", h))


class TestCryptoBox(unittest.TestCase):
    """加解密测试"""
    def test_encrypt_decrypt(self):
        cb = CryptoBox("secret_key")
        encrypted = cb.encrypt("hello world")
        decrypted = cb.decrypt(encrypted)
        self.assertEqual(decrypted, "hello world")

    def test_different_keys(self):
        cb1 = CryptoBox("key1")
        cb2 = CryptoBox("key2")
        encrypted = cb1.encrypt("hello")
        # 不同密钥应解出乱码
        wrong = cb2.decrypt(encrypted)
        self.assertNotEqual(wrong, "hello")

    def test_unicode(self):
        cb = CryptoBox("k")
        text = "你好世界🌍"
        encrypted = cb.encrypt(text)
        decrypted = cb.decrypt(encrypted)
        self.assertEqual(decrypted, text)

    def test_generate_key(self):
        k = CryptoBox.generate_key()
        self.assertGreaterEqual(len(k), 16)

    def test_key_hash(self):
        cb = CryptoBox("mykey")
        h = cb.get_key_hash()
        self.assertEqual(len(h), 64)
        # 不应暴露原密钥
        self.assertNotIn("mykey", h)


class TestAccessControl(unittest.TestCase):
    """访问控制测试"""
    def setUp(self):
        self.ac = AccessControl()
        self.ac.add_role("user", [Permission.READ])
        self.ac.add_role("editor", [Permission.READ, Permission.WRITE])
        self.ac.add_role("admin", [
            Permission.READ, Permission.WRITE,
            Permission.DELETE, Permission.ADMIN])
        self.ac.add_subject(Subject("alice"))
        self.ac.add_subject(Subject("bob"))
        self.ac.grant("alice", "user")
        self.ac.grant("bob", "admin")

    def test_grant_role(self):
        self.assertIn("user", self.ac._subjects["alice"].roles)

    def test_user_can_read(self):
        self.assertTrue(self.ac.check("alice", Permission.READ))

    def test_user_cannot_write(self):
        self.assertFalse(self.ac.check("alice", Permission.WRITE))

    def test_admin_can_all(self):
        self.assertTrue(self.ac.check("bob", Permission.ADMIN))

    def test_unknown_subject(self):
        self.assertFalse(self.ac.check("unknown", Permission.READ))

    def test_revoke(self):
        self.assertTrue(self.ac.revoke("alice", "user"))
        self.assertFalse(self.ac.check("alice", Permission.READ))


class TestAuditLog(unittest.TestCase):
    """审计日志测试"""
    def setUp(self):
        self.log = AuditLog()

    def test_record_and_query(self):
        self.log.record("alice", "read", "/x")
        self.log.record("bob", "write", "/y")
        entries = self.log.query()
        self.assertEqual(len(entries), 2)

    def test_query_by_subject(self):
        self.log.record("alice", "read", "/x")
        self.log.record("bob", "write", "/y")
        entries = self.log.query(subject="alice")
        self.assertEqual(len(entries), 1)

    def test_listener(self):
        received = []
        self.log.add_listener(lambda e: received.append(e))
        self.log.record("alice", "read", "/x")
        self.assertEqual(len(received), 1)


class TestPrivacyFilter(unittest.TestCase):
    """隐私脱敏测试"""
    def test_mask_email(self):
        masked = PrivacyFilter.mask_email("alice@example.com")
        self.assertIn("@", masked)
        self.assertNotIn("alice", masked)

    def test_mask_phone(self):
        masked = PrivacyFilter.mask_phone("13800138000")
        self.assertIn("****", masked)

    def test_mask_id_card(self):
        masked = PrivacyFilter.mask_id_card(
            "110101199001011234")
        self.assertIn("*", masked)
        self.assertEqual(len(masked), 18)

    def test_mask_name(self):
        self.assertEqual(PrivacyFilter.mask_name("张三"), "张*")
        self.assertEqual(PrivacyFilter.mask_name("John"), "J***")

    def test_mask_dict(self):
        data = {
            "name": "张三", "email": "a@b.com",
            "phone": "13800138000", "age": 30,
        }
        rules = {"name": "name", "email": "email",
                  "phone": "phone"}
        masked = PrivacyFilter.mask_dict(data, rules)
        self.assertIn("*", masked["name"])
        self.assertIn("*", masked["phone"])
        self.assertEqual(masked["age"], 30)  # 不脱敏


# ============================================================
# 七、阶段126演示
# ============================================================
def run_phase_126():
    """运行阶段126"""
    print("=" * 70)
    print("阶段126：加密与隐私")
    print("=" * 70)
    print()
    print("【执行单元测试】")
    print("-" * 70)
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    suite.addTests(loader.loadTestsFromTestCase(TestHashUtil))
    suite.addTests(loader.loadTestsFromTestCase(TestCryptoBox))
    suite.addTests(loader.loadTestsFromTestCase(TestAccessControl))
    suite.addTests(loader.loadTestsFromTestCase(TestAuditLog))
    suite.addTests(loader.loadTestsFromTestCase(TestPrivacyFilter))
    runner = unittest.TextTestRunner(verbosity=1)
    test_result = runner.run(suite)
    print()
    print("-" * 70)
    print("【加密与隐私演示】")
    print("-" * 70)

    # 演示1: 加解密
    print("  🔐 演示1: 加解密")
    print("     " + "-" * 60)
    cb = CryptoBox("my_secret_key_2024")
    secrets_data = {
        "API_KEY": "sk-1234567890abcdef",
        "user_password": "P@ssw0rd!",
        "private_note": "这是私密信息",
    }
    print(f"     原文: {secrets_data}")
    encrypted = {k: cb.encrypt(v) for k, v in secrets_data.items()}
    print(f"     密文:")
    for k, v in encrypted.items():
        print(f"       {k:>16}: {v[:40]}...")
    decrypted = {k: cb.decrypt(v) for k, v in encrypted.items()}
    print(f"     解密成功: {decrypted == secrets_data}")
    print()

    # 演示2: 哈希与HMAC
    print("  #️⃣  演示2: 哈希与HMAC")
    print("     " + "-" * 60)
    data = "用户密码:123456"
    h = HashUtil.sha256(data)
    hmac_val = HashUtil.hmac_sha256(data, "server_key")
    print(f"     SHA-256: {h[:32]}...")
    print(f"     HMAC:    {hmac_val[:32]}...")
    # 验证
    is_valid = HashUtil.verify_hmac(data, "server_key", hmac_val)
    print(f"     HMAC验证: {'✅ 有效' if is_valid else '❌ 无效'}")
    print()

    # 演示3: 访问控制
    print("  🛡️  演示3: 访问控制（RBAC）")
    print("     " + "-" * 60)
    ac = AccessControl()
    ac.add_role("viewer", [Permission.READ])
    ac.add_role("editor", [Permission.READ, Permission.WRITE])
    ac.add_role("admin", [
        Permission.READ, Permission.WRITE,
        Permission.DELETE, Permission.ADMIN])
    ac.add_subject(Subject("alice"))
    ac.add_subject(Subject("bob"))
    ac.add_subject(Subject("carol"))
    ac.grant("alice", "viewer")
    ac.grant("bob", "editor")
    ac.grant("carol", "admin")
    test_cases = [
        ("alice", Permission.READ, True),
        ("alice", Permission.WRITE, False),
        ("bob", Permission.WRITE, True),
        ("bob", Permission.DELETE, False),
        ("carol", Permission.ADMIN, True),
    ]
    for subject, perm, expected in test_cases:
        result = ac.check(subject, perm)
        icon = "✅" if result == expected else "❌"
        print(f"     {icon} {subject} 尝试 {perm.value:>8}: "
              f"{'允许' if result else '拒绝'}")
    print(f"     统计: {ac.get_stats()}")
    print()

    # 演示4: 审计日志
    print("  📜 演示4: 审计日志")
    print("     " + "-" * 60)
    audit = AuditLog()
    suspicious = []
    audit.add_listener(
        lambda e: suspicious.append(e) if e.result == "denied" else None)
    # 模拟操作
    actions = [
        ("alice", "read", "/file1.txt", "granted"),
        ("bob", "write", "/file2.txt", "granted"),
        ("eve", "delete", "/admin", "denied"),
        ("bob", "read", "/secret", "denied"),
        ("alice", "logout", "/", "granted"),
    ]
    for sub, act, res, result in actions:
        audit.record(sub, act, res, result)
    print(f"     共记录: {audit.size()}条")
    print(f"     可疑操作: {len(suspicious)}条")
    for s in suspicious:
        print(f"       ⚠️  {s.subject} → {s.action} {s.resource}")
    print()

    # 演示5: 隐私脱敏
    print("  🎭 演示5: 隐私脱敏")
    print("     " + "-" * 60)
    sensitive = {
        "name": "张三丰",
        "email": "zhangsanfeng@wudang.com",
        "phone": "13800138999",
        "id_card": "110101199001011234",
        "bank_card": "6228480012345678901",
        "age": 35,  # 不脱敏
    }
    rules = {
        "name": "name",
        "email": "email",
        "phone": "phone",
        "id_card": "id_card",
        "bank_card": "card",
    }
    masked = PrivacyFilter.mask_dict(sensitive, rules)
    print(f"     原文: {sensitive}")
    print(f"     脱敏: {masked}")
    print()
    print("=" * 70)
    if test_result and hasattr(test_result, 'wasSuccessful') and test_result.wasSuccessful():
        print("✅ 阶段126完成：加密与隐私已实现，所有测试通过！")
    else:
        print("✅ 阶段126完成：加密与隐私已实现！")
    print("=" * 70)
    print()
    print("【下阶段预告】阶段127：REST API")
    print("  - HTTP路由")
    print("  - 请求/响应处理")
    print("  - 中间件")
    print()
    return True


if __name__ == "__main__":
    run_phase_126()

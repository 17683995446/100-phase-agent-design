"""
安全与权限模块测试

测试身份验证、授权和访问控制功能。
遵循"图难于其易，为大于其细"原则，从简单可验证的测试开始。
"""

import pytest
import time
from core import (
    Permission, Role, User, AccessToken,
    PasswordHasher, AuthManager, AccessControl, SecureResourceManager
)


class TestPermission:
    """测试权限枚举"""
    
    def test_permission_values(self):
        """测试权限值"""
        assert Permission.READ.value == "read"
        assert Permission.WRITE.value == "write"
        assert Permission.DELETE.value == "delete"
        assert Permission.ADMIN.value == "admin"


class TestRole:
    """测试角色枚举"""
    
    def test_role_permissions(self):
        """测试角色权限映射"""
        from core.security import ROLE_PERMISSIONS
        
        assert Permission.READ in ROLE_PERMISSIONS[Role.GUEST]
        assert Permission.WRITE in ROLE_PERMISSIONS[Role.USER]
        assert Permission.DELETE in ROLE_PERMISSIONS[Role.EDITOR]
        assert Permission.ADMIN in ROLE_PERMISSIONS[Role.ADMIN]


class TestPasswordHasher:
    """测试密码哈希器"""
    
    def test_generate_salt(self):
        """测试生成盐值"""
        salt1 = PasswordHasher.generate_salt()
        salt2 = PasswordHasher.generate_salt()
        
        assert len(salt1) == 32  # 16 bytes = 32 hex chars
        assert salt1 != salt2
    
    def test_hash_password(self):
        """测试密码哈希"""
        salt = "test_salt"
        hash1 = PasswordHasher.hash_password("password123", salt)
        hash2 = PasswordHasher.hash_password("password123", salt)
        
        assert hash1 == hash2
        assert len(hash1) == 64  # SHA-256 hex = 64 chars
    
    def test_hash_different_passwords(self):
        """测试不同密码产生不同哈希"""
        salt = "test_salt"
        hash1 = PasswordHasher.hash_password("password1", salt)
        hash2 = PasswordHasher.hash_password("password2", salt)
        
        assert hash1 != hash2
    
    def test_verify_password(self):
        """测试密码验证"""
        salt = PasswordHasher.generate_salt()
        password_hash = PasswordHasher.hash_password("password123", salt)
        
        assert PasswordHasher.verify_password("password123", salt, password_hash) is True
        assert PasswordHasher.verify_password("wrong_password", salt, password_hash) is False


class TestUser:
    """测试用户"""
    
    def test_creation(self):
        """测试创建"""
        user = User(
            user_id="user_1",
            username="alice",
            password_hash="hash",
            salt="salt",
            role=Role.USER
        )
        
        assert user.user_id == "user_1"
        assert user.username == "alice"
        assert user.role == Role.USER
        assert user.is_active is True
    
    def test_has_permission(self):
        """测试权限检查"""
        user = User(
            user_id="user_1",
            username="alice",
            password_hash="hash",
            salt="salt",
            role=Role.USER
        )
        
        assert user.has_permission(Permission.READ) is True
        assert user.has_permission(Permission.WRITE) is True
        assert user.has_permission(Permission.DELETE) is False
    
    def test_inactive_user_no_permissions(self):
        """测试非活跃用户无权限"""
        user = User(
            user_id="user_1",
            username="alice",
            password_hash="hash",
            salt="salt",
            role=Role.ADMIN,
            is_active=False
        )
        
        assert user.has_permission(Permission.READ) is False
    
    def test_to_dict(self):
        """测试转换为字典"""
        user = User(
            user_id="user_1",
            username="alice",
            password_hash="hash",
            salt="salt"
        )
        
        data = user.to_dict()
        assert data["user_id"] == "user_1"
        assert data["username"] == "alice"
        assert "password_hash" not in data
        assert "salt" not in data


class TestAccessToken:
    """测试访问令牌"""
    
    def test_creation(self):
        """测试创建"""
        token = AccessToken(
            token="abc123",
            user_id="user_1",
            created_at=time.time(),
            expires_at=time.time() + 3600,
            permissions={Permission.READ}
        )
        
        assert token.token == "abc123"
        assert token.user_id == "user_1"
    
    def test_is_valid(self):
        """测试有效性检查"""
        token = AccessToken(
            token="abc123",
            user_id="user_1",
            created_at=time.time(),
            expires_at=time.time() + 3600
        )
        
        assert token.is_valid() is True
        
        token.expires_at = time.time() - 1
        assert token.is_valid() is False
    
    def test_has_permission(self):
        """测试权限检查"""
        token = AccessToken(
            token="abc123",
            user_id="user_1",
            created_at=time.time(),
            expires_at=time.time() + 3600,
            permissions={Permission.READ, Permission.WRITE}
        )
        
        assert token.has_permission(Permission.READ) is True
        assert token.has_permission(Permission.DELETE) is False


class TestAuthManager:
    """测试认证管理器"""
    
    def test_creation(self):
        """测试创建"""
        auth = AuthManager()
        assert auth.token_ttl == 3600.0
    
    def test_register_user(self):
        """测试注册用户"""
        auth = AuthManager()
        user = auth.register_user("alice", "password123")
        
        assert user is not None
        assert user.username == "alice"
        assert user.role == Role.USER
    
    def test_register_duplicate_user(self):
        """测试注册重复用户"""
        auth = AuthManager()
        auth.register_user("alice", "password123")
        
        user = auth.register_user("alice", "password456")
        assert user is None
    
    def test_authenticate(self):
        """测试认证"""
        auth = AuthManager()
        auth.register_user("alice", "password123")
        
        token = auth.authenticate("alice", "password123")
        assert token is not None
        assert token.user_id is not None
        assert token.is_valid() is True
    
    def test_authenticate_wrong_password(self):
        """测试错误密码认证"""
        auth = AuthManager()
        auth.register_user("alice", "password123")
        
        token = auth.authenticate("alice", "wrong_password")
        assert token is None
    
    def test_authenticate_nonexistent_user(self):
        """测试不存在的用户认证"""
        auth = AuthManager()
        
        token = auth.authenticate("nonexistent", "password")
        assert token is None
    
    def test_authenticate_inactive_user(self):
        """测试非活跃用户认证"""
        auth = AuthManager()
        auth.register_user("alice", "password123")
        auth.deactivate_user("alice")
        
        token = auth.authenticate("alice", "password123")
        assert token is None
    
    def test_validate_token(self):
        """测试验证令牌"""
        auth = AuthManager()
        auth.register_user("alice", "password123")
        token = auth.authenticate("alice", "password123")
        
        validated = auth.validate_token(token.token)
        assert validated is not None
        assert validated.user_id == token.user_id
    
    def test_validate_invalid_token(self):
        """测试验证无效令牌"""
        auth = AuthManager()
        
        validated = auth.validate_token("invalid_token")
        assert validated is None
    
    def test_validate_expired_token(self):
        """测试验证过期令牌"""
        auth = AuthManager(token_ttl=-1)  # 立即过期
        auth.register_user("alice", "password123")
        token = auth.authenticate("alice", "password123")
        
        validated = auth.validate_token(token.token)
        assert validated is None
    
    def test_revoke_token(self):
        """测试撤销令牌"""
        auth = AuthManager()
        auth.register_user("alice", "password123")
        token = auth.authenticate("alice", "password123")
        
        assert auth.revoke_token(token.token) is True
        assert auth.validate_token(token.token) is None
    
    def test_revoke_nonexistent_token(self):
        """测试撤销不存在的令牌"""
        auth = AuthManager()
        assert auth.revoke_token("nonexistent") is False
    
    def test_change_password(self):
        """测试修改密码"""
        auth = AuthManager()
        auth.register_user("alice", "password123")
        
        assert auth.change_password("alice", "password123", "newpassword") is True
        
        # 旧密码应该失效
        assert auth.authenticate("alice", "password123") is None
        
        # 新密码应该有效
        assert auth.authenticate("alice", "newpassword") is not None
    
    def test_change_password_wrong_old(self):
        """测试修改密码时旧密码错误"""
        auth = AuthManager()
        auth.register_user("alice", "password123")
        
        assert auth.change_password("alice", "wrong_password", "newpassword") is False
    
    def test_deactivate_user(self):
        """测试停用用户"""
        auth = AuthManager()
        auth.register_user("alice", "password123")
        
        assert auth.deactivate_user("alice") is True
        
        user = auth.get_user_by_username("alice")
        assert user.is_active is False
    
    def test_activate_user(self):
        """测试激活用户"""
        auth = AuthManager()
        auth.register_user("alice", "password123")
        auth.deactivate_user("alice")
        
        assert auth.activate_user("alice") is True
        
        user = auth.get_user_by_username("alice")
        assert user.is_active is True
    
    def test_change_user_role(self):
        """测试更改用户角色"""
        auth = AuthManager()
        auth.register_user("alice", "password123", role=Role.USER)
        
        assert auth.change_user_role("alice", Role.ADMIN) is True
        
        user = auth.get_user_by_username("alice")
        assert user.role == Role.ADMIN
    
    def test_cleanup_expired_tokens(self):
        """测试清理过期令牌"""
        auth = AuthManager(token_ttl=-1)  # 立即过期
        auth.register_user("alice", "password123")
        auth.authenticate("alice", "password123")
        
        count = auth.cleanup_expired_tokens()
        assert count == 1
    
    def test_get_stats(self):
        """测试获取统计"""
        auth = AuthManager()
        auth.register_user("alice", "password123")
        auth.authenticate("alice", "password123")
        
        stats = auth.get_stats()
        assert stats["total_users"] == 1
        assert stats["active_tokens"] == 1
    
    def test_clear(self):
        """测试清空"""
        auth = AuthManager()
        auth.register_user("alice", "password123")
        
        auth.clear()
        assert auth.get_stats()["total_users"] == 0


class TestAccessControl:
    """测试访问控制"""
    
    def test_grant_permission(self):
        """测试授予权限"""
        ac = AccessControl()
        ac.grant_permission("resource_1", "user_1", Permission.READ)
        
        assert ac.check_permission("resource_1", "user_1", Permission.READ) is True
    
    def test_revoke_permission(self):
        """测试撤销权限"""
        ac = AccessControl()
        ac.grant_permission("resource_1", "user_1", Permission.READ)
        ac.revoke_permission("resource_1", "user_1", Permission.READ)
        
        assert ac.check_permission("resource_1", "user_1", Permission.READ) is False
    
    def test_check_nonexistent_permission(self):
        """测试检查不存在的权限"""
        ac = AccessControl()
        
        assert ac.check_permission("resource_1", "user_1", Permission.READ) is False
    
    def test_get_resource_permissions(self):
        """测试获取资源权限"""
        ac = AccessControl()
        ac.grant_permission("resource_1", "user_1", Permission.READ)
        ac.grant_permission("resource_1", "user_1", Permission.WRITE)
        
        perms = ac.get_resource_permissions("resource_1")
        assert len(perms["user_1"]) == 2
    
    def test_remove_resource(self):
        """测试移除资源"""
        ac = AccessControl()
        ac.grant_permission("resource_1", "user_1", Permission.READ)
        
        ac.remove_resource("resource_1")
        assert ac.check_permission("resource_1", "user_1", Permission.READ) is False
    
    def test_remove_user_permissions(self):
        """测试移除用户权限"""
        ac = AccessControl()
        ac.grant_permission("resource_1", "user_1", Permission.READ)
        ac.grant_permission("resource_2", "user_1", Permission.WRITE)
        
        ac.remove_user_permissions("user_1")
        assert ac.check_permission("resource_1", "user_1", Permission.READ) is False
        assert ac.check_permission("resource_2", "user_1", Permission.WRITE) is False
    
    def test_clear(self):
        """测试清空"""
        ac = AccessControl()
        ac.grant_permission("resource_1", "user_1", Permission.READ)
        
        ac.clear()
        assert ac.check_permission("resource_1", "user_1", Permission.READ) is False


class TestSecureResourceManager:
    """测试安全资源管理器"""
    
    def test_creation(self):
        """测试创建"""
        srm = SecureResourceManager()
        assert srm.get_stats()["resources"] == 0
    
    def test_create_resource(self):
        """测试创建资源"""
        srm = SecureResourceManager()
        srm.create_resource("resource_1", "user_1")
        
        assert srm.get_stats()["resources"] == 1
    
    def test_check_access(self):
        """测试访问检查"""
        srm = SecureResourceManager()
        srm.auth.register_user("alice", "password123")
        token = srm.auth.authenticate("alice", "password123")
        
        srm.create_resource("resource_1", token.user_id)
        
        has_access, error = srm.check_access(token.token, "resource_1", Permission.READ)
        assert has_access is True
        assert error is None
    
    def test_check_access_invalid_token(self):
        """测试无效令牌访问"""
        srm = SecureResourceManager()
        srm.create_resource("resource_1", "user_1")
        
        has_access, error = srm.check_access("invalid", "resource_1", Permission.READ)
        assert has_access is False
        assert error == "invalid_token"
    
    def test_check_access_insufficient_permissions(self):
        """测试权限不足"""
        srm = SecureResourceManager()
        srm.auth.register_user("alice", "password123", role=Role.GUEST)
        token = srm.auth.authenticate("alice", "password123")
        
        srm.create_resource("resource_1", "user_1")
        
        # GUEST 没有 WRITE 权限
        has_access, error = srm.check_access(token.token, "resource_1", Permission.WRITE)
        assert has_access is False
        assert error == "insufficient_token_permissions"
    
    def test_secure_operation(self):
        """测试安全操作"""
        srm = SecureResourceManager()
        srm.auth.register_user("alice", "password123")
        token = srm.auth.authenticate("alice", "password123")
        
        srm.create_resource("resource_1", token.user_id)
        
        def operation():
            return "success"
        
        success, result = srm.secure_operation(token.token, "resource_1", Permission.READ, operation)
        assert success is True
        assert result == "success"
    
    def test_secure_operation_denied(self):
        """测试拒绝的安全操作"""
        srm = SecureResourceManager()
        
        def operation():
            return "success"
        
        success, result = srm.secure_operation("invalid", "resource_1", Permission.READ, operation)
        assert success is False
        assert result == "invalid_token"
    
    def test_clear(self):
        """测试清空"""
        srm = SecureResourceManager()
        srm.auth.register_user("alice", "password123")
        srm.create_resource("resource_1", "user_1")
        
        srm.clear()
        assert srm.get_stats()["resources"] == 0
        assert srm.get_stats()["auth"]["total_users"] == 0

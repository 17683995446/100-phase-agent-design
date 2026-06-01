"""
安全与权限模块

提供身份验证、授权和访问控制功能。
遵循"图难于其易，为大于其细"原则，从简单可验证的实现开始。
"""

import hashlib
import secrets
import time
from typing import Dict, List, Optional, Set, Tuple, Callable, Any
from dataclasses import dataclass, field
from enum import Enum


class Permission(Enum):
    """权限枚举"""
    READ = "read"
    WRITE = "write"
    DELETE = "delete"
    ADMIN = "admin"


class Role(Enum):
    """角色枚举"""
    GUEST = "guest"
    USER = "user"
    EDITOR = "editor"
    ADMIN = "admin"


# 角色权限映射
ROLE_PERMISSIONS: Dict[Role, Set[Permission]] = {
    Role.GUEST: {Permission.READ},
    Role.USER: {Permission.READ, Permission.WRITE},
    Role.EDITOR: {Permission.READ, Permission.WRITE, Permission.DELETE},
    Role.ADMIN: {Permission.READ, Permission.WRITE, Permission.DELETE, Permission.ADMIN}
}


@dataclass
class User:
    """
    用户
    """
    user_id: str
    username: str
    password_hash: str
    salt: str
    role: Role = Role.USER
    is_active: bool = True
    created_at: float = field(default_factory=time.time)
    last_login: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def has_permission(self, permission: Permission) -> bool:
        """检查用户是否有指定权限"""
        if not self.is_active:
            return False
        return permission in ROLE_PERMISSIONS.get(self.role, set())
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典（不包含敏感信息）"""
        return {
            "user_id": self.user_id,
            "username": self.username,
            "role": self.role.value,
            "is_active": self.is_active,
            "created_at": self.created_at,
            "last_login": self.last_login,
            "metadata": self.metadata
        }


@dataclass
class AccessToken:
    """
    访问令牌
    """
    token: str
    user_id: str
    created_at: float
    expires_at: float
    permissions: Set[Permission] = field(default_factory=set)
    
    def is_valid(self) -> bool:
        """检查令牌是否有效"""
        return time.time() < self.expires_at
    
    def has_permission(self, permission: Permission) -> bool:
        """检查令牌是否有指定权限"""
        return permission in self.permissions


class PasswordHasher:
    """
    密码哈希器
    """
    
    @staticmethod
    def generate_salt() -> str:
        """生成随机盐值"""
        return secrets.token_hex(16)
    
    @staticmethod
    def hash_password(password: str, salt: str) -> str:
        """
        哈希密码
        
        使用 PBKDF2 算法。
        """
        return hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt.encode("utf-8"),
            iterations=100000
        ).hex()
    
    @staticmethod
    def verify_password(password: str, salt: str, password_hash: str) -> bool:
        """验证密码"""
        computed_hash = PasswordHasher.hash_password(password, salt)
        return secrets.compare_digest(computed_hash, password_hash)


class AuthManager:
    """
    认证管理器
    
    管理用户认证和令牌生成。
    """
    
    def __init__(self, token_ttl: float = 3600.0):
        """
        初始化认证管理器
        
        Args:
            token_ttl: 令牌有效期（秒）
        """
        self.token_ttl = token_ttl
        self._users: Dict[str, User] = {}  # username -> User
        self._tokens: Dict[str, AccessToken] = {}  # token -> AccessToken
        self._user_tokens: Dict[str, Set[str]] = {}  # user_id -> {tokens}
    
    def register_user(self, username: str, password: str,
                     role: Role = Role.USER) -> Optional[User]:
        """
        注册用户
        
        Args:
            username: 用户名
            password: 密码
            role: 角色
            
        Returns:
            注册成功的用户，如果用户名已存在则返回 None
        """
        if username in self._users:
            return None
        
        salt = PasswordHasher.generate_salt()
        password_hash = PasswordHasher.hash_password(password, salt)
        
        user = User(
            user_id=secrets.token_hex(8),
            username=username,
            password_hash=password_hash,
            salt=salt,
            role=role
        )
        
        self._users[username] = user
        return user
    
    def authenticate(self, username: str, password: str) -> Optional[AccessToken]:
        """
        用户认证
        
        Args:
            username: 用户名
            password: 密码
            
        Returns:
            认证成功返回访问令牌，失败返回 None
        """
        user = self._users.get(username)
        if not user or not user.is_active:
            return None
        
        if not PasswordHasher.verify_password(password, user.salt, user.password_hash):
            return None
        
        # 更新最后登录时间
        user.last_login = time.time()
        
        # 生成令牌
        token = self._generate_token(user)
        return token
    
    def _generate_token(self, user: User) -> AccessToken:
        """生成访问令牌"""
        token_str = secrets.token_urlsafe(32)
        now = time.time()
        
        token = AccessToken(
            token=token_str,
            user_id=user.user_id,
            created_at=now,
            expires_at=now + self.token_ttl,
            permissions=ROLE_PERMISSIONS.get(user.role, set()).copy()
        )
        
        self._tokens[token_str] = token
        
        if user.user_id not in self._user_tokens:
            self._user_tokens[user.user_id] = set()
        self._user_tokens[user.user_id].add(token_str)
        
        return token
    
    def validate_token(self, token_str: str) -> Optional[AccessToken]:
        """
        验证令牌
        
        Args:
            token_str: 令牌字符串
            
        Returns:
            有效的令牌对象，无效则返回 None
        """
        token = self._tokens.get(token_str)
        if not token or not token.is_valid():
            return None
        return token
    
    def revoke_token(self, token_str: str) -> bool:
        """
        撤销令牌
        
        Args:
            token_str: 令牌字符串
            
        Returns:
            是否成功撤销
        """
        token = self._tokens.get(token_str)
        if not token:
            return False
        
        del self._tokens[token_str]
        
        if token.user_id in self._user_tokens:
            self._user_tokens[token.user_id].discard(token_str)
        
        return True
    
    def revoke_all_user_tokens(self, user_id: str) -> int:
        """
        撤销用户的所有令牌
        
        Returns:
            撤销的令牌数量
        """
        tokens = self._user_tokens.get(user_id, set()).copy()
        for token_str in tokens:
            self.revoke_token(token_str)
        return len(tokens)
    
    def get_user_by_username(self, username: str) -> Optional[User]:
        """通过用户名获取用户"""
        return self._users.get(username)
    
    def get_user_by_id(self, user_id: str) -> Optional[User]:
        """通过 ID 获取用户"""
        for user in self._users.values():
            if user.user_id == user_id:
                return user
        return None
    
    def change_password(self, username: str, old_password: str,
                       new_password: str) -> bool:
        """
        修改密码
        
        Args:
            username: 用户名
            old_password: 旧密码
            new_password: 新密码
            
        Returns:
            是否成功修改
        """
        user = self._users.get(username)
        if not user:
            return False
        
        if not PasswordHasher.verify_password(old_password, user.salt, user.password_hash):
            return False
        
        # 生成新盐值和密码哈希
        user.salt = PasswordHasher.generate_salt()
        user.password_hash = PasswordHasher.hash_password(new_password, user.salt)
        
        # 撤销所有现有令牌
        self.revoke_all_user_tokens(user.user_id)
        
        return True
    
    def deactivate_user(self, username: str) -> bool:
        """停用用户"""
        user = self._users.get(username)
        if not user:
            return False
        
        user.is_active = False
        self.revoke_all_user_tokens(user.user_id)
        return True
    
    def activate_user(self, username: str) -> bool:
        """激活用户"""
        user = self._users.get(username)
        if not user:
            return False
        
        user.is_active = True
        return True
    
    def change_user_role(self, username: str, new_role: Role) -> bool:
        """更改用户角色"""
        user = self._users.get(username)
        if not user:
            return False
        
        user.role = new_role
        # 撤销所有现有令牌，强制重新登录以获取新权限
        self.revoke_all_user_tokens(user.user_id)
        return True
    
    def cleanup_expired_tokens(self) -> int:
        """
        清理过期令牌
        
        Returns:
            清理的令牌数量
        """
        expired = [
            token_str for token_str, token in self._tokens.items()
            if not token.is_valid()
        ]
        
        for token_str in expired:
            self.revoke_token(token_str)
        
        return len(expired)
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "total_users": len(self._users),
            "active_tokens": len(self._tokens),
            "expired_tokens": sum(
                1 for t in self._tokens.values() if not t.is_valid()
            )
        }
    
    def clear(self):
        """清空所有数据"""
        self._users.clear()
        self._tokens.clear()
        self._user_tokens.clear()


class AccessControl:
    """
    访问控制
    
    提供资源级别的访问控制。
    """
    
    def __init__(self):
        self._resource_permissions: Dict[str, Dict[str, Set[Permission]]] = {}
        # resource_id -> {user_id -> {permissions}}
    
    def grant_permission(self, resource_id: str, user_id: str,
                        permission: Permission):
        """
        授予权限
        
        Args:
            resource_id: 资源标识
            user_id: 用户标识
            permission: 权限
        """
        if resource_id not in self._resource_permissions:
            self._resource_permissions[resource_id] = {}
        
        if user_id not in self._resource_permissions[resource_id]:
            self._resource_permissions[resource_id][user_id] = set()
        
        self._resource_permissions[resource_id][user_id].add(permission)
    
    def revoke_permission(self, resource_id: str, user_id: str,
                         permission: Permission):
        """撤销权限"""
        if resource_id in self._resource_permissions:
            if user_id in self._resource_permissions[resource_id]:
                self._resource_permissions[resource_id][user_id].discard(permission)
    
    def check_permission(self, resource_id: str, user_id: str,
                        permission: Permission) -> bool:
        """
        检查权限
        
        Args:
            resource_id: 资源标识
            user_id: 用户标识
            permission: 权限
            
        Returns:
            是否有权限
        """
        # 检查资源特定权限
        if resource_id in self._resource_permissions:
            if user_id in self._resource_permissions[resource_id]:
                if permission in self._resource_permissions[resource_id][user_id]:
                    return True
        
        return False
    
    def get_resource_permissions(self, resource_id: str) -> Dict[str, Set[Permission]]:
        """获取资源的所有权限"""
        return {
            k: v.copy()
            for k, v in self._resource_permissions.get(resource_id, {}).items()
        }
    
    def remove_resource(self, resource_id: str):
        """移除资源的所有权限"""
        self._resource_permissions.pop(resource_id, None)
    
    def remove_user_permissions(self, user_id: str):
        """移除用户的所有权限"""
        for resource_perms in self._resource_permissions.values():
            resource_perms.pop(user_id, None)
    
    def clear(self):
        """清空所有权限"""
        self._resource_permissions.clear()


class SecureResourceManager:
    """
    安全资源管理器
    
    结合认证和访问控制，提供安全的资源管理。
    """
    
    def __init__(self):
        self.auth = AuthManager()
        self.access_control = AccessControl()
    
    def create_resource(self, resource_id: str, owner_id: str):
        """
        创建资源
        
        自动授予所有者所有权限。
        """
        for permission in Permission:
            self.access_control.grant_permission(resource_id, owner_id, permission)
    
    def check_access(self, token_str: str, resource_id: str,
                    permission: Permission) -> Tuple[bool, Optional[str]]:
        """
        检查访问权限
        
        Args:
            token_str: 访问令牌
            resource_id: 资源标识
            permission: 请求的权限
            
        Returns:
            (是否有权限, 错误信息)
        """
        # 验证令牌
        token = self.auth.validate_token(token_str)
        if not token:
            return False, "invalid_token"
        
        # 检查令牌权限
        if not token.has_permission(permission):
            return False, "insufficient_token_permissions"
        
        # 检查资源权限
        if not self.access_control.check_permission(resource_id, token.user_id, permission):
            return False, "resource_access_denied"
        
        return True, None
    
    def secure_operation(self, token_str: str, resource_id: str,
                        permission: Permission, operation: Callable) -> Tuple[bool, Any]:
        """
        执行安全操作
        
        Args:
            token_str: 访问令牌
            resource_id: 资源标识
            permission: 需要的权限
            operation: 操作函数
            
        Returns:
            (是否成功, 结果或错误信息)
        """
        has_access, error = self.check_access(token_str, resource_id, permission)
        
        if not has_access:
            return False, error
        
        try:
            result = operation()
            return True, result
        except Exception as e:
            return False, str(e)
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "auth": self.auth.get_stats(),
            "resources": len(self.access_control._resource_permissions)
        }
    
    def clear(self):
        """清空所有数据"""
        self.auth.clear()
        self.access_control.clear()

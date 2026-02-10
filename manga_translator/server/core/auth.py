"""
身份验证和授权模块

负责管理员令牌管理、密码验证和访问控制。
"""

import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
from fastapi import Header, HTTPException


# 有效的管理员 tokens（登录后生成）
valid_admin_tokens = set()
_BCRYPT_PREFIXES = ("$2a$", "$2b$", "$2y$")
_LEGACY_RATE_LIMIT_MAX_FAILED = 10
_LEGACY_RATE_LIMIT_WINDOW = timedelta(minutes=5)
_legacy_failed_attempts: dict[str, list[datetime]] = {}


def generate_admin_token() -> str:
    """生成管理员令牌"""
    return secrets.token_hex(32)


def is_bcrypt_hash(value: Optional[str]) -> bool:
    """判断字符串是否为 bcrypt 哈希。"""
    if not value:
        return False
    return any(value.startswith(prefix) for prefix in _BCRYPT_PREFIXES)


def hash_password(password: str) -> str:
    """对密码进行 bcrypt 哈希。"""
    password_bytes = password.encode("utf-8")[:72]
    return bcrypt.hashpw(password_bytes, bcrypt.gensalt()).decode("utf-8")


def verify_password_hash(password: str, password_hash: Optional[str]) -> bool:
    """验证明文密码与 bcrypt 哈希是否匹配。"""
    if not is_bcrypt_hash(password_hash):
        return False
    try:
        password_bytes = password.encode("utf-8")[:72]
        return bcrypt.checkpw(password_bytes, password_hash.encode("utf-8"))
    except Exception:
        return False


def verify_password_with_legacy_fallback(
    password: str,
    password_hash: Optional[str],
    legacy_password: Optional[str],
) -> tuple[bool, Optional[str]]:
    """
    验证密码，优先走哈希，失败后回退旧版明文（兼容迁移）。

    Returns:
        (是否匹配, 命中模式["hash"|"legacy"|None])
    """
    if verify_password_hash(password, password_hash):
        return True, "hash"
    if legacy_password and secrets.compare_digest(password, legacy_password):
        return True, "legacy"
    return False, None


def validate_admin_token(token: str) -> bool:
    """验证管理员令牌"""
    return token in valid_admin_tokens


def add_admin_token(token: str):
    """添加管理员令牌到有效集合"""
    valid_admin_tokens.add(token)


def remove_admin_token(token: str):
    """从有效集合中移除管理员令牌"""
    valid_admin_tokens.discard(token)


def clear_admin_tokens():
    """清除所有管理员令牌"""
    valid_admin_tokens.clear()


def _cleanup_legacy_attempts(key: str) -> None:
    now = datetime.now(timezone.utc)
    cutoff = now - _LEGACY_RATE_LIMIT_WINDOW
    attempts = _legacy_failed_attempts.get(key, [])
    _legacy_failed_attempts[key] = [ts for ts in attempts if ts > cutoff]


def check_legacy_rate_limit(key: str) -> tuple[bool, Optional[int]]:
    """
    检查 legacy 登录/改密接口的失败速率限制。

    Returns:
        (是否允许, 建议重试秒数)
    """
    _cleanup_legacy_attempts(key)
    attempts = _legacy_failed_attempts.get(key, [])
    if len(attempts) < _LEGACY_RATE_LIMIT_MAX_FAILED:
        return True, None
    retry_after = int((_LEGACY_RATE_LIMIT_WINDOW - (datetime.now(timezone.utc) - attempts[0])).total_seconds())
    return False, max(retry_after, 1)


def record_legacy_auth_failure(key: str) -> None:
    """记录 legacy 登录链路失败尝试。"""
    _cleanup_legacy_attempts(key)
    _legacy_failed_attempts.setdefault(key, []).append(datetime.now(timezone.utc))


def clear_legacy_auth_failures(key: str) -> None:
    """清理指定 key 的 legacy 失败记录。"""
    _legacy_failed_attempts.pop(key, None)


def reset_legacy_auth_rate_limit_state() -> None:
    """测试/维护用途：清空 legacy 登录速率限制状态。"""
    _legacy_failed_attempts.clear()


async def require_admin_token(token: str = Header(alias="X-Admin-Token", default=None)) -> str:
    """
    FastAPI 依赖注入函数：要求管理员令牌
    
    Args:
        token: 从请求头获取的令牌
    
    Returns:
        验证通过的令牌
    
    Raises:
        HTTPException: 如果令牌无效或缺失
    """
    if not token or not validate_admin_token(token):
        raise HTTPException(401, detail="Unauthorized")
    return token


def admin_login(
    password: str,
    admin_password: Optional[str] = None,
    admin_password_hash: Optional[str] = None,
) -> dict:
    """
    管理员登录
    
    Args:
        password: 用户提供的密码
        admin_password: 旧版明文管理员密码（兼容）
        admin_password_hash: bcrypt 哈希管理员密码（推荐）
    
    Returns:
        包含 success 和 token/message 的字典
    """
    if not admin_password_hash and not admin_password:
        return {"success": False, "message": "Admin password not set. Please setup first."}

    matched, _ = verify_password_with_legacy_fallback(password, admin_password_hash, admin_password)
    if matched:
        token = generate_admin_token()
        add_admin_token(token)
        return {"success": True, "token": token}
    
    return {"success": False, "message": "Invalid password"}


def setup_admin_password(password: str, current_password: Optional[str]) -> dict:
    """
    首次设置管理员密码
    
    Args:
        password: 新密码
        current_password: 当前密码（如果已设置）
    
    Returns:
        包含 success 和 token/message 的字典
    """
    # 只有在没有密码时才允许设置
    if current_password:
        return {"success": False, "message": "Admin password already set"}
    
    if not password or len(password) < 6:
        return {"success": False, "message": "Password must be at least 6 characters"}
    
    # 生成 token
    token = generate_admin_token()
    add_admin_token(token)
    
    return {"success": True, "token": token}


def change_admin_password(
    old_password: str,
    new_password: str,
    admin_password: Optional[str] = None,
    admin_password_hash: Optional[str] = None,
) -> dict:
    """
    更改管理员密码
    
    Args:
        old_password: 旧密码
        new_password: 新密码
        admin_password: 当前明文管理员密码（兼容）
        admin_password_hash: 当前哈希管理员密码（推荐）
    
    Returns:
        包含 success 和 message 的字典
    """
    # 验证旧密码
    matched, _ = verify_password_with_legacy_fallback(old_password, admin_password_hash, admin_password)
    if not matched:
        return {"success": False, "message": "旧密码错误"}
    
    # 验证新密码
    if not new_password or len(new_password) < 6:
        return {"success": False, "message": "新密码至少需要6位"}
    
    # 清除所有旧的 token（强制重新登录）
    clear_admin_tokens()
    
    return {"success": True, "message": "密码已更改，请重新登录"}


def user_login(password: str, user_access: dict) -> dict:
    """
    用户登录
    
    Args:
        password: 用户提供的密码
        user_access: 用户访问配置
    
    Returns:
        包含 success 和 message 的字典
    """
    # 如果不需要密码，直接允许访问
    if not user_access.get('require_password', False):
        return {"success": True, "message": "No password required"}
    
    password_hash = user_access.get("user_password_hash")
    legacy_password = user_access.get("user_password", "")
    matched, _ = verify_password_with_legacy_fallback(password, password_hash, legacy_password)
    if matched:
        return {"success": True, "message": "Login successful"}
    
    return {"success": False, "message": "Invalid password"}


def check_user_access(user_access: dict) -> dict:
    """
    检查用户访问是否需要密码
    
    Args:
        user_access: 用户访问配置
    
    Returns:
        包含 require_password 的字典
    """
    return {
        "require_password": user_access.get('require_password', False)
    }

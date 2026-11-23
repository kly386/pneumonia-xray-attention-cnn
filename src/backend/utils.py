"""密码哈希、密码校验与 JWT 编解码工具。"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple

import jwt
from passlib.context import CryptContext

# 生产环境必须通过环境变量覆盖默认密钥。
JWT_SECRET_KEY = os.getenv(
    "JWT_SECRET_KEY",
    "course-demo-change-this-secret-before-deployment",
)
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "120"))

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """使用 bcrypt 生成密码哈希。"""

    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """校验明文密码与数据库哈希是否匹配。"""

    try:
        return pwd_context.verify(plain_password, hashed_password)
    except (ValueError, TypeError):
        return False


def create_access_token(
    subject: str,
    expires_delta: Optional[timedelta] = None,
) -> Tuple[str, int]:
    """签发 JWT，并返回 Token 与有效秒数。"""

    now = datetime.now(timezone.utc)
    expires_delta = expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    expires_at = now + expires_delta
    expires_in = max(1, int(expires_delta.total_seconds()))

    payload = {
        "sub": subject,
        "type": "access",
        "iat": now,
        "exp": expires_at,
    }
    token = jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    return token, expires_in


def decode_access_token(token: str) -> dict:
    """解析并验证 JWT；过期或非法 Token 会抛出 PyJWT 异常。"""

    return jwt.decode(
        token,
        JWT_SECRET_KEY,
        algorithms=[JWT_ALGORITHM],
        options={"require": ["sub", "type", "iat", "exp"]},
    )
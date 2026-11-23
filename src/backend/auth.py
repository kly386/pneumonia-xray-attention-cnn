"""用户注册、登录与 JWT 鉴权依赖。"""

from __future__ import annotations

import base64
import logging
import os
import secrets
import sys
import time
from pathlib import Path
from typing import Optional

import jwt
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from src.backend.database import SessionLocal, User, get_db
from src.backend.schemas import (
    CaptchaResponse,
    LoginRequest,
    Token,
    UserCreate,
    UserProfileUpdate,
    UserResponse,
)
from src.backend.utils import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)

logger = logging.getLogger(__name__)
DEMO_USERNAME = os.getenv("DEMO_USERNAME", "doctor")
DEMO_PASSWORD = os.getenv("DEMO_PASSWORD", "123456")

# 医生个人资料由用户自行填写，系统不预置任何真实医师信息。
PROFILE_FIELDS = (
    "full_name",
    "title",
    "department",
    "hospital",
    "license_no",
    "phone",
)

# 旧版本曾写入的演示资料，启动时清理，避免冒充真实医师。
LEGACY_DEMO_PROFILE = {
    "full_name": "钟南山",
    "title": "主任医师 · 教授 · 中国工程院院士",
    "department": "呼吸与危重症医学科",
    "hospital": "广州医科大学附属第一医院",
    "license_no": "DEMO-2026-0001",
    "phone": None,
}

CAPTCHA_TTL_SECONDS = 180
CAPTCHA_STORE: dict[str, tuple[str, float]] = {}
CAPTCHA_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def _cleanup_expired_captchas(now: float) -> None:
    """移除已过期的验证码，避免内存持续增长。"""

    expired = [
        captcha_id
        for captcha_id, (_code, expires_at) in CAPTCHA_STORE.items()
        if expires_at <= now
    ]
    for captcha_id in expired:
        CAPTCHA_STORE.pop(captcha_id, None)


def _build_captcha_svg(code: str) -> str:
    """生成带干扰线和旋转字符的 SVG 验证码图片。"""

    width, height = 140, 46
    chars = []
    for index, char in enumerate(code):
        x = 20 + index * 28
        y = 32
        angle = secrets.randbelow(31) - 15
        chars.append(
            f'<text x="{x}" y="{y}" fill="#0e7490" font-size="26" '
            f'font-family="Consolas, monospace" font-weight="700" '
            f'transform="rotate({angle} {x} {y})">{char}</text>'
        )

    lines = []
    for _ in range(4):
        x1 = secrets.randbelow(width)
        y1 = secrets.randbelow(height)
        x2 = secrets.randbelow(width)
        y2 = secrets.randbelow(height)
        lines.append(
            f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" '
            f'stroke="#38bdf8" stroke-opacity="0.45" stroke-width="1.4" />'
        )

    dots = []
    for _ in range(16):
        cx = secrets.randbelow(width)
        cy = secrets.randbelow(height)
        dots.append(
            f'<circle cx="{cx}" cy="{cy}" r="1.2" fill="#0ea5e9" fill-opacity="0.5" />'
        )

    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}">'
        f'<rect width="{width}" height="{height}" rx="8" fill="#e0f2fe" />'
        f'{"".join(lines)}{"".join(dots)}{"".join(chars)}</svg>'
    )
    encoded = base64.b64encode(svg.encode("utf-8")).decode("ascii")
    return f"data:image/svg+xml;base64,{encoded}"


def _issue_captcha() -> CaptchaResponse:
    """生成并登记一枚新的图形验证码。"""

    now = time.time()
    _cleanup_expired_captchas(now)

    code = "".join(secrets.choice(CAPTCHA_ALPHABET) for _ in range(4))
    captcha_id = secrets.token_urlsafe(16)
    CAPTCHA_STORE[captcha_id] = (code, now + CAPTCHA_TTL_SECONDS)

    return CaptchaResponse(
        captcha_id=captcha_id,
        image=_build_captcha_svg(code),
        expires_in=CAPTCHA_TTL_SECONDS,
    )


def _verify_captcha(captcha_id: Optional[str], captcha_code: Optional[str]) -> bool:
    """校验图形验证码，使用后立即失效。"""

    if not captcha_id or not captcha_code:
        return False

    stored = CAPTCHA_STORE.pop(captcha_id, None)
    if stored is None:
        return False

    code, expires_at = stored
    if expires_at <= time.time():
        return False

    return secrets.compare_digest(code, captcha_code.strip().upper())

router = APIRouter(prefix="/api/auth", tags=["用户认证"])
oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/api/auth/login",
    auto_error=False,
)


def _unauthorized(code: str, message: str) -> HTTPException:
    """构造统一的 401 错误。"""

    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={"code": code, "message": message},
        headers={"WWW-Authenticate": "Bearer"},
    )


def _to_user_response(user: User) -> UserResponse:
    """将 ORM 用户对象转换为公开响应模型。"""

    return UserResponse(
        id=user.id,
        username=user.username,
        full_name=user.full_name,
        title=user.title,
        department=user.department,
        hospital=user.hospital,
        license_no=user.license_no,
        phone=user.phone,
        created_at=user.created_at,
    )


def _clean_profile_value(value: Optional[str]) -> Optional[str]:
    """去除个人资料首尾空白，空字符串按未填写处理。"""

    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


def ensure_demo_user() -> None:
    """首次启动时创建空资料的演示账号 doctor / 123456。

    医生资料由用户自行填写，演示账号不预置任何真实医师信息。
    """

    with SessionLocal() as db:
        existing_user = (
            db.query(User)
            .filter(User.username == DEMO_USERNAME)
            .first()
        )
        if existing_user is not None:
            changed = False
            for field in PROFILE_FIELDS:
                if getattr(existing_user, field) == LEGACY_DEMO_PROFILE.get(field):
                    setattr(existing_user, field, None)
                    changed = True
            if changed:
                db.commit()
                logger.info("已清理演示账号预置资料：%s", DEMO_USERNAME)
            return

        demo_user = User(
            username=DEMO_USERNAME,
            hashed_password=hash_password(DEMO_PASSWORD),
        )
        db.add(demo_user)
        db.commit()
        logger.info("已初始化演示账号：%s", DEMO_USERNAME)


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
def register(payload: UserCreate, db: Session = Depends(get_db)) -> UserResponse:
    """注册新用户。用户名不可重复，密码只保存 bcrypt 哈希。"""

    username = payload.username.strip()
    if len(username) < 3:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "INVALID_USERNAME", "message": "用户名至少需要 3 个字符"},
        )

    existing_user = db.query(User).filter(User.username == username).first()
    if existing_user is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "USERNAME_EXISTS", "message": "该用户名已被注册"},
        )

    user = User(
        username=username,
        hashed_password=hash_password(payload.password),
        full_name=_clean_profile_value(payload.full_name),
        title=_clean_profile_value(payload.title),
        department=_clean_profile_value(payload.department),
        hospital=_clean_profile_value(payload.hospital),
        license_no=_clean_profile_value(payload.license_no),
        phone=_clean_profile_value(payload.phone),
    )

    try:
        db.add(user)
        db.commit()
        db.refresh(user)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "USERNAME_EXISTS", "message": "该用户名已被注册"},
        ) from None

    return _to_user_response(user)


@router.get("/captcha", response_model=CaptchaResponse)
def get_captcha() -> CaptchaResponse:
    """获取图形验证码，登录时必须提交验证码。"""

    return _issue_captcha()


@router.post("/login", response_model=Token)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> Token:
    """校验图形验证码、用户名和密码，成功后返回 JWT。"""

    if not payload.captcha_id or not payload.captcha_code:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "CAPTCHA_REQUIRED", "message": "请输入图形验证码"},
        )

    if not _verify_captcha(payload.captcha_id, payload.captcha_code):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "INVALID_CAPTCHA", "message": "验证码错误或已过期，请刷新"},
        )

    username = payload.username.strip()
    user = db.query(User).filter(User.username == username).first()

    if user is None or not verify_password(payload.password, user.hashed_password):
        raise _unauthorized("UNAUTHORIZED", "用户名或密码错误")

    access_token, expires_in = create_access_token(subject=str(user.id))
    return Token(
        access_token=access_token,
        token_type="Bearer",
        expires_in=expires_in,
        user=_to_user_response(user),
    )


def get_current_user(
    token: Optional[str] = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    """从 Bearer Token 中解析当前用户，供受保护接口依赖。"""

    if not token:
        raise _unauthorized("UNAUTHORIZED", "未提供有效登录凭证")

    try:
        payload = decode_access_token(token)
    except jwt.ExpiredSignatureError:
        raise _unauthorized("TOKEN_EXPIRED", "登录已过期，请重新登录") from None
    except jwt.InvalidTokenError:
        raise _unauthorized("INVALID_TOKEN", "登录凭证无效，请重新登录") from None

    if payload.get("type") != "access":
        raise _unauthorized("INVALID_TOKEN", "登录凭证类型错误")

    subject = payload.get("sub")
    try:
        user_id = int(subject)
    except (TypeError, ValueError):
        raise _unauthorized("INVALID_TOKEN", "登录凭证无效，请重新登录") from None

    user = db.get(User, user_id)
    if user is None:
        raise _unauthorized("INVALID_TOKEN", "用户不存在或已失效")

    return user


@router.get("/me", response_model=UserResponse)
def get_profile(
    current_user: User = Depends(get_current_user),
) -> UserResponse:
    """返回当前登录医生的个人信息。"""

    return _to_user_response(current_user)


@router.patch("/me", response_model=UserResponse)
def update_profile(
    payload: UserProfileUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UserResponse:
    """更新当前登录医生的个人信息并持久化到数据库。"""

    updates = payload.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(current_user, field, _clean_profile_value(value))

    db.add(current_user)
    db.commit()
    db.refresh(current_user)
    return _to_user_response(current_user)
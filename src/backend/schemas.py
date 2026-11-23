"""后端 API 使用的 Pydantic 请求与响应模型。"""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class UserCreate(BaseModel):
    """注册请求。"""

    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=6, max_length=72)
    full_name: Optional[str] = Field(default=None, max_length=64)
    title: Optional[str] = Field(default=None, max_length=64)
    department: Optional[str] = Field(default=None, max_length=128)
    hospital: Optional[str] = Field(default=None, max_length=255)
    license_no: Optional[str] = Field(default=None, max_length=64)
    phone: Optional[str] = Field(default=None, max_length=32)


class UserProfileUpdate(BaseModel):
    """医生个人资料更新请求。"""

    full_name: Optional[str] = Field(default=None, max_length=64)
    title: Optional[str] = Field(default=None, max_length=64)
    department: Optional[str] = Field(default=None, max_length=128)
    hospital: Optional[str] = Field(default=None, max_length=255)
    license_no: Optional[str] = Field(default=None, max_length=64)
    phone: Optional[str] = Field(default=None, max_length=32)


class LoginRequest(BaseModel):
    """登录请求。"""

    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=72)
    captcha_id: Optional[str] = Field(default=None, max_length=64)
    captcha_code: Optional[str] = Field(default=None, max_length=16)


class CaptchaResponse(BaseModel):
    """图形验证码响应。"""

    captcha_id: str
    image: str
    expires_in: int


class UserResponse(BaseModel):
    """返回给前端的用户公开信息。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    full_name: Optional[str] = None
    title: Optional[str] = None
    department: Optional[str] = None
    hospital: Optional[str] = None
    license_no: Optional[str] = None
    phone: Optional[str] = None
    created_at: datetime


class Token(BaseModel):
    """登录成功后的 JWT 响应。"""

    access_token: str
    token_type: str = "Bearer"
    expires_in: int
    user: UserResponse


class ClinicalInfo(BaseModel):
    """可选临床信息，用于影像概率的晚期融合。"""

    model_config = ConfigDict(extra="forbid")

    age: Optional[int] = Field(default=None, ge=0, le=120)
    gender: Optional[Literal["MALE", "FEMALE"]] = None
    temperature: Optional[float] = Field(default=None, ge=30.0, le=45.0)
    cough_days: Optional[int] = Field(default=None, ge=0, le=365)


class Probabilities(BaseModel):
    """两类别的概率。"""

    NORMAL: float = Field(ge=0.0, le=1.0)
    PNEUMONIA: float = Field(ge=0.0, le=1.0)


class PredictionInfo(BaseModel):
    """单次模型预测结果。"""

    probs: Probabilities
    label: str
    threshold: float
    confidence: float = Field(ge=0.0, le=1.0)


class GradCAMInfo(BaseModel):
    """Grad-CAM 可视化信息。"""

    status: str
    original_url: str = ""
    heatmap_url: str = ""
    overlay_url: str = ""


class ImageResult(BaseModel):
    """多图筛查中单张影像的预测结果。"""

    filename: str
    label: str
    final_label: str = ""
    confidence: float = Field(ge=0.0, le=1.0)
    prob_pneumonia: float = Field(ge=0.0, le=1.0)
    final_prob: float = Field(default=0.0, ge=0.0, le=1.0)
    clinical_risk: str = ""
    age: Optional[int] = None
    gender: Optional[str] = None
    temperature: Optional[float] = None
    cough_days: Optional[int] = None
    original_url: str = ""
    heatmap_url: str = ""


class PredictResponse(BaseModel):
    """预测接口响应。"""

    request_id: str
    record_id: int
    filename: str
    prediction: PredictionInfo
    gradcam: GradCAMInfo
    heatmap_url: str = ""
    original_url: str = ""
    images: list[ImageResult] = []
    primary_index: int = 0
    image_prob: float = Field(ge=0.0, le=1.0)
    clinical_risk: str
    final_prob: float = Field(ge=0.0, le=1.0)
    model_version: str
    inference_ms: int
    created_at: datetime


class HistoryItem(BaseModel):
    """历史记录列表项。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    filename: str
    prediction: str
    confidence: float
    prob_pneumonia: float
    age: Optional[int] = None
    gender: Optional[str] = None
    temperature: Optional[float] = None
    cough_days: Optional[int] = None
    original_url: Optional[str] = ""
    heatmap_url: Optional[str] = ""
    doctor_label: Optional[Literal["NORMAL", "PNEUMONIA"]] = None
    use_ai_judgement: Optional[bool] = None
    created_at: datetime


class JudgementUpdate(BaseModel):
    """医生初步评判：是否采用 AI 判定或改为医生判定。"""

    use_ai_judgement: bool
    doctor_label: Optional[Literal["NORMAL", "PNEUMONIA"]] = None


class HistoryResponse(BaseModel):
    """分页历史记录响应。"""

    page: int
    page_size: int
    total: int
    items: list[HistoryItem]


class TrendPoint(BaseModel):
    """近 7 天趋势中的单日数据。"""

    date: str
    normal: int
    pneumonia: int
    total: int


class AgeBucket(BaseModel):
    """按年龄段聚合的阴阳性人数。"""

    age_group: str
    normal: int
    pneumonia: int
    total: int


class GenderBucket(BaseModel):
    """按性别聚合的阴阳性人数。"""

    gender: str
    normal: int
    pneumonia: int
    total: int


class DashboardResponse(BaseModel):
    """数据看板响应。"""

    total_diagnoses: int
    pneumonia_count: int
    normal_count: int
    pneumonia_rate: float
    last_7_days: list[TrendPoint]
    age_distribution: list[AgeBucket]
    gender_distribution: list[GenderBucket]


class ModelInfoResponse(BaseModel):
    """模型信息看板响应。"""

    model_name: str
    architecture: str
    deployment_format: str
    accuracy: float
    auc: float
    threshold: float
    input_shape: list[int]
    class_order: list[str]


class MessageResponse(BaseModel):
    """通用消息响应。"""

    message: str

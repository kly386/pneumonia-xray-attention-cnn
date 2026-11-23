"""肺炎 X 光片智能辅助诊断系统 FastAPI 主入口。"""

from __future__ import annotations

import json
import logging
import math
import os
import sys
import time
import uuid
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta, timezone
from io import BytesIO
from pathlib import Path
from typing import Optional

from fastapi import (
    Depends,
    FastAPI,
    File,
    Form,
    HTTPException,
    Query,
    Request,
    Response,
    UploadFile,
    status,
)
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from PIL import Image
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from starlette.exceptions import HTTPException as StarletteHTTPException

# 兼容从项目根目录或 PyCharm 的 src/backend 工作目录直接运行。
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from src.backend.auth import ensure_demo_user, get_current_user
from src.backend.auth import router as auth_router
from src.backend.database import HistoryRecord, User, get_db, init_db
from src.backend.model_loader import (
    PNEUMONIA_THRESHOLD,
    generate_gradcam,
    load_model,
    predict_image,
)
from src.backend.schemas import (
    AgeBucket,
    ClinicalInfo,
    DashboardResponse,
    GenderBucket,
    GradCAMInfo,
    HistoryItem,
    HistoryResponse,
    ImageResult,
    JudgementUpdate,
    ModelInfoResponse,
    PredictResponse,
    PredictionInfo,
    Probabilities,
    TrendPoint,
)

logger = logging.getLogger(__name__)

MODEL_VERSION = "resnet50_baseline"
MAX_FILE_SIZE = 10 * 1024 * 1024
MIN_IMAGE_SIDE = 64
MAX_IMAGE_PIXELS = 40_000_000
CHINA_TZ = timezone(timedelta(hours=8))
UPLOAD_DIR = Path(__file__).resolve().parent / "uploads"
HEATMAP_DIR = UPLOAD_DIR / "heatmaps"
ORIGINAL_DIR = UPLOAD_DIR / "originals"
HEATMAP_URL_PREFIX = "/api/files/heatmaps"
ORIGINAL_URL_PREFIX = "/api/files/originals"
MAX_IMAGES = 3
ALLOWED_EXTENSIONS = {
    ".jpg": ("image/jpeg", "JPEG"),
    ".jpeg": ("image/jpeg", "JPEG"),
    ".png": ("image/png", "PNG"),
}


def _cors_origins() -> list[str]:
    """读取允许跨域的前端地址。"""

    raw_origins = os.getenv(
        "CORS_ORIGINS",
        "http://localhost:15173,http://127.0.0.1:15173",
    )
    return [item.strip() for item in raw_origins.split(",") if item.strip()]


@asynccontextmanager
async def lifespan(_: FastAPI):
    """应用启动时建表并加载 ONNX 模型。"""

    init_db()
    ensure_demo_user()
    load_model()
    logger.info("数据库初始化完成，ONNX 模型已加载")
    yield


app = FastAPI(
    title="肺炎 X 光片智能辅助诊断系统 API",
    description="基于 ResNet50 + ONNX Runtime 的 NORMAL / PNEUMONIA 二分类辅助筛查接口",
    version="1.0.0",
    lifespan=lifespan,
)

HEATMAP_DIR.mkdir(parents=True, exist_ok=True)
ORIGINAL_DIR.mkdir(parents=True, exist_ok=True)
app.mount(
    "/api/files",
    StaticFiles(directory=str(UPLOAD_DIR)),
    name="files",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept"],
    expose_headers=["WWW-Authenticate"],
)

# 注册、登录、JWT 依赖统一放在 auth.py 中。
app.include_router(auth_router)


@app.get("/", include_in_schema=False)
def root() -> dict:
    """浏览器访问后端根地址时返回服务状态和接口入口。"""

    return {
        "name": "肺炎 X 光片智能辅助诊断系统 API",
        "status": "ok",
        "docs": "/docs",
        "health": "/api/health",
        "openapi": "/openapi.json",
    }


@app.get("/api/health", tags=["系统"])
def health_check() -> dict:
    """返回后端、模型版本和判定阈值的健康状态。"""

    return {
        "status": "ok",
        "model_version": MODEL_VERSION,
        "threshold": PNEUMONIA_THRESHOLD,
    }


@app.get("/favicon.ico", include_in_schema=False)
def favicon() -> Response:
    """避免浏览器自动请求 favicon 时产生 404 日志。"""

    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _api_error(
    status_code: int,
    code: str,
    message: str,
    details: Optional[object] = None,
) -> HTTPException:
    """构造统一格式的业务异常。"""

    return HTTPException(
        status_code=status_code,
        detail={
            "request_id": str(uuid.uuid4()),
            "code": code,
            "message": message,
            "details": details,
        },
    )


def _status_code_error(status_code: int) -> str:
    """将常见 HTTP 状态码映射为业务错误码。"""

    return {
        400: "INVALID_REQUEST",
        401: "UNAUTHORIZED",
        403: "FORBIDDEN",
        404: "NOT_FOUND",
        413: "FILE_TOO_LARGE",
        422: "IMAGE_DECODE_ERROR",
        500: "INTERNAL_ERROR",
        503: "MODEL_UNAVAILABLE",
    }.get(status_code, "INTERNAL_ERROR")


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(
    _: Request,
    exc: StarletteHTTPException,
) -> JSONResponse:
    """统一处理业务异常与框架 HTTP 异常。"""

    detail = exc.detail
    if isinstance(detail, dict) and "code" in detail and "message" in detail:
        content = {
            "request_id": detail.get("request_id", str(uuid.uuid4())),
            "code": detail["code"],
            "message": detail["message"],
            "details": detail.get("details"),
        }
    else:
        content = {
            "request_id": str(uuid.uuid4()),
            "code": _status_code_error(exc.status_code),
            "message": str(detail),
            "details": None,
        }

    return JSONResponse(
        status_code=exc.status_code,
        content=content,
        headers=exc.headers,
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    _: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    """将 Pydantic 校验错误转换为统一 400 响应，且不回显原始输入。"""

    details = [
        {
            "field": ".".join(str(part) for part in error.get("loc", [])),
            "message": error.get("msg", "参数校验失败"),
            "type": error.get("type", "value_error"),
        }
        for error in exc.errors()
    ]
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={
            "request_id": str(uuid.uuid4()),
            "code": "INVALID_REQUEST",
            "message": "请求参数格式不正确",
            "details": details,
        },
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(_: Request, exc: Exception) -> JSONResponse:
    """兜底处理未捕获异常，避免向前端暴露服务端堆栈。"""

    logger.exception("未处理的后端异常：%s", exc)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "request_id": str(uuid.uuid4()),
            "code": "INTERNAL_ERROR",
            "message": "服务器内部错误，请稍后重试",
            "details": None,
        },
    )


def _read_and_validate_image(file: UploadFile) -> tuple[str, bytes]:
    """校验文件名、MIME、大小、文件头及图片可解码性。"""

    filename = Path((file.filename or "").strip()).name
    suffix = Path(filename).suffix.lower()
    allowed = ALLOWED_EXTENSIONS.get(suffix)

    if not filename or allowed is None:
        raise _api_error(
            status.HTTP_400_BAD_REQUEST,
            "INVALID_FILE_TYPE",
            "仅支持 JPG、JPEG、PNG 格式的 X 光片",
            {"allowed_extensions": [".jpg", ".jpeg", ".png"]},
        )

    expected_mime, expected_format = allowed
    if (file.content_type or "").lower() != expected_mime:
        raise _api_error(
            status.HTTP_400_BAD_REQUEST,
            "INVALID_FILE_TYPE",
            "文件 MIME 类型与扩展名不匹配",
        )

    image_bytes = file.file.read(MAX_FILE_SIZE + 1)
    if len(image_bytes) > MAX_FILE_SIZE:
        raise _api_error(
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            "FILE_TOO_LARGE",
            "文件大小不得超过 10 MB",
            {"max_mb": 10},
        )
    if not image_bytes:
        raise _api_error(
            status.HTTP_400_BAD_REQUEST,
            "INVALID_FILE_CONTENT",
            "文件为空或已损坏",
        )

    signature_ok = (
        image_bytes.startswith(b"\x89PNG\r\n\x1a\n")
        if expected_format == "PNG"
        else image_bytes.startswith(b"\xff\xd8\xff")
    )
    if not signature_ok:
        raise _api_error(
            status.HTTP_400_BAD_REQUEST,
            "INVALID_FILE_CONTENT",
            "文件内容与图片格式不匹配",
        )

    try:
        with Image.open(BytesIO(image_bytes)) as image:
            detected_format = (image.format or "").upper()
            width, height = image.size
            image.verify()
    except Exception:
        raise _api_error(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "IMAGE_DECODE_ERROR",
            "影像无法解析，请更换文件",
        ) from None

    if detected_format != expected_format:
        raise _api_error(
            status.HTTP_400_BAD_REQUEST,
            "INVALID_FILE_CONTENT",
            "图片实际格式与文件扩展名不一致",
        )
    if width < MIN_IMAGE_SIDE or height < MIN_IMAGE_SIDE:
        raise _api_error(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "IMAGE_DECODE_ERROR",
            "影像尺寸过小，最小尺寸为 64×64",
        )
    if width * height > MAX_IMAGE_PIXELS:
        raise _api_error(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "IMAGE_DECODE_ERROR",
            "影像像素总量过大，请压缩后重试",
        )

    return filename, image_bytes


def _normalize_gender(value: object) -> object:
    """将前端可能提交的中英文性别写法统一为 MALE / FEMALE。"""

    if not isinstance(value, str):
        return value

    normalized = value.strip().lower()
    mapping = {
        "male": "MALE",
        "m": "MALE",
        "男": "MALE",
        "男性": "MALE",
        "female": "FEMALE",
        "f": "FEMALE",
        "女": "FEMALE",
        "女性": "FEMALE",
    }
    return mapping.get(normalized, value)


def _save_original_image(filename: str, image_bytes: bytes) -> str:
    """保存原始上传影像并返回静态访问 URL。"""

    suffix = Path(filename).suffix.lower()
    if suffix == ".jpeg":
        suffix = ".jpg"
    if suffix not in {".jpg", ".png"}:
        suffix = ".jpg"

    try:
        ORIGINAL_DIR.mkdir(parents=True, exist_ok=True)
        saved_name = f"{uuid.uuid4()}{suffix}"
        (ORIGINAL_DIR / saved_name).write_bytes(image_bytes)
        return f"{ORIGINAL_URL_PREFIX}/{saved_name}"
    except OSError:
        logger.exception("原始影像保存失败：%s", filename)
        return ""


def _parse_clinical_info(
    clinical_data: Optional[str],
    age: Optional[int],
    gender: Optional[str],
    temperature: Optional[float],
    cough_days: Optional[int],
) -> ClinicalInfo:
    """解析可选临床信息，兼容 JSON 字符串和独立 multipart 字段。"""

    payload: dict[str, object] = {}

    if clinical_data and clinical_data.strip():
        try:
            parsed = json.loads(clinical_data)
        except json.JSONDecodeError:
            raise _api_error(
                status.HTTP_400_BAD_REQUEST,
                "INVALID_REQUEST",
                "clinical_data 必须是合法 JSON 对象",
            ) from None

        if not isinstance(parsed, dict):
            raise _api_error(
                status.HTTP_400_BAD_REQUEST,
                "INVALID_REQUEST",
                "clinical_data 必须是 JSON 对象",
            )

        payload.update(parsed)

    direct_values = {
        "age": age,
        "gender": gender,
        "temperature": temperature,
        "cough_days": cough_days,
    }
    payload.update(
        {key: value for key, value in direct_values.items() if value is not None}
    )

    if "gender" in payload:
        normalized_gender = _normalize_gender(payload["gender"])
        if isinstance(normalized_gender, str) and not normalized_gender.strip():
            payload.pop("gender")
        else:
            payload["gender"] = normalized_gender

    try:
        return ClinicalInfo(**payload)
    except ValueError as exc:
        raise _api_error(
            status.HTTP_400_BAD_REQUEST,
            "INVALID_REQUEST",
            "临床信息格式不正确",
            {"reason": str(exc)},
        ) from None


def _parse_patients_info(
    patients_data: Optional[str],
    fallback: ClinicalInfo,
    count: int,
) -> list[ClinicalInfo]:
    """解析每张影像对应的受检者临床信息。"""

    if not patients_data or not patients_data.strip():
        return [fallback for _ in range(count)]

    try:
        parsed = json.loads(patients_data)
    except json.JSONDecodeError:
        raise _api_error(
            status.HTTP_400_BAD_REQUEST,
            "INVALID_REQUEST",
            "patients_data 必须是合法 JSON 数组",
        ) from None

    if not isinstance(parsed, list):
        raise _api_error(
            status.HTTP_400_BAD_REQUEST,
            "INVALID_REQUEST",
            "patients_data 必须是 JSON 数组",
        )

    infos: list[ClinicalInfo] = []
    for payload in parsed[:count]:
        if not isinstance(payload, dict):
            raise _api_error(
                status.HTTP_400_BAD_REQUEST,
                "INVALID_REQUEST",
                "每条患者临床信息必须是 JSON 对象",
            )

        item = dict(payload)
        if "gender" in item:
            normalized_gender = _normalize_gender(item["gender"])
            if (
                isinstance(normalized_gender, str)
                and not normalized_gender.strip()
            ):
                item.pop("gender")
            else:
                item["gender"] = normalized_gender

        try:
            infos.append(ClinicalInfo(**item))
        except ValueError as exc:
            raise _api_error(
                status.HTTP_400_BAD_REQUEST,
                "INVALID_REQUEST",
                "患者临床信息格式不正确",
                {"reason": str(exc)},
            ) from None

    while len(infos) < count:
        infos.append(ClinicalInfo())

    return infos


def _fuse_clinical_probability(
    prob_image: float,
    clinical: ClinicalInfo,
) -> tuple[float, str]:
    """按规则引擎对影像概率进行临床晚期融合。"""

    has_clinical = any(
        value is not None
        for value in (
            clinical.age,
            clinical.gender,
            clinical.temperature,
            clinical.cough_days,
        )
    )
    if not has_clinical:
        return float(prob_image), "未填写临床信息"

    prob_final = prob_image

    if clinical.temperature is not None and clinical.temperature > 38.5:
        prob_final += 0.05
    if clinical.age is not None and clinical.age > 65:
        prob_final += 0.03
    if clinical.cough_days is not None and clinical.cough_days > 3:
        prob_final += 0.02

    prob_final = min(prob_final, 0.99)
    clinical_risk = (
        "有风险提示" if prob_final > prob_image else "无明显高危特征"
    )
    return float(prob_final), clinical_risk


def _to_china_datetime(value: datetime) -> datetime:
    """将数据库中的无时区 UTC 时间转换为东八区时间。"""

    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(CHINA_TZ)


def _local_date(value: datetime) -> date:
    """将数据库时间转换为东八区自然日。"""

    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(CHINA_TZ).date()


@app.post(
    "/api/predict",
    response_model=PredictResponse,
    status_code=status.HTTP_200_OK,
)
def predict(
    file: Optional[UploadFile] = File(default=None),
    files: Optional[list[UploadFile]] = File(default=None),
    clinical_data: Optional[str] = Form(default=None),
    patients_data: Optional[str] = Form(default=None),
    age: Optional[int] = Form(default=None),
    gender: Optional[str] = Form(default=None),
    temperature: Optional[float] = Form(default=None),
    cough_days: Optional[int] = Form(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PredictResponse:
    """执行 1–3 张胸片推理，并按最高风险影像写入历史记录。"""

    uploads: list[UploadFile] = []
    if file is not None and file.filename:
        uploads.append(file)
    if files:
        uploads.extend(
            item for item in files if item is not None and item.filename
        )

    if not uploads:
        raise _api_error(
            status.HTTP_400_BAD_REQUEST,
            "NO_FILE",
            "请至少上传 1 张影像",
        )
    if len(uploads) > MAX_IMAGES:
        raise _api_error(
            status.HTTP_400_BAD_REQUEST,
            "TOO_MANY_FILES",
            f"单次最多上传 {MAX_IMAGES} 张影像",
            {"max_images": MAX_IMAGES},
        )

    validated_images = [
        _read_and_validate_image(item) for item in uploads
    ]
    filenames = [name for name, _ in validated_images]
    request_id = str(uuid.uuid4())
    clinical_info = _parse_clinical_info(
        clinical_data=clinical_data,
        age=age,
        gender=gender,
        temperature=temperature,
        cough_days=cough_days,
    )
    patient_infos = _parse_patients_info(
        patients_data=patients_data,
        fallback=clinical_info,
        count=len(validated_images),
    )

    started_at = time.perf_counter()
    try:
        image_items = []
        for name, image_bytes in validated_images:
            label, confidence, prob_pneumonia = predict_image(image_bytes)
            image_items.append(
                {
                    "filename": name,
                    "label": str(label).strip().upper(),
                    "confidence": float(confidence),
                    "prob_pneumonia": float(prob_pneumonia),
                    "bytes": image_bytes,
                }
            )
    except Exception:
        logger.exception("ONNX 推理失败（request_id=%s）", request_id)
        raise _api_error(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "MODEL_UNAVAILABLE",
            "模型服务暂不可用，请稍后重试",
        ) from None
    inference_ms = max(0, int(round((time.perf_counter() - started_at) * 1000)))

    try:
        for item in image_items:
            if item["label"] not in {"NORMAL", "PNEUMONIA"}:
                raise ValueError("未知预测类别")
            if not all(
                math.isfinite(value) and 0.0 <= value <= 1.0
                for value in (item["confidence"], item["prob_pneumonia"])
            ):
                raise ValueError("预测概率超出有效范围")
    except (TypeError, ValueError):
        logger.exception("模型输出格式异常（request_id=%s）", request_id)
        raise _api_error(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "INTERNAL_ERROR",
            "模型输出异常，请稍后重试",
        ) from None

    for item in image_items:
        heatmap_filename = generate_gradcam(item["bytes"])
        item["heatmap_url"] = (
            f"{HEATMAP_URL_PREFIX}/{heatmap_filename}"
            if heatmap_filename
            else ""
        )
        item["original_url"] = _save_original_image(
            item["filename"], item["bytes"]
        )

    for index, item in enumerate(image_items):
        fused_prob, risk = _fuse_clinical_probability(
            prob_image=item["prob_pneumonia"],
            clinical=patient_infos[index],
        )
        item["final_prob"] = float(fused_prob)
        item["final_label"] = (
            "PNEUMONIA"
            if fused_prob >= PNEUMONIA_THRESHOLD
            else "NORMAL"
        )
        item["clinical_risk"] = risk

    # 多图筛查以融合后最高风险影像作为主影像，避免漏掉局部阳性表现。
    primary_item = max(
        image_items,
        key=lambda item: item["final_prob"],
    )
    primary_index = image_items.index(primary_item)

    heatmap_url = primary_item["heatmap_url"]
    original_url = primary_item["original_url"]
    gradcam_status = "AVAILABLE" if heatmap_url else "UNAVAILABLE"
    image_results = [
        ImageResult(
            filename=item["filename"],
            label=item["label"],
            final_label=item["final_label"],
            confidence=item["confidence"],
            prob_pneumonia=item["prob_pneumonia"],
            final_prob=item["final_prob"],
            clinical_risk=item["clinical_risk"],
            age=patient_infos[index].age,
            gender=patient_infos[index].gender,
            temperature=patient_infos[index].temperature,
            cough_days=patient_infos[index].cough_days,
            original_url=item["original_url"],
            heatmap_url=item["heatmap_url"],
        )
        for index, item in enumerate(image_items)
    ]

    prob_final = primary_item["final_prob"]
    clinical_risk = primary_item["clinical_risk"]
    final_label = primary_item["final_label"]
    prob_image = primary_item["prob_pneumonia"]
    prob_normal = 1.0 - prob_final
    final_confidence = (
        prob_final if final_label == "PNEUMONIA" else prob_normal
    )

    records = []
    for index, item in enumerate(image_items):
        patient = patient_infos[index]
        item_prob = item["final_prob"]
        item_label = item["final_label"]
        item_confidence = (
            item_prob if item_label == "PNEUMONIA" else 1.0 - item_prob
        )
        records.append(
            HistoryRecord(
                user_id=current_user.id,
                filename=item["filename"][:255],
                prediction=item_label,
                confidence=item_confidence,
                prob_pneumonia=item_prob,
                age=patient.age,
                gender=patient.gender,
                temperature=patient.temperature,
                cough_days=patient.cough_days,
                original_url=item["original_url"],
                heatmap_url=item["heatmap_url"],
            )
        )

    primary_record = records[primary_index]

    try:
        db.add_all(records)
        db.commit()
        db.refresh(primary_record)
    except SQLAlchemyError:
        db.rollback()
        logger.exception("诊断记录写入失败（request_id=%s）", request_id)
        raise _api_error(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "INTERNAL_ERROR",
            "诊断结果保存失败，请稍后重试",
        ) from None

    return PredictResponse(
        request_id=request_id,
        record_id=primary_record.id,
        filename=" | ".join(filenames)[:255],
        prediction=PredictionInfo(
            probs=Probabilities(
                NORMAL=prob_normal,
                PNEUMONIA=prob_final,
            ),
            label=final_label,
            threshold=PNEUMONIA_THRESHOLD,
            confidence=final_confidence,
        ),
        gradcam=GradCAMInfo(
            status=gradcam_status,
            original_url=original_url,
            heatmap_url=heatmap_url,
            overlay_url=heatmap_url,
        ),
        heatmap_url=heatmap_url,
        original_url=original_url,
        images=image_results,
        primary_index=primary_index,
        image_prob=prob_image,
        clinical_risk=clinical_risk,
        final_prob=prob_final,
        model_version=MODEL_VERSION,
        inference_ms=inference_ms,
        created_at=_to_china_datetime(primary_record.created_at),
    )

def _to_history_item(record: HistoryRecord) -> HistoryItem:
    """将数据库记录转换为历史记录响应。"""

    return HistoryItem(
        id=record.id,
        filename=record.filename,
        prediction=record.prediction,
        confidence=record.confidence,
        prob_pneumonia=record.prob_pneumonia,
        age=record.age,
        gender=record.gender,
        temperature=record.temperature,
        cough_days=record.cough_days,
        original_url=record.original_url or "",
        heatmap_url=record.heatmap_url or "",
        doctor_label=record.doctor_label,
        use_ai_judgement=record.use_ai_judgement,
        created_at=_to_china_datetime(record.created_at),
    )


@app.get("/api/history", response_model=HistoryResponse)
def get_history(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=50),
    prediction: Optional[str] = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> HistoryResponse:
    """分页查询当前用户的历史诊断记录。"""

    query = db.query(HistoryRecord).filter(
        HistoryRecord.user_id == current_user.id,
    )

    if prediction:
        prediction_filter = prediction.strip().upper()
        if prediction_filter not in {"NORMAL", "PNEUMONIA"}:
            raise _api_error(
                status.HTTP_400_BAD_REQUEST,
                "INVALID_REQUEST",
                "prediction 仅支持 NORMAL 或 PNEUMONIA",
            )
        query = query.filter(HistoryRecord.prediction == prediction_filter)

    total = query.count()
    records = (
        query.order_by(HistoryRecord.created_at.desc(), HistoryRecord.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    items = [_to_history_item(record) for record in records]

    return HistoryResponse(
        page=page,
        page_size=page_size,
        total=total,
        items=items,
    )


@app.get("/api/history/{record_id}", response_model=HistoryItem)
def get_history_detail(
    record_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> HistoryItem:
    """返回单条历史记录详情（含原始影像与热力图 URL）。"""

    record = (
        db.query(HistoryRecord)
        .filter(
            HistoryRecord.id == record_id,
            HistoryRecord.user_id == current_user.id,
        )
        .first()
    )
    if record is None:
        raise _api_error(
            status.HTTP_404_NOT_FOUND,
            "RECORD_NOT_FOUND",
            "记录不存在或无权访问",
        )

    return _to_history_item(record)


@app.patch("/api/history/{record_id}/judgement", response_model=HistoryItem)
def update_history_judgement(
    record_id: int,
    payload: JudgementUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> HistoryItem:
    """保存医生对单条筛查记录的初步评判。"""

    record = (
        db.query(HistoryRecord)
        .filter(
            HistoryRecord.id == record_id,
            HistoryRecord.user_id == current_user.id,
        )
        .first()
    )
    if record is None:
        raise _api_error(
            status.HTTP_404_NOT_FOUND,
            "RECORD_NOT_FOUND",
            "记录不存在或无权访问",
        )

    if payload.use_ai_judgement:
        record.use_ai_judgement = True
        record.doctor_label = None
    else:
        if payload.doctor_label is None:
            raise _api_error(
                status.HTTP_400_BAD_REQUEST,
                "INVALID_REQUEST",
                "选择医生复核判定时必须提供 doctor_label",
            )
        record.use_ai_judgement = False
        record.doctor_label = payload.doctor_label

    try:
        db.commit()
        db.refresh(record)
    except SQLAlchemyError:
        db.rollback()
        raise _api_error(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "INTERNAL_ERROR",
            "保存医生评判失败，请稍后重试",
        ) from None

    return _to_history_item(record)


@app.delete("/api/history/{record_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_history(
    record_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    """删除当前用户的一条历史记录；禁止跨用户删除。"""

    record = (
        db.query(HistoryRecord)
        .filter(
            HistoryRecord.id == record_id,
            HistoryRecord.user_id == current_user.id,
        )
        .first()
    )
    if record is None:
        raise _api_error(
            status.HTTP_404_NOT_FOUND,
            "RECORD_NOT_FOUND",
            "记录不存在或无权访问",
        )

    try:
        db.delete(record)
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        raise _api_error(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "INTERNAL_ERROR",
            "删除记录失败，请稍后重试",
        ) from None

    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.get("/api/stats/dashboard", response_model=DashboardResponse)
def get_dashboard(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DashboardResponse:
    """返回当前用户的总诊断数、分类数量与近 7 天趋势。"""

    records = (
        db.query(HistoryRecord)
        .filter(HistoryRecord.user_id == current_user.id)
        .all()
    )

    total_diagnoses = len(records)
    pneumonia_count = sum(
        1 for record in records if record.prediction == "PNEUMONIA"
    )
    normal_count = total_diagnoses - pneumonia_count
    pneumonia_rate = (
        pneumonia_count / total_diagnoses if total_diagnoses else 0.0
    )

    today = datetime.now(CHINA_TZ).date()
    start_date = today - timedelta(days=6)
    trend = {
        start_date + timedelta(days=offset): {"normal": 0, "pneumonia": 0}
        for offset in range(7)
    }

    for record in records:
        record_date = _local_date(record.created_at)
        if start_date <= record_date <= today:
            if record.prediction == "PNEUMONIA":
                trend[record_date]["pneumonia"] += 1
            else:
                trend[record_date]["normal"] += 1

    last_7_days = [
        TrendPoint(
            date=day.isoformat(),
            normal=trend[day]["normal"],
            pneumonia=trend[day]["pneumonia"],
            total=trend[day]["normal"] + trend[day]["pneumonia"],
        )
        for day in sorted(trend)
    ]

    age_labels = ["0-18", "19-40", "41-65", "65+"]
    age_counts = {
        label: {"normal": 0, "pneumonia": 0} for label in age_labels
    }
    unknown_age = {"normal": 0, "pneumonia": 0}

    gender_labels = {"MALE": "男性", "FEMALE": "女性"}
    gender_counts = {
        label: {"normal": 0, "pneumonia": 0}
        for label in ("男性", "女性")
    }
    unknown_gender = {"normal": 0, "pneumonia": 0}

    for record in records:
        result_key = (
            "pneumonia" if record.prediction == "PNEUMONIA" else "normal"
        )

        age = record.age
        if age is None:
            bucket = unknown_age
        elif age <= 18:
            bucket = age_counts["0-18"]
        elif age <= 40:
            bucket = age_counts["19-40"]
        elif age <= 65:
            bucket = age_counts["41-65"]
        else:
            bucket = age_counts["65+"]

        gender_label = gender_labels.get(
            (record.gender or "").strip().upper()
        )
        gender_bucket = (
            gender_counts[gender_label]
            if gender_label is not None
            else unknown_gender
        )

        bucket[result_key] += 1
        gender_bucket[result_key] += 1

    age_distribution = [
        AgeBucket(
            age_group=label,
            normal=age_counts[label]["normal"],
            pneumonia=age_counts[label]["pneumonia"],
            total=(
                age_counts[label]["normal"]
                + age_counts[label]["pneumonia"]
            ),
        )
        for label in age_labels
    ]
    if unknown_age["normal"] + unknown_age["pneumonia"] > 0:
        age_distribution.append(
            AgeBucket(
                age_group="未填写",
                normal=unknown_age["normal"],
                pneumonia=unknown_age["pneumonia"],
                total=unknown_age["normal"] + unknown_age["pneumonia"],
            )
        )

    gender_distribution = [
        GenderBucket(
            gender=label,
            normal=gender_counts[label]["normal"],
            pneumonia=gender_counts[label]["pneumonia"],
            total=(
                gender_counts[label]["normal"]
                + gender_counts[label]["pneumonia"]
            ),
        )
        for label in ("男性", "女性")
    ]
    if unknown_gender["normal"] + unknown_gender["pneumonia"] > 0:
        gender_distribution.append(
            GenderBucket(
                gender="未填写",
                normal=unknown_gender["normal"],
                pneumonia=unknown_gender["pneumonia"],
                total=unknown_gender["normal"] + unknown_gender["pneumonia"],
            )
        )

    return DashboardResponse(
        total_diagnoses=total_diagnoses,
        pneumonia_count=pneumonia_count,
        normal_count=normal_count,
        pneumonia_rate=pneumonia_rate,
        last_7_days=last_7_days,
        age_distribution=age_distribution,
        gender_distribution=gender_distribution,
    )


@app.get("/api/model/info", response_model=ModelInfoResponse)
def get_model_info(_: User = Depends(get_current_user)) -> ModelInfoResponse:
    """返回当前部署模型的静态信息。"""

    return ModelInfoResponse(
        model_name="ResNet50",
        architecture="ResNet50 + 二分类全连接层",
        deployment_format="ONNX Runtime (FP32)",
        accuracy=0.974,
        auc=0.9946,
        threshold=PNEUMONIA_THRESHOLD,
        input_shape=[3, 224, 224],
        class_order=["NORMAL", "PNEUMONIA"],
    )
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "src.backend.main:app",
        host="127.0.0.1",
        port=18080,
        reload=False,
    )
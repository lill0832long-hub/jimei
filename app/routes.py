"""API 路由注册 — 安全加固版"""
import os
import time
import logging
import functools
import json

from fastapi import Request
from fastapi.responses import JSONResponse
from app.services.fixed_asset_service import FixedAssetService
from app.services.account_service import AccountService
from app.services.ledger_service import LedgerService
from app.services.voucher_service import VoucherService

logger = logging.getLogger(__name__)
DEBUG = os.getenv("DEBUG", "false").lower() == "true"


# ── 统一错误处理装饰器 ──

def api_error_handler(func):
    """API 错误处理装饰器

    生产环境：返回友好提示，不暴露内部信息
    开发环境：返回详细错误信息（通过 DEBUG 环境变量控制）
    """
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except ValueError as e:
            logger.warning(f"Validation error in {func.__name__}: {e}")
            msg = str(e) if DEBUG else "输入数据无效"
            return JSONResponse({"success": False, "error": msg}, status_code=400)
        except KeyError as e:
            logger.warning(f"Missing field in {func.__name__}: {e}")
            msg = f"缺少必填字段: {e}" if DEBUG else "缺少必填字段"
            return JSONResponse({"success": False, "error": msg}, status_code=400)
        except PermissionError as e:
            logger.warning(f"Permission denied in {func.__name__}: {e}")
            msg = str(e) if DEBUG else "权限不足"
            return JSONResponse({"success": False, "error": msg}, status_code=403)
        except FileNotFoundError as e:
            logger.warning(f"Not found in {func.__name__}: {e}")
            msg = str(e) if DEBUG else "请求的资源不存在"
            return JSONResponse({"success": False, "error": msg}, status_code=404)
        except Exception as e:
            logger.error(f"Unexpected error in {func.__name__}: {e}", exc_info=True)
            msg = str(e) if DEBUG else "服务器内部错误，请稍后重试"
            return JSONResponse({"success": False, "error": msg}, status_code=500)
    return wrapper


# ── 输入验证辅助函数 ──

def _validate_positive_number(value, field_name, allow_zero=False):
    """验证数值为正数"""
    try:
        num = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{field_name} 必须是有效数字")
    if not allow_zero and num <= 0:
        raise ValueError(f"{field_name} 必须为正数")
    if allow_zero and num < 0:
        raise ValueError(f"{field_name} 不能为负数")
    return num


def _validate_positive_integer(value, field_name):
    """验证正整数"""
    try:
        num = int(value)
    except (TypeError, ValueError):
        raise ValueError(f"{field_name} 必须是整数")
    if num <= 0:
        raise ValueError(f"{field_name} 必须为正整数")
    return num


def _validate_range(value, min_val, max_val, field_name):
    """验证数值在指定范围内"""
    num = _validate_positive_number(value, field_name, allow_zero=True)
    if num < min_val or num > max_val:
        raise ValueError(f"{field_name} 必须在 {min_val} 到 {max_val} 之间")
    return num


def _validate_not_empty(value, field_name):
    """验证非空字符串"""
    if not value or not str(value).strip():
        raise ValueError(f"{field_name} 不能为空")
    return str(value).strip()


def _validate_account_no(account_no):
    """验证银行账号格式"""
    _validate_not_empty(account_no, "account_no")
    cleaned = str(account_no).replace(" ", "").replace("-", "")
    if not cleaned.isdigit():
        raise ValueError("账号只能包含数字、空格和连字符")
    if len(cleaned) < 8:
        raise ValueError("账号长度不能少于 8 位")
    return cleaned


VALID_AUX_TYPES = {"customer", "supplier", "department", "employee", "project", "other"}


def _validate_aux_type(aux_type):
    """验证辅助核算类型"""
    _validate_not_empty(aux_type, "aux_type")
    if aux_type not in VALID_AUX_TYPES:
        raise ValueError(f"aux_type 无效，必须为以下之一: {', '.join(sorted(VALID_AUX_TYPES))}")
    return aux_type


def register_routes(app):
    """注册所有 GET + POST API 路由"""

    # ── 请求日志中间件 ──
    @app.middleware("http")
    async def log_requests(request: Request, call_next):
        """记录 API 请求日志（仅 /api/ 路径）"""
        start = time.time()
        response = await call_next(request)
        duration = time.time() - start

        if request.url.path.startswith("/api/"):
            logger.info(
                f"{request.method} {request.url.path} "
                f"status={response.status_code} "
                f"duration={duration:.3f}s"
            )

        return response

    # ═══════════════════════════
    #  GET 路由
    # ═══════════════════════════

    @app.get("/api/v3/fa/list")
    @api_error_handler
    async def api_v3_fa_list(ledger_id: int, status: str = None):
        assets = FixedAssetService.get_all(ledger_id, status=status)
        return {"success": True, "data": assets, "count": len(assets)}

    @app.get("/api/v3/fa/{asset_id}")
    @api_error_handler
    async def api_v3_fa_detail(asset_id: int):
        a = FixedAssetService.get_by_id(asset_id)
        if not a:
            raise FileNotFoundError("固定资产不存在")
        return {"success": True, "data": a}

    @app.get("/api/v3/bank/list")
    @api_error_handler
    async def api_v3_bank_list(ledger_id: int):
        return {"success": True, "data": AccountService.get_bank_accounts(ledger_id)}

    @app.get("/api/v3/bank/{bank_id}/reconciliation")
    @api_error_handler
    async def api_v3_bank_reconciliation(bank_id: int, period: str = None):
        return {"success": True, "data": AccountService.get_bank_reconciliation(bank_id, period)}

    @app.get("/api/v3/aux/list")
    @api_error_handler
    async def api_v3_aux_list(ledger_id: int, aux_type: str = None):
        return {"success": True, "data": AccountService.get_auxiliaries(ledger_id, category=aux_type)}

    @app.get("/api/v3/period/status")
    @api_error_handler
    async def api_v3_period_status(ledger_id: int, year: int, month: int):
        period = LedgerService.get_period_status(ledger_id, year, month)
        return {"success": True, "data": {"status": period, "period": f"{year}-{month:02d}"}}

    # ═══════════════════════════
    #  POST 路由
    # ═══════════════════════════

    @app.post("/api/v3/fa/create")
    @api_error_handler
    async def _fa_create(request: Request):
        p = request.query_params
        # 输入验证
        ledger_id = _validate_positive_integer(p.get("ledger_id"), "ledger_id")
        asset_code = _validate_not_empty(p.get("asset_code"), "asset_code")
        asset_name = _validate_not_empty(p.get("asset_name"), "asset_name")
        original_value = _validate_positive_number(p.get("original_value", 0), "original_value")
        useful_life_months = _validate_positive_integer(p.get("useful_life_months"), "useful_life_months")
        residual_rate = _validate_range(p.get("residual_rate", 0.05), 0, 1, "residual_rate")

        ov = int(round(original_value * 100))
        asset = FixedAssetService.create(
            ledger_id, asset_code, asset_name, ov,
            useful_life_months,
            category_id=int(p["category_id"]) if "category_id" in p else None,
            purchase_date=p.get("purchase_date"),
            residual_rate=residual_rate,
            department=p.get("department"), employee=p.get("employee"),
            location=p.get("location"),
            depreciation_method=p.get("depreciation_method", "straight_line"),
        )
        return JSONResponse({"success": True, "id": asset.id})

    @app.post("/api/v3/fa/{asset_id}/depreciate")
    @api_error_handler
    async def _fa_depreciate(request: Request):
        p = request.path_params
        q = request.query_params
        asset_id = _validate_positive_integer(p.get("asset_id"), "asset_id")
        year = _validate_positive_integer(q.get("year"), "year")
        month = _validate_positive_integer(q.get("month"), "month")
        if month < 1 or month > 12:
            raise ValueError("month 必须在 1 到 12 之间")
        amt = FixedAssetService.calculate_depreciation(asset_id, year, month)
        return JSONResponse({"success": True, "amount": amt, "amount_yuan": round(amt / 100, 2)})

    @app.post("/api/v3/fa/batch-depreciate")
    @api_error_handler
    async def _fa_batch_dep(request: Request):
        q = request.query_params
        ledger_id = _validate_positive_integer(q.get("ledger_id"), "ledger_id")
        year = _validate_positive_integer(q.get("year"), "year")
        month = _validate_positive_integer(q.get("month"), "month")
        if month < 1 or month > 12:
            raise ValueError("month 必须在 1 到 12 之间")
        results = FixedAssetService.batch_calculate_depreciation(ledger_id, year, month)
        total = sum(r[1] for r in results)
        return JSONResponse({
            "success": True,
            "results": [{"asset_id": r[0], "amount": r[1]} for r in results],
            "total": total, "total_yuan": round(total / 100, 2),
        })

    @app.post("/api/v3/fa/{asset_id}/dispose")
    @api_error_handler
    async def _fa_dispose(request: Request):
        p = request.path_params
        q = request.query_params
        asset_id = _validate_positive_integer(p.get("asset_id"), "asset_id")
        dispose_type = _validate_not_empty(q.get("dispose_type"), "dispose_type")
        if dispose_type not in ("sale", "scrap", "donation", "other"):
            raise ValueError("dispose_type 无效，必须为 sale/scrap/donation/other")
        proceeds = _validate_positive_number(q.get("proceeds", 0), "proceeds", allow_zero=True)
        result = FixedAssetService.dispose(asset_id, dispose_type, int(round(proceeds * 100)))
        if not result:
            raise FileNotFoundError("资产不存在")
        return JSONResponse({"success": True, "data": result})

    @app.post("/api/v3/bank/create")
    @api_error_handler
    async def _bank_create(request: Request):
        q = request.query_params
        ledger_id = _validate_positive_integer(q.get("ledger_id"), "ledger_id")
        account_no = _validate_account_no(q.get("account_no"))
        bank_name = _validate_not_empty(q.get("bank_name"), "bank_name")
        opening_balance = _validate_positive_number(
            q.get("opening_balance", 0), "opening_balance", allow_zero=True
        )
        ob = int(round(opening_balance * 100))
        result = AccountService.create_bank_account(
            ledger_id,
            account_no=account_no,
            bank_name=bank_name,
            account_name=q.get("account_name"),
            currency_code=q.get("currency_code", "CNY"),
            opening_balance=ob,
            subject_code=q.get("subject_code"),
        )
        rid = result.get("id") if isinstance(result, dict) else getattr(result, "id", result)
        return JSONResponse({"success": True, "id": rid})

    @app.post("/api/v3/bank/{bank_id}/reconcile")
    @api_error_handler
    async def _bank_reconcile(request: Request):
        p = request.path_params
        bank_id = _validate_positive_integer(p.get("bank_id"), "bank_id")
        matched = AccountService.auto_match(bank_id)
        return JSONResponse({"success": True, "matched": matched})

    @app.post("/api/v3/aux/create")
    @api_error_handler
    async def _aux_create(request: Request):
        q = request.query_params
        ledger_id = _validate_positive_integer(q.get("ledger_id"), "ledger_id")
        name = _validate_not_empty(q.get("name"), "name")
        aux_type = _validate_aux_type(q.get("aux_type"))
        result = AccountService.create_auxiliary(ledger_id, name, aux_type)
        rid = result.get("id") if isinstance(result, dict) else getattr(result, "id", result)
        return JSONResponse({"success": True, "id": rid})

    @app.post("/api/v3/period/close")
    @api_error_handler
    async def _period_close(request: Request):
        q = request.query_params
        ledger_id = _validate_positive_integer(q.get("ledger_id"), "ledger_id")
        year = _validate_positive_integer(q.get("year"), "year")
        month = _validate_positive_integer(q.get("month"), "month")
        vn = LedgerService.close_period(ledger_id, year, month)
        if vn:
            return JSONResponse({"success": True, "voucher_no": vn, "message": f"结转成功，凭证号：{vn}"})
        return JSONResponse({"success": True, "message": "无需结转"})

    @app.post("/api/v3/period/reverse")
    @api_error_handler
    async def _period_reverse(request: Request):
        q = request.query_params
        ledger_id = _validate_positive_integer(q.get("ledger_id"), "ledger_id")
        year = _validate_positive_integer(q.get("year"), "year")
        month = _validate_positive_integer(q.get("month"), "month")
        result = LedgerService.reverse_close_period(ledger_id, year, month)
        return JSONResponse({"success": True, "data": result})

    # ═══════════════════════════
    #  标注 API（设计协作）
    # ═══════════════════════════

    # 标注文件保存路径：优先用环境变量，否则用项目根目录下的 .claude/annotations/
    # 在 WSL 环境中运行时，通过 /mnt/e/... 映射到 Windows 工作区，确保 Claude Code 可直接读取
    _ANNOTATIONS_DIR = os.environ.get(
        "ANNOTATIONS_DIR",
        os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".claude", "annotations")
    )
    # 如果 WSL 映射存在，优先使用 Windows 侧路径（方便 Claude Code 读取）
    _wsl_alt = "/mnt/e/ClaudeCode/my-project/.claude/annotations"
    if os.path.isdir("/mnt/e/ClaudeCode/my-project/.claude"):
        _ANNOTATIONS_DIR = _wsl_alt
    os.makedirs(_ANNOTATIONS_DIR, exist_ok=True)

    def _annotation_file(page: str) -> str:
        safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in page)
        return os.path.join(_ANNOTATIONS_DIR, f"{safe}.json")

    @app.get("/api/v1/annotations/{page}")
    async def api_get_annotations(page: str):
        """读取页面标注"""
        f = _annotation_file(page)
        if os.path.exists(f):
            with open(f, "r", encoding="utf-8") as fh:
                data = json.load(fh)
        else:
            data = {"page": page, "annotations": []}
        return JSONResponse({"success": True, "data": data})

    @app.post("/api/v1/annotations/{page}")
    async def api_save_annotations(page: str, request: Request):
        """保存页面标注"""
        body = await request.json()
        f = _annotation_file(page)
        with open(f, "w", encoding="utf-8") as fh:
            json.dump(body, fh, ensure_ascii=False, indent=2)
        return JSONResponse({"success": True, "message": "标注已保存"})
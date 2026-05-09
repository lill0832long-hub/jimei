"""API 路由注册"""
from fastapi import Request
from fastapi.responses import JSONResponse
from database_v3 import (
    get_fixed_assets, get_fixed_asset, create_fixed_asset,
    calculate_depreciation, batch_calculate_depreciation, dispose_asset,
    get_bank_accounts, create_bank_account, auto_match_bank_statement,
    get_bank_reconciliation, get_auxiliaries, create_auxiliary,
    close_period, reverse_close_period, get_period_status,
)


def register_routes(app):
    """注册所有 GET + POST API 路由"""

    # ── GET 路由 ──
    @app.get("/api/v3/fa/list")
    async def api_v3_fa_list(ledger_id: int, status: str = None):
        try:
            assets = get_fixed_assets(ledger_id, status=status)
            return {"success": True, "data": assets, "count": len(assets)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @app.get("/api/v3/fa/{asset_id}")
    async def api_v3_fa_detail(asset_id: int):
        try:
            a = get_fixed_asset(asset_id)
            return {"success": True, "data": a} if a else {"success": False, "error": "不存在"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @app.get("/api/v3/bank/list")
    async def api_v3_bank_list(ledger_id: int):
        try:
            return {"success": True, "data": get_bank_accounts(ledger_id)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @app.get("/api/v3/bank/{bank_id}/reconciliation")
    async def api_v3_bank_reconciliation(bank_id: int, period: str = None):
        try:
            return {"success": True, "data": get_bank_reconciliation(bank_id, period)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @app.get("/api/v3/aux/list")
    async def api_v3_aux_list(ledger_id: int, aux_type: str = None):
        try:
            return {"success": True, "data": get_auxiliaries(ledger_id, aux_type=aux_type)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @app.get("/api/v3/period/status")
    async def api_v3_period_status(ledger_id: int, year: int, month: int):
        try:
            status = get_period_status(ledger_id, year, month)
            result = {"status": "closed" if status.get("closed") else "open", "period": f"{year}-{month:02d}"}
            if status.get("voucher_no"):
                result["voucher_no"] = status["voucher_no"]
                result["closed_at"] = status["closed_at"]
            return {"success": True, "data": result}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ── POST 路由 ──
    async def _fa_create(request: Request):
        p = request.query_params
        try:
            ov = int(round(float(p.get("original_value", 0)) * 100))
            aid = create_fixed_asset(
                int(p["ledger_id"]), p["asset_code"], p["asset_name"], ov,
                int(p["useful_life_months"]),
                category_id=int(p["category_id"]) if "category_id" in p else None,
                purchase_date=p.get("purchase_date"),
                residual_rate=float(p.get("residual_rate", 0.05)),
                department=p.get("department"), employee=p.get("employee"),
                location=p.get("location"),
                depreciation_method=p.get("depreciation_method", "straight_line"))
            return JSONResponse({"success": True, "id": aid})
        except Exception as e:
            return JSONResponse({"success": False, "error": str(e)}, status_code=400)

    async def _fa_depreciate(request: Request):
        p = request.path_params
        q = request.query_params
        try:
            amt = calculate_depreciation(int(p["asset_id"]), int(q["year"]), int(q["month"]))
            return JSONResponse({"success": True, "amount": amt, "amount_yuan": round(amt/100, 2)})
        except Exception as e:
            return JSONResponse({"success": False, "error": str(e)}, status_code=400)

    async def _fa_batch_dep(request: Request):
        q = request.query_params
        try:
            results = batch_calculate_depreciation(int(q["ledger_id"]), int(q["year"]), int(q["month"]))
            total = sum(r[1] for r in results)
            return JSONResponse({"success": True,
                "results": [{"asset_id": r[0], "amount": r[1]} for r in results],
                "total": total, "total_yuan": round(total/100, 2)})
        except Exception as e:
            return JSONResponse({"success": False, "error": str(e)}, status_code=400)

    async def _fa_dispose(request: Request):
        p = request.path_params
        q = request.query_params
        try:
            r = dispose_asset(int(p["asset_id"]), q["dispose_type"], int(round(float(q.get("proceeds", 0))*100)))
            return JSONResponse({"success": True, "data": r}) if r else JSONResponse({"success": False, "error": "资产不存在"}, status_code=404)
        except Exception as e:
            return JSONResponse({"success": False, "error": str(e)}, status_code=400)

    async def _bank_create(request: Request):
        q = request.query_params
        try:
            ob = int(round(float(q.get("opening_balance", 0)) * 100))
            bid = create_bank_account(int(q["ledger_id"]), q["account_no"], q["bank_name"],
                account_name=q.get("account_name"), currency_code=q.get("currency_code", "CNY"),
                opening_balance=ob, subject_code=q.get("subject_code"))
            return JSONResponse({"success": True, "id": bid})
        except Exception as e:
            return JSONResponse({"success": False, "error": str(e)}, status_code=400)

    async def _bank_reconcile(request: Request):
        p = request.path_params
        try:
            return JSONResponse({"success": True, "matched": auto_match_bank_statement(int(p["bank_id"]))})
        except Exception as e:
            return JSONResponse({"success": False, "error": str(e)}, status_code=400)

    async def _aux_create(request: Request):
        q = request.query_params
        try:
            aid = create_auxiliary(int(q["ledger_id"]), q["aux_type"], q["code"], q["name"],
                parent_id=int(q["parent_id"]) if "parent_id" in q else None)
            return JSONResponse({"success": True, "id": aid})
        except Exception as e:
            return JSONResponse({"success": False, "error": str(e)}, status_code=400)

    async def _period_close(request: Request):
        q = request.query_params
        try:
            vn = close_period(int(q["ledger_id"]), int(q["year"]), int(q["month"]))
            if vn:
                return JSONResponse({"success": True, "voucher_no": vn, "message": f"结转成功，凭证号：{vn}"})
            else:
                return JSONResponse({"success": True, "message": "无需结转"})
        except Exception as e:
            return JSONResponse({"success": False, "error": str(e)}, status_code=400)

    async def _period_reverse(request: Request):
        q = request.query_params
        try:
            return JSONResponse(reverse_close_period(int(q["ledger_id"]), int(q["year"]), int(q["month"])))
        except Exception as e:
            return JSONResponse({"success": False, "error": str(e)}, status_code=400)

    app.add_api_route("/api/v3/fa/create", _fa_create, methods=["POST"])
    app.add_api_route("/api/v3/fa/{asset_id}/depreciate", _fa_depreciate, methods=["POST"])
    app.add_api_route("/api/v3/fa/batch-depreciate", _fa_batch_dep, methods=["POST"])
    app.add_api_route("/api/v3/fa/{asset_id}/dispose", _fa_dispose, methods=["POST"])
    app.add_api_route("/api/v3/bank/create", _bank_create, methods=["POST"])
    app.add_api_route("/api/v3/bank/{bank_id}/reconcile", _bank_reconcile, methods=["POST"])
    app.add_api_route("/api/v3/aux/create", _aux_create, methods=["POST"])
    app.add_api_route("/api/v3/period/close", _period_close, methods=["POST"])
    app.add_api_route("/api/v3/period/reverse", _period_reverse, methods=["POST"])

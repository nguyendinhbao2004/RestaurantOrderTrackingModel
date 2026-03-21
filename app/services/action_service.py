"""
app/services/action_service.py
--------------------------------
Executes .NET 10 API calls based on a parsed intent.

Each handler method corresponds to one intent name from IntentService.
Add a new handler to support a new voice command.

Authentication with .NET backend:
    Reads DOTNET_API_KEY from settings and attaches it as 'X-API-Key' header.
    Adjust to match your .NET authentication scheme if needed.
"""

from __future__ import annotations

import unicodedata
from typing import Any

import httpx

from app.core.config import Settings
from app.core.logging import get_logger
from app.schemas.voice_schema import ActionResult

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Vietnamese response messages
# ---------------------------------------------------------------------------

_MSG = {
    "create_user_ok":     "Tạo tài khoản thành công.",
    "create_user_fail":   "Tạo tài khoản thất bại: {detail}",
    "create_user_miss":   "Thiếu thông tin: cần có tên đăng nhập và mật khẩu.",
    "delete_user_ok":     "Xóa tài khoản thành công.",
    "delete_user_fail":   "Xóa tài khoản thất bại: {detail}",
    "delete_user_miss":   "Thiếu thông tin: cần có tên hoặc ID để xóa.",
    "list_users_ok":      "Lấy danh sách người dùng thành công.",
    "list_users_fail":    "Không lấy được danh sách người dùng: {detail}",
    "get_user_ok":        "Tìm thấy thông tin người dùng.",
    "get_user_fail":      "Không tìm thấy người dùng: {detail}",
    "create_product_ok":  "Tạo sản phẩm thành công.",
    "create_product_fail":"Tạo sản phẩm thất bại: {detail}",
    "create_product_miss":"Thiếu thông tin: cần có tên sản phẩm.",
    "create_product_exists":"Món này đã có trong hệ thống, không tạo trùng.",
    "delete_product_ok":  "Xóa sản phẩm thành công.",
    "delete_product_fail":"Xóa sản phẩm thất bại: {detail}",
    "delete_product_miss":"Thiếu thông tin: cần tên hoặc ID sản phẩm.",
    "list_products_ok":   "Lấy danh sách sản phẩm thành công.",
    "list_products_fail": "Không lấy được danh sách sản phẩm: {detail}",
    "create_order_ok":    "Tạo đơn hàng thành công.",
    "create_order_fail":  "Tạo đơn hàng thất bại: {detail}",
    "create_order_miss":  "Thiếu thông tin: cần có tên món để gọi món.",
    "create_order_not_found": "Không tìm thấy món trong danh sách sản phẩm: {detail}",
    "list_orders_ok":     "Lấy danh sách đơn hàng thành công.",
    "list_orders_fail":   "Không lấy được danh sách đơn hàng: {detail}",
    "unknown_intent":     "Không nhận ra lệnh. Vui lòng thử lại.",
    "api_error":          "Lỗi kết nối đến hệ thống: {detail}",
}


class ActionService:
    """
    Bridges parsed voice intents to concrete .NET 10 API calls.

    All methods are async (use httpx.AsyncClient internally).
    Timeout defaults to 10 s per call to keep the voice pipeline snappy.
    """

    TIMEOUT = httpx.Timeout(10.0)

    def __init__(self, settings: Settings) -> None:
        self._base_url = settings.dotnet_api_base_url.rstrip("/")
        self._headers = {
            "X-API-Key": settings.dotnet_api_key,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    async def execute(self, intent: str, params: dict[str, Any]) -> ActionResult:
        """
        Dispatch to the appropriate handler based on intent name.
        Returns a structured ActionResult regardless of success/failure.
        """
        handler = getattr(self, f"_handle_{intent}", self._handle_unknown)
        try:
            return await handler(params)
        except httpx.RequestError as exc:
            msg = _MSG["api_error"].format(detail=str(exc))
            logger.error("HTTP request error.", intent=intent, error=str(exc))
            return ActionResult(success=False, http_status=503, message=msg)

    # ------------------------------------------------------------------
    # Intent handlers — one per intent in INTENT_CATALOG
    # ------------------------------------------------------------------

    async def _handle_create_user(self, params: dict) -> ActionResult:
        username = params.get("username")
        password = params.get("password")
        if not username or not password:
            return ActionResult(
                success=False,
                http_status=400,
                message=_MSG["create_user_miss"],
            )
        payload: dict[str, Any] = {"username": username, "password": password}
        if "email" in params:
            payload["email"] = params["email"]
        if "role" in params:
            payload["role"] = params["role"]

        return await self._post("/api/users", payload, "create_user")

    async def _handle_delete_user(self, params: dict) -> ActionResult:
        if "user_id" in params:
            return await self._delete(f"/api/users/{params['user_id']}", "delete_user")
        if "username" in params:
            return await self._delete(f"/api/users/by-name/{params['username']}", "delete_user")
        return ActionResult(
            success=False, http_status=400, message=_MSG["delete_user_miss"]
        )

    async def _handle_list_users(self, params: dict) -> ActionResult:
        return await self._get("/api/users", "list_users")

    async def _handle_get_user(self, params: dict) -> ActionResult:
        if "user_id" in params:
            return await self._get(f"/api/users/{params['user_id']}", "get_user")
        if "username" in params:
            return await self._get(f"/api/users/by-name/{params['username']}", "get_user")
        return await self._get("/api/users", "list_users")

    async def _handle_create_product(self, params: dict) -> ActionResult:
        if "name" not in params:
            return ActionResult(
                success=False, http_status=400, message=_MSG["create_product_miss"]
            )
        product_name = str(params["name"]).strip()
        existing_product = await self._find_product_by_name(product_name)
        if existing_product:
            return ActionResult(
                success=False,
                http_status=409,
                message=_MSG["create_product_exists"],
                data=existing_product,
            )

        payload: dict[str, Any] = {"name": product_name}
        if "price" in params:
            payload["price"] = float(params["price"].replace(",", "."))
        if "quantity" in params:
            payload["quantity"] = int(params["quantity"])

        return await self._post("/api/products", payload, "create_product")

    async def _handle_delete_product(self, params: dict) -> ActionResult:
        if "product_id" in params:
            return await self._delete(f"/api/products/{params['product_id']}", "delete_product")
        if "name" in params:
            return await self._delete(f"/api/products/by-name/{params['name']}", "delete_product")
        return ActionResult(
            success=False, http_status=400, message=_MSG["delete_product_miss"]
        )

    async def _handle_list_products(self, params: dict) -> ActionResult:
        return await self._get("/api/products", "list_products")

    async def _handle_create_order(self, params: dict) -> ActionResult:
        product_name = self._extract_product_name(params)
        if not product_name:
            return ActionResult(
                success=False,
                http_status=400,
                message=_MSG["create_order_miss"],
            )

        product = await self._find_product_by_name(product_name)
        if not product:
            return ActionResult(
                success=False,
                http_status=404,
                message=_MSG["create_order_not_found"].format(detail=product_name),
            )

        product_id = self._extract_id(product)
        if product_id is None:
            return ActionResult(
                success=False,
                http_status=500,
                message=_MSG["create_order_fail"].format(detail="Không đọc được product_id từ API product."),
            )

        quantity = self._to_int(params.get("quantity"), default=1)
        payload: dict[str, Any] = {
            "productId": product_id,
            "quantity": quantity,
        }

        order_id = self._to_int(params.get("order_id"))
        if order_id is not None:
            payload["orderId"] = order_id

        if "customer" in params:
            payload["customer"] = params["customer"]

        # Try common order-item endpoints, fallback to legacy order creation.
        for path in ("/api/orderitems", "/api/order-items", "/api/orderitem"):
            result = await self._post(path, payload, "create_order")
            if result.success or result.http_status != 404:
                return result

        fallback_payload: dict[str, Any] = {k: v for k, v in params.items()}
        fallback_payload["product_id"] = product_id
        return await self._post("/api/orders", fallback_payload, "create_order")

    async def _handle_list_orders(self, params: dict) -> ActionResult:
        return await self._get("/api/orders", "list_orders")

    async def _handle_unknown(self, params: dict) -> ActionResult:
        return ActionResult(
            success=False,
            http_status=400,
            message=_MSG["unknown_intent"],
        )

    # ------------------------------------------------------------------
    # HTTP helpers
    # ------------------------------------------------------------------

    async def _get(self, path: str, intent: str) -> ActionResult:
        async with httpx.AsyncClient(
            base_url=self._base_url,
            headers=self._headers,
            timeout=self.TIMEOUT,
        ) as client:
            resp = await client.get(path)
        return self._build_result(resp, intent, "ok", "fail")

    async def _post(self, path: str, payload: dict, intent: str) -> ActionResult:
        async with httpx.AsyncClient(
            base_url=self._base_url,
            headers=self._headers,
            timeout=self.TIMEOUT,
        ) as client:
            resp = await client.post(path, json=payload)
        return self._build_result(resp, intent, "ok", "fail")

    async def _delete(self, path: str, intent: str) -> ActionResult:
        async with httpx.AsyncClient(
            base_url=self._base_url,
            headers=self._headers,
            timeout=self.TIMEOUT,
        ) as client:
            resp = await client.delete(path)
        return self._build_result(resp, intent, "ok", "fail")

    @staticmethod
    def _build_result(
        resp: httpx.Response,
        intent: str,
        ok_suffix: str,
        fail_suffix: str,
    ) -> ActionResult:
        success = resp.is_success
        key = f"{intent}_{ok_suffix}" if success else f"{intent}_{fail_suffix}"

        try:
            data: dict | None = resp.json() if resp.content else None
        except Exception:
            data = None

        # Build detail for failure message
        detail = ""
        if not success:
            if data and isinstance(data, dict):
                detail = data.get("message") or data.get("detail") or data.get("title") or str(resp.status_code)
            else:
                detail = str(resp.status_code)

        template = _MSG.get(key, "{detail}")
        message = template.format(detail=detail) if "{detail}" in template else template

        return ActionResult(
            success=success,
            http_status=resp.status_code,
            message=message,
            data=data if success else None,
        )

    async def _find_product_by_name(self, name: str) -> dict[str, Any] | None:
        candidate = name.strip()
        if not candidate:
            return None

        by_name = await self._get(f"/api/products/by-name/{candidate}", "get_product")
        if by_name.success and isinstance(by_name.data, dict):
            return by_name.data

        products = await self._get("/api/products", "list_products")
        if not products.success or products.data is None:
            return None

        rows = self._extract_collection(products.data)
        if not rows:
            return None

        target = self._normalize_text(candidate)
        for row in rows:
            if not isinstance(row, dict):
                continue
            row_name = str(row.get("name") or row.get("productName") or "").strip()
            if row_name and self._normalize_text(row_name) == target:
                return row
        return None

    @staticmethod
    def _extract_collection(data: Any) -> list[Any]:
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            for key in ("items", "data", "results", "value"):
                value = data.get(key)
                if isinstance(value, list):
                    return value
        return []

    @staticmethod
    def _normalize_text(value: str) -> str:
        normalized = unicodedata.normalize("NFKD", value)
        no_accent = "".join(ch for ch in normalized if not unicodedata.combining(ch))
        return " ".join(no_accent.lower().split())

    @staticmethod
    def _extract_product_name(params: dict[str, Any]) -> str | None:
        for key in ("product", "name", "item", "dish"):
            value = params.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return None

    @staticmethod
    def _to_int(value: Any, default: int | None = None) -> int | None:
        if value is None:
            return default
        try:
            return int(str(value).strip())
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _extract_id(product: dict[str, Any]) -> int | None:
        for key in ("id", "productId", "product_id"):
            value = product.get(key)
            try:
                if value is not None:
                    return int(value)
            except (TypeError, ValueError):
                continue
        return None

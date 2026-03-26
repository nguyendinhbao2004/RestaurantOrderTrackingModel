"""
app/services/intent_service.py
--------------------------------
Rule-based Natural Language Understanding (NLU) for Vietnamese voice commands.

Design: zero-dependency, offline, pure Python regex.
        Every intent is defined as a dict entry — easy to extend.

Adding new intents:
    1. Add a key to INTENT_CATALOG with 'patterns' (trigger phrases)
       and 'params' (named capture groups as regex strings).
    2. Add the corresponding handler in ActionService.
"""

from __future__ import annotations

import re
from typing import Any

from app.core.logging import get_logger
from app.schemas.voice_schema import ParsedIntent

logger = get_logger(__name__)

_ORDER_VERBS = (
    "cho toi",
    "cho tui",
    "cho tuy",
    "cho minh",
    "cho anh",
    "cho chi",
    "cho em",
    "lay",
    "them",
    "goi",
    "order",
)

_QTY_TOKEN = r"\d+|một|mot|hai|ba|bốn|bon|tư|tu|năm|nam|sáu|sau|bảy|bay|tám|tam|chín|chin|mười|muoi"

# ---------------------------------------------------------------------------
# Intent catalog — edit freely to match your .NET 10 API routes
# ---------------------------------------------------------------------------

# Each entry:
#   patterns: list of Vietnamese keyword substrings that trigger this intent
#   params:   dict[param_name → regex with ONE capture group]
#
# Params are extracted from the full transcript text (case-insensitive).
# If a param is not found, it is omitted from ParsedIntent.params.

INTENT_CATALOG: dict[str, dict] = {

    # ── User management ──────────────────────────────────────────────────
    "create_user": {
        "patterns": [
            "tạo user", "tạo người dùng", "thêm user",
            "thêm người dùng", "tạo tài khoản", "thêm tài khoản",
            "đăng ký user", "tạo account",
        ],
        "params": {
            "username": r"(?:tên|username|tên đăng nhập)\s+(?:là\s+)?([A-Za-z0-9_\.]+)",
            "password": r"(?:mật khẩu|password|pass)\s+(?:là\s+)?(\S+)",
            "email":    r"(?:email|mail)\s+(?:là\s+)?([A-Za-z0-9_.+\-]+@[A-Za-z0-9_.\-]+)",
            "role":     r"(?:vai trò|role|quyền)\s+(?:là\s+)?([A-Za-z0-9]+)",
        },
    },

    "delete_user": {
        "patterns": [
            "xóa user", "xóa người dùng", "xóa tài khoản",
            "xóa account", "xóa tên",
        ],
        "params": {
            "username": r"(?:tên|username)\s+(?:là\s+)?([A-Za-z0-9_\.]+)",
            "user_id":  r"(?:id|mã)\s+(?:là\s+)?(\d+)",
        },
    },

    "list_users": {
        "patterns": [
            "danh sách user", "xem user", "liệt kê user",
            "danh sách người dùng", "xem tài khoản", "tất cả user",
        ],
        "params": {},   # No parameters needed
    },

    "get_user": {
        "patterns": [
            "tìm user", "thông tin user", "xem user tên",
            "tìm người dùng", "thông tin người dùng",
        ],
        "params": {
            "username": r"(?:tên|username)\s+(?:là\s+)?([A-Za-z0-9_\.]+)",
            "user_id":  r"(?:id|mã)\s+(?:là\s+)?(\d+)",
        },
    },

    # ── Product management ───────────────────────────────────────────────
    "create_product": {
        "patterns": [
            "tạo sản phẩm", "thêm sản phẩm", "thêm hàng", "tạo hàng",
            "thêm mặt hàng", "tạo mặt hàng", "tạo món", "thêm món",
        ],
        "params": {
            "name":     r"(?:tên|name|món|sản phẩm|mặt hàng)\s+(?:là\s+)?([A-Za-z0-9À-ỹ\s]+?)(?:\s+(?:giá|số lượng|price|quantity|$))",
            "price":    r"(?:giá|price)\s+(?:là\s+)?([0-9]+(?:[.,][0-9]+)?)",
            "quantity": r"(?:số lượng|quantity|sl)\s+(?:là\s+)?(\d+)",
        },
    },

    "delete_product": {
        "patterns": [
            "xóa sản phẩm", "xóa hàng", "xóa mặt hàng",
        ],
        "params": {
            "name":       r"(?:tên|name)\s+(?:là\s+)?([A-Za-z0-9\s]+)",
            "product_id": r"(?:id|mã)\s+(?:là\s+)?(\d+)",
        },
    },

    "list_products": {
        "patterns": [
            "danh sách sản phẩm", "xem sản phẩm", "liệt kê sản phẩm",
            "tất cả sản phẩm", "xem hàng",
        ],
        "params": {},
    },

    # ── Order management ─────────────────────────────────────────────────
    "create_order": {
        "patterns": [
            "tạo đơn hàng", "thêm đơn hàng", "tạo order", "đặt hàng",
            "gọi món", "order món", "đặt món", "gọi thêm món",
            # Common STT recognition errors for "đơn hàng" / "tạo"
            "tạo đương hẹn", "tạo đơn hẹn", "tạo don hang", "tao don hang",
            "đương hẹn", "đơn hẹn", "don hang",
            # Natural ordering speech in restaurants
            "cho tôi", "cho tui", "cho tuy", "cho mình", "cho em", "cho anh", "cho chị",
            "lấy", "thêm", "cho",
        ],
        "params": {
            "customer":   r"(?:tên khắc|khắc|tên|customer|khách)\s+(?:là\s+)?([A-Za-z0-9À-ỹ\s]+?)[\s,;.]*(?:sản phẩm|sẵn phẩm|product|hàng|$)",
            "product":    r"(?:sản phẩm|sẵn phẩm|product|hàng|món)\s+(?:là\s+)?([A-Za-z0-9À-ỹ\s\d]+?)[\s,;.]*(?:số lượng|giá|cân|order|đơn|$)",
            "quantity":   r"(?:số lượng|cân|sl|quantity)\s+(?:là\s+)?(\d+|một|mot|hai|ba|bốn|bon|tư|tu|bốn|bon|năm|nam|sáu|sau|bảy|bay|tám|tam|chín|chin|mười|muoi)",
            "order_id":   r"(?:đơn|order)\s*(?:id|mã)?\s*(?:là\s+)?(\d+)",
        },
    },

    "list_orders": {
        "patterns": [
            "danh sách đơn hàng", "xem đơn hàng", "liệt kê đơn hàng",
            "tất cả đơn hàng", "xem order",
        ],
        "params": {},
    },
}

# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------

class IntentService:
    """
    Parses a Vietnamese transcript into an intent + parameter dict.

    Matching strategy:
    1. Lowercase the transcript.
    2. For each intent, check if ANY of its trigger phrases appear in the text.
    3. First match wins (order of INTENT_CATALOG dict insertion).
    4. Extract params using the intent's regex patterns.
    5. Return ParsedIntent("unknown") if no intent matched.
    """

    def parse(self, transcript: str) -> ParsedIntent:
        """
        Args:
            transcript: Raw Vietnamese STT output.

        Returns:
            ParsedIntent with intent name and extracted parameters.
        """
        text_lower = transcript.lower().strip()
        logger.info("Parsing intent.", transcript=transcript[:80])

        for intent_name, definition in INTENT_CATALOG.items():
            # Check trigger phrases
            if not any(phrase in text_lower for phrase in definition["patterns"]):
                continue

            # Extract parameters
            params = self._extract_params(transcript, definition["params"])

            if intent_name == "create_order":
                items = self._extract_order_items(transcript)
                if items:
                    params["items"] = items
                    if "product" not in params:
                        params["product"] = items[0]["product"]
                    if "quantity" not in params:
                        params["quantity"] = items[0]["quantity"]

            logger.info(
                "Intent matched.",
                intent=intent_name,
                params=list(params.keys()),
            )
            return ParsedIntent(intent=intent_name, params=params, confidence=1.0)

        # Heuristic fallback for natural order sentences where trigger phrase is noisy.
        if self._looks_like_order_request(text_lower):
            params = self._extract_params(transcript, INTENT_CATALOG["create_order"]["params"])
            items = self._extract_order_items(transcript)
            if items:
                params["items"] = items
                if "product" not in params:
                    params["product"] = items[0]["product"]
                if "quantity" not in params:
                    params["quantity"] = items[0]["quantity"]
            if "product" not in params:
                inferred_product = self._infer_product_from_free_speech(transcript)
                if inferred_product:
                    params["product"] = inferred_product
            if "quantity" not in params:
                inferred_qty = self._infer_quantity_from_free_speech(transcript)
                if inferred_qty:
                    params["quantity"] = inferred_qty

            logger.info("Intent inferred by fallback.", intent="create_order", params=list(params.keys()))
            return ParsedIntent(intent="create_order", params=params, confidence=0.7)

        logger.warning("No intent matched.", transcript=transcript[:80])
        return ParsedIntent(intent="unknown", params={}, confidence=0.0)

    @staticmethod
    def _extract_params(text: str, patterns: dict[str, str]) -> dict[str, Any]:
        """Run each regex pattern against the transcript and collect matches."""
        extracted: dict[str, Any] = {}
        for param_name, pattern in patterns.items():
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                extracted[param_name] = match.group(1).strip()
        return extracted

    @staticmethod
    def _looks_like_order_request(text_lower: str) -> bool:
        has_verb = any(verb in text_lower for verb in _ORDER_VERBS)
        has_qty = re.search(rf"\b({_QTY_TOKEN})\b", text_lower) is not None
        return has_verb and has_qty

    @staticmethod
    def _extract_order_items(text: str) -> list[dict[str, str]]:
        items: list[dict[str, str]] = []
        parts = re.split(r"\b(?:và|va|với|voi)\b", text, flags=re.IGNORECASE)
        item_pattern = re.compile(
            rf"(?:cho\s+\w+\s+|lấy\s+|them\s+|thêm\s+|gọi\s+|goi\s+|order\s+)?({_QTY_TOKEN})\s+([A-Za-z0-9À-ỹ\s]+)",
            re.IGNORECASE,
        )

        for part in parts:
            match = item_pattern.search(part)
            if not match:
                continue
            quantity = match.group(1).strip()
            product = " ".join(match.group(2).split())
            product = re.sub(r"[\.,;:!?]+$", "", product).strip()
            if not product:
                continue
            items.append({"product": product, "quantity": quantity})
        return items

    @staticmethod
    def _infer_product_from_free_speech(text: str) -> str | None:
        match = re.search(
            rf"(?:cho\s+\w+\s+|lấy\s+|thêm\s+|gọi\s+)?(?:{_QTY_TOKEN})\s+([A-Za-z0-9À-ỹ\s]+?)(?:\s+và\s+(?:{_QTY_TOKEN})|[\.,;]|$)",
            text,
            re.IGNORECASE,
        )
        if not match:
            return None
        product = " ".join(match.group(1).split())
        return product or None

    @staticmethod
    def _infer_quantity_from_free_speech(text: str) -> str | None:
        match = re.search(
            rf"(?:cho\s+\w+\s+|lấy\s+|thêm\s+|gọi\s+)?({_QTY_TOKEN})\s+[A-Za-z0-9À-ỹ]+",
            text,
            re.IGNORECASE,
        )
        if not match:
            return None
        return match.group(1).strip()


# Module-level singleton
intent_service = IntentService()

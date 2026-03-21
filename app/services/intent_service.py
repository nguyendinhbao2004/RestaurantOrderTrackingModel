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
        ],
        "params": {
            "customer":   r"(?:khách|customer|tên khách)\s+(?:là\s+)?([A-Za-z0-9\s]+?)(?:\s+(?:sản phẩm|đặt|order|$))",
            "product":    r"(?:sản phẩm|product|hàng|món)\s+(?:là\s+)?([A-Za-z0-9À-ỹ\s]+?)(?:\s+(?:số lượng|giá|order|đơn|$))",
            "quantity":   r"(?:số lượng|sl|quantity)\s+(?:là\s+)?(\d+)",
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

            logger.info(
                "Intent matched.",
                intent=intent_name,
                params=list(params.keys()),
            )
            return ParsedIntent(intent=intent_name, params=params, confidence=1.0)

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


# Module-level singleton
intent_service = IntentService()

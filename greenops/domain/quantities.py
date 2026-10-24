"""Units, decimal parsing and canonical hashing. Pure functions only."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from enum import Enum
from typing import Any

GIB = 1024**3


class DomainError(ValueError):
    """Stable domain validation failure; `code` maps to an API error code."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def dec(value: Any, *, field: str = "value", allow_negative: bool = False) -> Decimal:
    """Parse to Decimal; reject NaN, infinity, floats with binary noise are passed via str()."""
    if isinstance(value, bool):
        raise DomainError("VALIDATION_ERROR", f"{field}: boolean is not a quantity")
    try:
        d = Decimal(str(value)) if not isinstance(value, Decimal) else value
    except (InvalidOperation, ValueError):
        raise DomainError("VALIDATION_ERROR", f"{field}: not a decimal quantity: {value!r}")
    if not d.is_finite():
        raise DomainError("VALIDATION_ERROR", f"{field}: non-finite quantity rejected")
    if d < 0 and not allow_negative:
        raise DomainError("VALIDATION_ERROR", f"{field}: negative quantity rejected")
    return d


_BYTE_UNITS = {"B": 1, "KiB": 1024, "MiB": 1024**2, "GiB": GIB, "TiB": 1024**4,
               "KB": 1000, "MB": 1000**2, "GB": 1000**3, "TB": 1000**4}


def to_bytes(quantity: Any, unit: str) -> Decimal:
    """Explicit byte conversion. GB (decimal) and GiB (binary) are different units."""
    if unit not in _BYTE_UNITS:
        raise DomainError("VALIDATION_ERROR", f"unsupported memory unit {unit!r}")
    return dec(quantity, field="memory") * _BYTE_UNITS[unit]


def require_same(label: str, a: str, b: str) -> None:
    if a != b:
        raise DomainError("VALIDATION_ERROR", f"{label} mismatch: {a!r} vs {b!r}; explicit conversion required")


def utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        raise DomainError("VALIDATION_ERROR", "naive timestamp rejected; UTC required")
    return dt.astimezone(timezone.utc)


def rfc3339(dt: datetime) -> str:
    return utc(dt).isoformat().replace("+00:00", "Z")


def _canon(obj: Any) -> Any:
    if isinstance(obj, Decimal):
        if not obj.is_finite():
            raise DomainError("VALIDATION_ERROR", "non-finite decimal cannot be hashed")
        return format(obj.normalize(), "f")
    if isinstance(obj, float):
        raise DomainError("VALIDATION_ERROR", "floats are not allowed in canonical documents; use Decimal")
    if isinstance(obj, datetime):
        return rfc3339(obj)
    if isinstance(obj, Enum):
        return obj.value
    if isinstance(obj, dict):
        return {str(k): _canon(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_canon(v) for v in obj]
    if hasattr(obj, "model_dump"):
        return _canon(obj.model_dump(mode="python"))
    return obj


def canonical_bytes(obj: Any) -> bytes:
    """Versioned canonical JSON: sorted keys, no whitespace, decimals as strings, UTC timestamps."""
    return json.dumps(_canon(obj), sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def sha256_digest(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def canonical_hash(obj: Any) -> str:
    return sha256_digest(canonical_bytes(obj))

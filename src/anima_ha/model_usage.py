"""Bounded provider-reported usage metadata. Never authority or billing proof."""

from typing import Any
from uuid import UUID

TOKEN_FIELDS = frozenset(
    {
        "input_tokens",
        "cached_input_tokens",
        "output_tokens",
        "total_tokens",
        "reasoning_output_tokens",
    }
)


def model_call_receipt(value: Any) -> dict[str, Any]:
    required = {
        "call_id",
        "purpose",
        "model",
        "phase",
        "status",
        "usage",
        "usage_status",
        "elapsed_ms",
    }
    if not isinstance(value, dict) or set(value) != required:
        raise ValueError("INVALID_MODEL_CALL_RECEIPT")
    if any(
        type(value[key]) is not str
        for key in ("call_id", "purpose", "model", "phase", "status", "usage_status")
    ):
        raise ValueError("INVALID_MODEL_CALL_RECEIPT")
    UUID(str(value["call_id"]))
    if (
        value["purpose"] not in {"PLANNER", "FINAL", "AUTH_SMOKE"}
        or value["model"] != "gpt-5.6-luna"
        or value["phase"] not in {"ATTEMPTED", "FINISHED"}
        or value["status"]
        not in {"UNKNOWN", "SUCCEEDED", "FAILED", "TIMEOUT", "LAUNCH_FAILED", "INVALID_RESULT"}
        or value["usage_status"] not in {"UNKNOWN", "REPORTED"}
        or type(value["elapsed_ms"]) is not int
        or not 0 <= value["elapsed_ms"] <= 900_000
    ):
        raise ValueError("INVALID_MODEL_CALL_RECEIPT")
    usage = value["usage"]
    if value["usage_status"] == "UNKNOWN":
        if usage is not None:
            raise ValueError("INVALID_MODEL_CALL_USAGE")
    elif (
        not isinstance(usage, dict)
        or not usage
        or set(usage) - TOKEN_FIELDS
        or any(type(item) is not int or not 0 <= item <= 10**12 for item in usage.values())
    ):
        raise ValueError("INVALID_MODEL_CALL_USAGE")
    if value["phase"] == "ATTEMPTED" and (
        value["status"] != "UNKNOWN" or usage is not None or value["elapsed_ms"] != 0
    ):
        raise ValueError("INVALID_MODEL_CALL_ATTEMPT")
    return dict(value)

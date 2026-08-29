from __future__ import annotations

import json
import logging

from anima_ha.logging_setup import JsonFormatter


def test_json_formatter_emits_structured_record() -> None:
    record = logging.LogRecord("test", logging.INFO, __file__, 1, "ready", (), None)
    record.component = "baseline"
    payload = json.loads(JsonFormatter().format(record))
    assert payload["level"] == "INFO"
    assert payload["logger"] == "test"
    assert payload["message"] == "ready"
    assert payload["component"] == "baseline"
    assert payload["timestamp"].endswith("+00:00")

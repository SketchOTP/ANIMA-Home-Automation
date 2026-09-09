"""Sparse, live reasoning inputs for SENTRY; never a notification rule engine."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from anima_ha.family_routines import family_routines_page
from anima_ha.intelligence import IntelligenceRequest
from anima_ha.preferences import preferences_page

REASONING_GUIDANCE = (
    "Decide whether to do nothing, ask, investigate, or notify; "
    "no greeting or action is mandatory. "
    "Consult relevant household and individual preferences, routines, presence evidence, and "
    "long-term memory before choosing a response or delivery channel. Individual preferences "
    "are scoped exceptions, not a replacement for everyone else's choices. Resolve conflicts "
    "explicitly; do not invent a recipient, email address, quiet-hours window or authorization. "
    "Routines are expectations, not proof of presence. Phones and router associations are "
    "fallible presence evidence, never proof of who opened a door. Check current state when "
    "freshness matters. Read relevant memory with its sources and confidence, and correct "
    "obsolete lessons rather than treating notes as policy. Save only useful durable facts "
    "actually told or discovered and reusable lessons through ANIMA knowledge tools. Never "
    "invent a knowledge classifier: its root must be exactly 000, 100, 300, 600, 640, 900, "
    "or 920, with only an optional decimal subdivision. When correcting a note, reuse the "
    "exact note ID and full digest from the current read programmatically; never retype them. "
    "Never "
    "store secrets, whole transcripts, ephemeral restricted product content or unsupported "
    "personal conclusions. A successful tool acknowledgment is not physical verification. "
    "Only claim notification delivery when the selected channel reports its actual result."
    " Correlate nearby timestamped signals; never treat missing events as proof of absence "
    "or one phone/lock label as authenticated identity. Use ANIMA's initiative disposition: "
    "always-notify events bypass learning, optional proactive delivery waits for real "
    "multi-day evidence and owner enablement. Learning reviews are silent work, not unsolicited "
    "announcements. Save observed routines as inferred suggestions with source references, "
    "never overwrite owner-declared expectations. Repeated work may justify a reusable "
    "workflow proposal; generated code must not execute or self-register as an authorized tool."
)


def household_reasoning_context(
    request: IntelligenceRequest, memory: Any, graph: Any, *, initiative: Any = None
) -> dict[str, Any]:
    """Refresh bounded preferences/expectations without mutating the stored packet.

    Details of other people and the vault are not pre-dumped. The frozen tools
    remain the path to further person-scoped reads and relevant memory search.
    """
    result: dict[str, Any] = {
        "generated_at": datetime.now(UTC).isoformat(),
        "guidance": REASONING_GUIDANCE,
        "authority": "NONE",
        "preferences": {"status": "UNAVAILABLE"},
        "routines": {"status": "UNAVAILABLE"},
        "memory": {"status": "READ_RELEVANT_NOTES_ON_DEMAND"},
        "presence": {"status": "READ_FRESH_EVIDENCE_ON_DEMAND"},
    }
    if initiative is not None:
        result["initiative"] = initiative(request)
    preference_context: dict[str, Any] = {
        "status": "UNAVAILABLE",
        "household": {"status": "UNAVAILABLE"},
        "request_person": {"status": "UNAVAILABLE" if request.principal_id else "NOT_APPLICABLE"},
        "other_people": "Use scoped list_preferences when an event concerns another member",
    }
    result["preferences"] = preference_context
    try:
        shared = preferences_page(
            memory, request.household_id, graph=graph, scope="household", limit=10
        )
        preference_context["household"] = {"status": "AVAILABLE", **shared}
    except Exception:
        pass
    if request.principal_id is not None:
        try:
            personal = preferences_page(
                memory,
                request.household_id,
                graph=graph,
                person_id=str(request.principal_id),
                limit=10,
            )
            preference_context["request_person"] = {"status": "AVAILABLE", **personal}
        except Exception:
            pass
    statuses = [preference_context[key]["status"] for key in ("household", "request_person")]
    preference_context["status"] = (
        "AVAILABLE"
        if "UNAVAILABLE" not in statuses
        else "PARTIAL"
        if "AVAILABLE" in statuses
        else "UNAVAILABLE"
    )
    try:
        page = family_routines_page(
            memory,
            graph,
            request.household_id,
            limit=10,
            person_id=str(request.principal_id) if request.principal_id else None,
        )
        result["routines"] = {"status": "AVAILABLE", **page}
    except Exception:
        pass
    return result

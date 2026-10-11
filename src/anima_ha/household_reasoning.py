"""Sparse, live reasoning inputs for SENTRY; never a notification rule engine."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from anima_ha.family_routines import family_routines_page
from anima_ha.intelligence import IntelligenceRequest
from anima_ha.preferences import preferences_page

REASONING_GUIDANCE = (
    "Do not merely repeat sensor names or count triggers. Reason from the combined timeline: "
    "state the important observations, how household relationships and event order connect them, "
    "the most plausible situation, a serious alternative, confidence and unknowns, then choose "
    "a proportionate next step. When independent evidence supports a recognizable situation, "
    "say what likely happened instead of stopping at a sensor-pattern description. "
    "Decide whether to do nothing, ask, investigate, greet, assist, or notify. "
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
    " Correlate nearby timestamped signals and learned multi-signal episodes. For example, "
    "driveway/entry motion followed by a member-associated phone reconnect can support a likely "
    "arrival and a welcome; motion followed by that device disconnecting can support a possible "
    "departure. A missing doorbell-press record does not refute either inference. Do not infer "
    "that a departure is for work unless a relevant owner-declared routine "
    "or schedule supports it. "
    "At night, use explicit source coverage and a quiet interval only when those coverage facts "
    "are available; backyard motion plus a basement-window opening can be anomalous and may "
    "warrant a prompt homeowner alert through an already approved route, while actor and intent "
    "remain unknown. During declared owner travel, account for household members who remain "
    "home; children's ordinary movement is not itself suspicious, but repeated unexpected "
    "entry/garage signals may warrant an approved owner notification. Never treat missing events "
    "as proof of absence or one phone/lock label as authenticated identity. "
    "Use ANIMA's initiative disposition: "
    "always-notify events bypass learning, optional proactive delivery waits for real "
    "multi-day evidence and owner enablement. When a likely arrival is supported and relevant "
    "preferences permit, use the existing greeting/speech path once; avoid duplicate welcome "
    "messages. To assist a routine, inspect the actual available tools and preferences first, "
    "then propose or perform only an action the current catalog and policy allow. Do not claim "
    "coffee, lighting, music, weather or calendar capability unless a live tool is available and "
    "its result is verified. Learning reviews are silent work, not unsolicited "
    "announcements. Save observed routines as inferred suggestions with source references, "
    "never overwrite owner-declared expectations. Repeated work may justify a reusable "
    "workflow proposal; generated code must not execute or self-register as an authorized tool."
    " The bounded household_situation separates inventory, observations and source coverage. "
    "HOME/AWAY/UNSET is an explicit owner declaration, not inferred occupancy or permission. "
    "When an already reasoning-eligible event warrants an incident assessment, distinguish "
    "observed, inferred and unknown; consider legitimate arrivals, conflicting or stale "
    "signals, source outages and tenant scope. Do not script an intruder conclusion. "
    "Duplicate transport receipts are not independent corroboration, and familiarity must "
    "not suppress required canonical speech. Record at most one bounded source-linked "
    "assessment through the frozen record_incident_assessment tool when authorized; "
    "its data is not action authority. Immediate-only routes remain zero-model and must "
    "not gain commentary. Existing owner route selection is the contextual opt-in."
)


def household_reasoning_context(
    request: IntelligenceRequest,
    memory: Any,
    graph: Any,
    *,
    initiative: Any = None,
    situation: Any = None,
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
        correlation = getattr(initiative, "correlation_context", None)
        if callable(correlation):
            result["initiative"]["nearby_events"] = correlation(request)
        feedback = getattr(initiative, "prospective_feedback_context", None)
        if callable(feedback):
            result["prospective_feedback"] = feedback(request)
    if situation is not None:
        # Rich context is an optional reasoning read, never notification policy
        # or the durable canonical speech initializer/claim dependency.
        result["household_situation"] = situation(request.household_id)
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

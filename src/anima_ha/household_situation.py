"""Bounded commissioned context; observation, inference and authority stay separate.

No new state platform: Graph is inventory, Journal is observation history,
Memory retains assessments, and the existing request/action ledgers own results.
Event age is never a source-uptime or human-occupancy measurement.
"""

from __future__ import annotations

import json
import os
import re
import stat
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import UUID

import psycopg
from psycopg.rows import dict_row

from anima_ha.graph import NodeKind
from anima_ha.preferences import _household


def diagnostic_coverage(path: Path, *, now: datetime | None = None) -> dict[str, Any]:
    """Bounded passive readiness; stale/absent diagnostics never mean quiet."""
    at = now or datetime.now(UTC)
    result: dict[str, Any] = {
        "status": "NOT_READY",
        "reason": "NO_FRESH_READINESS",
        "coverage": "PROCESS_DIAGNOSTIC_NOT_DELIVERY_PROOF",
    }
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(fd) as stream:
            info = os.fstat(stream.fileno())
            if (
                not stat.S_ISREG(info.st_mode)
                or info.st_size > 16384
                or info.st_nlink != 1
                or info.st_uid != os.geteuid()
                or stat.S_IMODE(info.st_mode) != 0o600
            ):
                return result
            value = json.loads(stream.read(16385))
        stamp = datetime.fromisoformat(value["observed_at"])
        if stamp.tzinfo is None or stamp.utcoffset() is None:
            return result
        age = (at - stamp).total_seconds()
        state = value.get("state")
        if state in {"READY", "DEGRADED", "NOT_READY"} and 0 <= age <= 90:
            result.update(status=state, observed_at=stamp.isoformat())
            result.pop("reason")
        components = value.get("components", {})
        if isinstance(components, dict):
            faults = {
                str(component.get("reason"))
                for component in components.values()
                if isinstance(component, dict)
                and component.get("reason") in {"BINDER_PERMISSION", "SOURCE_ACCESS"}
            }
            if faults:
                result["last_access_fault"] = sorted(faults)[0]
    except (OSError, ValueError, TypeError, KeyError, AttributeError):
        return result
    return result


def public_delivery(value: Any, *, followup: bool = False) -> dict[str, Any]:
    """Credential/lease/client fields never enter UI or reasoning context."""
    if not isinstance(value, dict) or not value:
        return {"status": "NOT_MANAGED", "human_receipt": "NOT_VERIFIED"}
    result: dict[str, Any] = {"human_receipt": "NOT_VERIFIED"}
    for key in ("state", "execution_kind", "reason"):
        item = value.get(key)
        if isinstance(item, str) and re.fullmatch(r"[A-Z0-9_]{1,96}", item):
            result[key] = item
    for key in ("created_at", "receipt_at", "retry_at"):
        item = value.get(key)
        if isinstance(item, str) and len(item) <= 64:
            try:
                stamp = datetime.fromisoformat(item)
                if stamp.tzinfo is not None and stamp.utcoffset() is not None:
                    result[key] = stamp.astimezone(UTC).isoformat()
            except ValueError:
                continue
    evidence = value.get("evidence", {})
    if isinstance(evidence, dict):
        safe = {
            key: evidence[key]
            for key in (
                "playback_state",
                "timing_source",
                "playback_process_started_at",
                "playback_completed_at",
            )
            if isinstance(evidence.get(key), str) and len(evidence[key]) <= 64
        }
        # Process evidence is not an audible-device endpoint.
        safe["actual_audible_start_at"] = None
        result["evidence"] = safe
    if not followup and isinstance(value.get("followup"), dict):
        result["followup"] = public_delivery(value["followup"], followup=True)
    return result


def public_action(action: dict[str, Any], request_key: str) -> dict[str, Any] | None:
    prefix = f"{request_key}:action:"
    key = action["idempotency_key"]
    if not key.startswith(prefix) or not re.fullmatch(r"[0-9]{1,6}", key[len(prefix) :]):
        return None
    result = action.get("result")
    effects = result.get("effects", []) if isinstance(result, dict) else []
    verified = (
        action["status"] == "SUCCEEDED"
        and isinstance(effects, list)
        and 1 <= len(effects) <= 12
        and all(
            isinstance(effect, dict) and effect.get("outcome") == "VERIFIED" for effect in effects
        )
    )
    return {
        "action_id": str(action["action_id"]),
        "status": action["status"],
        "recorded_at": action["updated_at"].isoformat(),
        "provenance": "ANIMA_REQUEST_ACTION_NAMESPACE",
        "verification": "COORDINATOR_EXPECTED_EFFECTS_VERIFIED"
        if verified
        else "NOT_VERIFIED_OR_UNCERTAIN",
        "human_receipt": "NOT_VERIFIED",
        "physical_result": "NOT_INDEPENDENTLY_VERIFIED_BY_THIS_PROJECTION",
        "verification_basis": "PROVIDER_RECEIPT_ACCEPTANCE_NOT_HUMAN_RECEIPT"
        if effects
        and all(
            isinstance(effect, dict) and effect.get("source") == "PROVIDER_RECEIPT"
            for effect in effects
        )
        else "COORDINATOR_EXPECTED_EFFECT_EVIDENCE"
        if verified
        else "UNVERIFIED",
    }


class HouseholdSituation:
    def __init__(
        self,
        database_url: str,
        graph: Any,
        evidence: Any,
        coverage: Callable[[UUID], dict[str, Any]],
    ) -> None:
        self.database_url, self.graph, self.evidence = database_url, graph, evidence
        self.coverage = coverage

    def __call__(self, household_id: UUID) -> dict[str, Any]:
        _household(self.graph, household_id)
        now = datetime.now(UTC)
        places = self.graph.places_in_household(household_id)
        resources = self.graph.resources_in_place(household_id)
        members = self.graph.members_of_household(household_id)
        if len(places) + len(resources) + len(members) > 256:
            raise ValueError("commissioned context exceeds bounded inventory")
        nodes = {item.canonical_id: item for item in (*places, *resources, *members)}
        nodes[household_id] = self.graph.get_node(household_id)
        capabilities: list[dict[str, Any]] = []
        for resource in resources:
            for capability in self.graph.resource_capabilities(resource.canonical_id):
                if capability.kind != NodeKind.CAPABILITY or capability.retired_at is not None:
                    continue
                if len(capabilities) >= 256:
                    raise ValueError("commissioned capability context exceeds bound")
                capabilities.append(
                    {
                        "resource_id": str(resource.canonical_id),
                        "capability_id": str(capability.canonical_id),
                        "capability_type": capability.metadata.get("capability_type"),
                        "availability": "COMMISSIONED_NOT_PROOF_OF_LIVE_CONTROL",
                    }
                )
        observations = self.evidence.recent_household_evidence(
            household_id,
            since=now - timedelta(minutes=10),
            limit=48,
            now=now,
        )
        with psycopg.connect(
            self.database_url,
            row_factory=dict_row,
            connect_timeout=5,
            options="-c statement_timeout=5000",
        ) as conn:
            relationships = conn.execute(
                "SELECT relationship_type,source_id,target_id FROM anima_graph_relationships "
                "WHERE source_id=ANY(%s) AND target_id=ANY(%s) AND retired_at IS NULL "
                "ORDER BY relationship_id LIMIT 513",
                (list(nodes), list(nodes)),
            ).fetchall()
            if len(relationships) > 512:
                raise ValueError("commissioned relationship context exceeds bound")
            incidents = conn.execute(
                "SELECT memory_id,created_at,metadata FROM anima_memory_records "
                "WHERE household_id=%s AND status='ACTIVE' "
                "AND (expires_at IS NULL OR expires_at > %s) "
                "AND metadata->>'record_kind'='household_incident_assessment' "
                "ORDER BY created_at DESC,memory_id DESC LIMIT 12",
                (household_id, now),
            ).fetchall()
            assessments = []
            for row in incidents:
                metadata = row["metadata"]
                request = conn.execute(
                    "SELECT request_id,lifecycle,idempotency_key,request_metadata,result_metadata "
                    "FROM anima_intelligence_requests WHERE household_id=%s AND request_id=%s",
                    (household_id, UUID(metadata["request_id"])),
                ).fetchone()
                actions = []
                if request:
                    # Provider-supplied references alone cannot verify an action.
                    refs = request["result_metadata"].get("action_references", [])
                    valid_refs = []
                    for ref in refs[:12] if isinstance(refs, list) else []:
                        try:
                            valid_refs.append(UUID(str(ref)))
                        except ValueError:
                            continue
                    if valid_refs:
                        actions = conn.execute(
                            "SELECT action_id,status,idempotency_key,result,updated_at "
                            "FROM anima_actions "
                            "WHERE household_id=%s AND action_id=ANY(%s)",
                            (household_id, valid_refs),
                        ).fetchall()
                assessments.append(
                    {
                        "incident_id": str(row["memory_id"]),
                        "created_at": row["created_at"].isoformat(),
                        **{
                            key: metadata.get(key)
                            for key in (
                                "assessment",
                                "unknowns",
                                "source_refs",
                                "declared_mode",
                                "classification",
                                "disposition",
                                "request_id",
                                "source_coverage",
                            )
                        },
                        "request_lifecycle": request["lifecycle"] if request else "UNAVAILABLE",
                        "required_delivery": public_delivery(
                            request["request_metadata"].get("required_delivery", {})
                            if request
                            else {}
                        ),
                        "response_ledger": [
                            projected
                            for action in actions
                            if request
                            and (projected := public_action(action, request["idempotency_key"]))
                            is not None
                        ],
                        "authority": "NONE",
                    }
                )
        return {
            "status": "SUCCEEDED",
            "household_id": str(household_id),
            "generated_at": now.isoformat(),
            "window_seconds": 600,
            "inventory": [
                {"canonical_id": str(key), "kind": node.kind.value, "name": node.name}
                for key, node in nodes.items()
            ],
            "relationships": [
                {
                    "type": row["relationship_type"],
                    "source_id": str(row["source_id"]),
                    "target_id": str(row["target_id"]),
                }
                for row in relationships
            ],
            "capabilities": capabilities,
            "observations": observations,
            "source_coverage": self.coverage(household_id),
            "incidents": assessments,
            "unknowns": [
                "Physical occurrence time and actor identity may be unobservable.",
                "Repeated transport records are not independent corroboration.",
                "No observation-count denominator or uptime is inferred.",
            ],
            "authority": "NONE",
        }

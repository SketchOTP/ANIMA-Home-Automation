#!/usr/bin/env python3
"""Commission the owner's passive Tapo/Wansview notification resources.

The script is an operator deployment helper. It creates only canonical ANIMA
resources/capabilities and a private receiver configuration. It never reads
vendor accounts, controls a lock/camera, or qualifies an unseen notification
format. Sources become enabled only when named with ``--qualified-vendor``.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
import json
import os
import stat
import tempfile
from pathlib import Path
from uuid import NAMESPACE_URL, UUID, uuid5

from anima_ha.graph import (
    Alias,
    CanonicalNode,
    CanonicalRelationship,
    CommissioningDocument,
    NodeKind,
    PostgresHouseholdGraph,
    ProviderReference,
    RelationshipType,
)

TAPO_PACKAGE = "com.tplink.iot"
WANSVIEW_PACKAGE = "net.ajcloud.wansviewplus"


def identifier(household_id: UUID, value: str) -> UUID:
    return uuid5(NAMESPACE_URL, f"anima:{household_id}:owner-vendor:{value}")


def private_text(path: Path) -> str:
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        info = os.fstat(descriptor)
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_nlink != 1
            or stat.S_IMODE(info.st_mode) != 0o600
            or info.st_uid != os.geteuid()
            or info.st_size > 512
        ):
            raise ValueError("unsafe token file")
        return os.read(descriptor, 513).decode().strip()
    finally:
        os.close(descriptor)


def vendor_token(master: str, package_name: str) -> str:
    digest = hmac.new(master.encode(), package_name.encode(), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(digest).decode().rstrip("=")


def atomic_private(path: Path, value: dict[str, object]) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(value, stream, indent=2, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        os.chmod(path, 0o600)
    except Exception:
        Path(temporary).unlink(missing_ok=True)
        raise


def ensure_place(
    graph: PostgresHouseholdGraph,
    household_id: UUID,
    name: str,
    kind: NodeKind,
) -> CanonicalNode:
    matches = [
        item
        for item in graph.places_in_household(household_id)
        if item.retired_at is None and item.name.casefold() == name.casefold()
    ]
    if len(matches) > 1:
        raise ValueError(f"commissioned {name} place is ambiguous")
    if matches:
        return matches[0]
    return graph.create_place(household_id, household_id, name, kind)


def node(
    household_id: UUID,
    key: str,
    kind: NodeKind,
    name: str,
    metadata: dict[str, object],
) -> CanonicalNode:
    return CanonicalNode(identifier(household_id, key), kind, name, True, metadata)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database-url", default=os.environ.get("ANIMA_DATABASE_URL"))
    parser.add_argument("--household-id", type=UUID, required=True)
    parser.add_argument("--token-file", type=Path, required=True)
    parser.add_argument("--receiver-config", type=Path, required=True)
    parser.add_argument(
        "--qualified-vendor", action="append", choices=("tapo", "wansview"), default=[]
    )
    arguments = parser.parse_args()
    if not arguments.database_url:
        raise SystemExit("ANIMA_DATABASE_URL is required")
    graph = PostgresHouseholdGraph(arguments.database_url)
    household = graph.get_node(arguments.household_id)
    if household is None or household.kind != NodeKind.HOUSEHOLD:
        raise SystemExit("owner household is not commissioned")
    garage = ensure_place(graph, arguments.household_id, "Garage", NodeKind.ROOM)
    foyer = ensure_place(graph, arguments.household_id, "Foyer", NodeKind.ROOM)
    back_yard = ensure_place(graph, arguments.household_id, "Back Yard", NodeKind.ZONE)

    resources = (
        node(
            arguments.household_id,
            "tapo-front-door",
            NodeKind.RESOURCE,
            "Front Door Lock",
            {"resource_type": "lock", "provider": "tapo_android_notification"},
        ),
        node(
            arguments.household_id,
            "wansview-back-yard",
            NodeKind.SENSOR,
            "Back Yard Camera",
            {"sensor_type": "motion_notification", "provider": "wansview_android_notification"},
        ),
        node(
            arguments.household_id,
            "wansview-garage",
            NodeKind.SENSOR,
            "Garage Camera",
            {"sensor_type": "motion_notification", "provider": "wansview_android_notification"},
        ),
    )
    capabilities = (
        node(
            arguments.household_id,
            "tapo-front-door-events",
            NodeKind.CAPABILITY,
            "Front Door Lock Events",
            {"capability_type": "lock.event", "readable": True, "writable": False},
        ),
        node(
            arguments.household_id,
            "wansview-back-yard-motion",
            NodeKind.CAPABILITY,
            "Back Yard Motion Events",
            {"capability_type": "motion.event", "readable": True, "writable": False},
        ),
        node(
            arguments.household_id,
            "wansview-garage-motion",
            NodeKind.CAPABILITY,
            "Garage Motion Events",
            {"capability_type": "motion.event", "readable": True, "writable": False},
        ),
    )
    placements = (foyer, back_yard, garage)
    relationships: list[CanonicalRelationship] = []
    for resource, capability, installed_in in zip(resources, capabilities, placements, strict=True):
        relationships.extend(
            [
                CanonicalRelationship(
                    identifier(arguments.household_id, f"{resource.canonical_id}:installed"),
                    RelationshipType.INSTALLED_IN,
                    resource.canonical_id,
                    installed_in.canonical_id,
                ),
                CanonicalRelationship(
                    identifier(arguments.household_id, f"{resource.canonical_id}:exposes"),
                    RelationshipType.EXPOSES,
                    resource.canonical_id,
                    capability.canonical_id,
                ),
            ]
        )
    aliases = tuple(
        Alias(
            identifier(arguments.household_id, f"alias:{resource.canonical_id}"),
            alias,
            resource.canonical_id,
            resource.kind,
            arguments.household_id,
        )
        for resource, alias in zip(
            resources, ("Tapo DL110", "Back Yard Camera", "Garage Camera"), strict=True
        )
    )
    references = tuple(
        ProviderReference(
            identifier(arguments.household_id, f"provider:{resource.canonical_id}"),
            "android_notification",
            "owner-waydroid",
            "notification_resource",
            external,
            resource.canonical_id,
            metadata={"package_name": package},
        )
        for resource, package, external in (
            (resources[0], TAPO_PACKAGE, "front-door"),
            (resources[1], WANSVIEW_PACKAGE, "back-yard"),
            (resources[2], WANSVIEW_PACKAGE, "garage"),
        )
    )
    graph.commission(
        CommissioningDocument(
            1,
            (household, foyer, back_yard, garage, *resources, *capabilities),
            tuple(relationships),
            aliases,
            references,
        )
    )
    token = private_text(arguments.token_file)
    qualified = frozenset(arguments.qualified_vendor)

    def source(vendor: str, package: str, mappings: dict[str, UUID]) -> dict[str, object]:
        enabled = vendor in qualified
        return {
            "household_id": str(arguments.household_id),
            "relay_id": str(identifier(arguments.household_id, f"relay:{vendor}")),
            "camera_mappings": {key: str(value) for key, value in mappings.items()},
            "allowed_channels": [],
            "token": vendor_token(token, package),
            "enabled": enabled,
            "official_app_ready": True,
            "source_privacy_qualified": True,
            "transport": "waydroid_private_dbus",
            "package_name": package,
            "producer_adapter": "anima-waydroid-private-dbus",
            "producer_version": "1.0.0",
            "producer_qualified": enabled,
            "wake_enabled": enabled,
        }

    atomic_private(
        arguments.receiver_config,
        {
            "version": 1,
            "enabled": bool(qualified),
            "sources": [
                source("tapo", TAPO_PACKAGE, {"front-door": resources[0].canonical_id}),
                source(
                    "wansview",
                    WANSVIEW_PACKAGE,
                    {
                        "back-yard": resources[1].canonical_id,
                        "garage": resources[2].canonical_id,
                    },
                ),
            ],
        },
    )
    print("commissioned passive Tapo/Wansview resources and wrote private receiver config")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
